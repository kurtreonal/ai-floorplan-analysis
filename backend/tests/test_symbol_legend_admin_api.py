import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Base, Role, SymbolLegend, SymbolLegendHistory, User


class SymbolLegendAdminApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = get_engine().connect()
        self.transaction = self.connection.begin()
        self.session = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        roles = {role.name: role for role in self.session.scalars(select(Role))}
        marker = uuid4().hex
        self.admin = User(oauth_provider="pre7-test", oauth_subject=marker, role=roles["ADMIN"])
        self.designer = User(oauth_provider="pre7-test", oauth_subject=f"{marker}-designer", role=roles["DESIGNER"])
        self.session.add_all((self.admin, self.designer))
        self.session.commit()
        self.app = create_app()
        self.app.dependency_overrides[get_db] = lambda: self.session
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        self.client = TestClient(self.app)
        self.path = "/api/admin/symbol-legends"

    def tearDown(self):
        self.client.close()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def create(self, class_id=1001, name="PRE7 fixture", active=True):
        return self.client.post(self.path, json={
            "class_id": class_id,
            "name": name,
            "is_active": active,
        })

    def test_admin_create_list_update_deactivate_and_history(self):
        created = self.create()
        self.assertEqual(created.status_code, 201, created.text)
        record = created.json()
        self.assertTrue(record["is_active"])
        self.assertIsNotNone(record["created_at"])
        listing = self.client.get(self.path)
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertIn(record, listing.json())

        changed = self.client.put(f"{self.path}/{record['id']}", json={
            "class_id": 1002,
            "name": "PRE7 reviewed fixture",
            "is_active": True,
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        deactivated = self.client.put(f"{self.path}/{record['id']}", json={
            "class_id": 1002,
            "name": "PRE7 reviewed fixture",
            "is_active": False,
        })
        self.assertEqual(deactivated.status_code, 200, deactivated.text)
        self.assertFalse(deactivated.json()["is_active"])
        history = tuple(self.session.scalars(
            select(SymbolLegendHistory)
            .where(SymbolLegendHistory.symbol_legend_id == record["id"])
            .order_by(SymbolLegendHistory.sequence)
        ))
        self.assertEqual([item.action for item in history], ["created", "updated", "deactivated"])
        self.assertEqual([item.sequence for item in history], [1, 2, 3])
        self.assertTrue(all(item.actor_user_id == self.admin.id for item in history))
        self.assertEqual(history[1].old_name, "PRE7 fixture")
        self.assertEqual(history[-1].new_name, "PRE7 reviewed fixture")

    def test_designer_keeps_active_read_but_cannot_manage(self):
        record = self.create().json()
        self.app.dependency_overrides[get_current_user] = lambda: self.designer
        active = self.client.get("/api/symbol-legends")
        self.assertEqual(active.status_code, 200)
        self.assertIn(record["name"], active.text)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.create(1002, "Denied").status_code, 403)
        self.assertEqual(self.client.put(f"{self.path}/{record['id']}", json={
            "class_id": 1001, "name": record["name"], "is_active": False,
        }).status_code, 403)
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get(self.path).status_code, 401)

    def test_conflicts_validation_missing_and_noop_are_bounded(self):
        first = self.create().json()
        second = self.create(1002, "PRE7 second").json()
        self.assertEqual(self.create(1001, "Unique name").status_code, 409)
        self.assertEqual(self.create(1003, first["name"]).status_code, 409)
        conflict = self.client.put(f"{self.path}/{second['id']}", json={
            "class_id": first["class_id"], "name": second["name"], "is_active": True,
        })
        self.assertEqual(conflict.status_code, 409)
        for body in (
            {"class_id": True, "name": "Invalid", "is_active": True},
            {"class_id": -1, "name": "Invalid", "is_active": True},
            {"class_id": 20, "name": " not normalized ", "is_active": True},
            {"class_id": 20, "name": "Invalid", "is_active": 1},
            {"class_id": 20, "name": "Invalid", "is_active": True, "glyph_path": "private.png"},
        ):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.path, json=body).status_code, 422)
        self.assertEqual(self.client.put(f"{self.path}/9007199254740990", json={
            "class_id": 20, "name": "Missing", "is_active": True,
        }).status_code, 404)
        before = self.session.scalar(select(func.count()).select_from(SymbolLegendHistory))
        self.assertEqual(self.client.put(f"{self.path}/{first['id']}", json={
            "class_id": first["class_id"], "name": first["name"], "is_active": True,
        }).status_code, 200)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegendHistory)), before)

    def test_deactivation_updates_only_catalog_and_appends_history(self):
        record = self.create().json()
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.strip().casefold())

        event.listen(get_engine(), "before_cursor_execute", capture)
        try:
            response = self.client.put(f"{self.path}/{record['id']}", json={
                "class_id": record["class_id"], "name": record["name"], "is_active": False,
            })
        finally:
            event.remove(get_engine(), "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        mutations = [statement for statement in statements if statement.startswith(("update", "insert", "delete"))]
        self.assertTrue(any(statement.startswith("update symbol_legends") for statement in mutations))
        self.assertTrue(any(statement.startswith("insert into symbol_legend_history") for statement in mutations))
        self.assertFalse(any(statement.startswith("delete") for statement in mutations))
        protected_tables = ("detected_symbols", "detection_class_corrections", "manual_symbols", "layout_versions")
        self.assertFalse(any(any(table in statement for table in protected_tables) for statement in mutations))

    def test_private_fields_are_absent_and_failures_are_sanitized(self):
        response = self.create()
        for value in ("glyph", "path", "storage", "sha256", "reference_file"):
            self.assertNotIn(value, response.text.casefold())
        with patch(
            "app.repositories.symbol_legend_repository.add_and_flush",
            side_effect=SQLAlchemyError("SELECT password FROM C:\\private\\glyph.png"),
        ):
            failed = self.create(1002, "Failure")
        self.assertEqual(failed.status_code, 503)
        for value in ("password", "private", "glyph.png", "select"):
            self.assertNotIn(value, failed.text.casefold())

    def test_schema_and_openapi_contract(self):
        empty = self.client.get(self.path)
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json(), [])
        inspector = inspect(get_engine())
        self.assertEqual(set(inspector.get_table_names()), set(Base.metadata.tables))
        self.assertEqual(len(Base.metadata.tables), 22)
        table = SymbolLegendHistory.__table__
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_symbol_legend_history_sequence",
                "ck_symbol_legend_history_sequence",
                "ck_symbol_legend_history_action",
                "ck_symbol_legend_history_old_class_id",
                "ck_symbol_legend_history_new_class_id",
                "ck_symbol_legend_history_old_name",
                "ck_symbol_legend_history_new_name",
                "ck_symbol_legend_history_old_snapshot",
            },
        )
        operations = {
            (path, method)
            for path, definitions in self.app.openapi()["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 30)
        self.assertTrue({
            (self.path, "get"),
            (self.path, "post"),
            (self.path + "/{legend_id}", "put"),
        }.issubset(operations))


if __name__ == "__main__":
    unittest.main()
