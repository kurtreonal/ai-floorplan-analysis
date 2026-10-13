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
    def test_pdf_import_includes_all_sources_without_weights_and_preserves_prior_decisions(self):
        names = tuple(f"Fixture [pdf-76f411c60b6d:p1:L{i:02d}]" for i in range(1, 41))
        original = self.create().json()
        before = self.session.scalar(select(func.count()).select_from(SymbolLegendHistory))
        with patch("app.ai.floor_plan_interpretation.multiclass_symbol_detector.verify_artifacts",
                   side_effect=AssertionError("Catalog must not load weights")), \
             patch("app.services.pdf_legend_catalog.approved_pdf_catalog_names", return_value=names):
            first = self.client.post(f"{self.path}/import-trained?catalog=approved-pdf")
            self.assertEqual(first.status_code, 200, first.text)
            rows = first.json()
            self.assertEqual([r["name"] for r in rows], list(names))
            self.assertEqual(len(rows), 40)
            self.assertEqual(len({r["class_id"] for r in rows}), 40)
            self.assertEqual(self.client.post(f"{self.path}/import-trained?catalog=approved-pdf").json(), rows)
            self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegendHistory)), before + 40)
            self.client.put(f"{self.path}/{rows[0]['id']}", json={
                "class_id": rows[0]["class_id"], "name": rows[0]["name"], "is_active": False})
            again = self.client.post(f"{self.path}/import-trained?catalog=approved-pdf").json()
            self.assertFalse(again[0]["is_active"])
        public_names = {r["name"] for r in self.client.get("/api/symbol-legends").json()}
        self.assertTrue(set(names[1:]).issubset(public_names))
        self.assertNotIn(names[0], public_names)
        self.assertIn(original["name"], public_names)

    def test_pdf_import_denies_wrong_authority_environment_and_changed_artifacts(self):
        from types import SimpleNamespace
        query = f"{self.path}/import-trained?catalog=approved-pdf"
        before = self.session.scalar(select(func.count()).select_from(SymbolLegend))
        self.app.dependency_overrides[get_current_user] = lambda: self.designer
        self.assertEqual(self.client.post(query).status_code, 403)
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.post(query).status_code, 401)
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        with patch("app.services.symbol_legend_service.get_settings", return_value=SimpleNamespace(app_env="production")):
            self.assertEqual(self.client.post(query).status_code, 403)
        with patch("app.services.pdf_legend_catalog.approved_pdf_catalog_names", side_effect=ValueError("hash changed")):
            self.assertEqual(self.client.post(query).status_code, 503)
        self.assertEqual(self.client.post(f"{self.path}/import-trained?catalog=arbitrary").status_code, 422)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegend)), before)

    def test_trained_import_keeps_all_drawing_identities_without_overwriting_or_reactivating(self):
        original = self.create().json()
        classes = {i: ("Reviewed downlight", f"sheet-{i + 1:02d}:L01") for i in range(56)}
        with patch("app.ai.floor_plan_interpretation.multiclass_symbol_detector.verify_artifacts", return_value=classes):
            first = self.client.post(f"{self.path}/import-trained")
            self.assertEqual(first.status_code, 200, first.text)
            entries = first.json()
            self.assertEqual(len(entries), 56)
            self.assertEqual(len({row["id"] for row in entries}), 56)
            self.assertEqual(len({row["class_id"] for row in entries}), 56)
            self.assertEqual(entries[0]["name"], "Reviewed downlight [sheet-01:L01]")
            self.assertTrue(all(row["class_id"] > original["class_id"] for row in entries))
            counts = self.session.scalar(select(func.count()).select_from(SymbolLegendHistory))
            second = self.client.post(f"{self.path}/import-trained")
            self.assertEqual(second.json(), entries)
            self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegendHistory)), counts)
            self.client.put(f"{self.path}/{entries[0]['id']}", json={
                "class_id": entries[0]["class_id"], "name": entries[0]["name"], "is_active": False})
            self.assertFalse(self.client.post(f"{self.path}/import-trained").json()[0]["is_active"])
        histories = tuple(self.session.scalars(select(SymbolLegendHistory).where(
            SymbolLegendHistory.symbol_legend_id.in_([row["id"] for row in entries]))))
        self.assertTrue(all(row.actor_user_id == self.admin.id for row in histories))
        self.assertIn(original, self.client.get(self.path).json())

    def test_trained_import_requires_admin_development_and_verified_artifacts(self):
        from types import SimpleNamespace
        from app.ai.floor_plan_interpretation.experimental_symbol_detector import ExperimentalDetectorUnavailable
        self.app.dependency_overrides[get_current_user] = lambda: self.designer
        self.assertEqual(self.client.post(f"{self.path}/import-trained").status_code, 403)
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.post(f"{self.path}/import-trained").status_code, 401)
        self.app.dependency_overrides[get_current_user] = lambda: self.admin
        before = self.session.scalar(select(func.count()).select_from(SymbolLegend))
        with patch("app.services.symbol_legend_service.get_settings", return_value=SimpleNamespace(app_env="production")):
            self.assertEqual(self.client.post(f"{self.path}/import-trained").status_code, 403)
        with patch("app.ai.floor_plan_interpretation.multiclass_symbol_detector.verify_artifacts",
                   side_effect=ExperimentalDetectorUnavailable("MULTICLASS_MODEL_INTEGRITY_FAILED")):
            response = self.client.post(f"{self.path}/import-trained")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"]["error"]["code"], "TRAINED_LEGENDS_UNAVAILABLE")
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegend)), before)

    def test_trained_import_rolls_back_partial_catalog_and_history_on_failure(self):
        before = self.session.scalar(select(func.count()).select_from(SymbolLegend))
        histories = self.session.scalar(select(func.count()).select_from(SymbolLegendHistory))
        from app.services import symbol_legend_service as service
        original = service._history
        calls = []
        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise SQLAlchemyError("synthetic write failure")
            return original(**kwargs)
        with patch("app.ai.floor_plan_interpretation.multiclass_symbol_detector.verify_artifacts",
                   return_value={i: ("Fixture", f"sheet-{i}:L1") for i in range(56)}), \
             patch.object(service, "_history", side_effect=fail_second):
            self.assertEqual(self.client.post(f"{self.path}/import-trained").status_code, 503)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegend)), before)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(SymbolLegendHistory)), histories)

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
        self.assertEqual(len(Base.metadata.tables), 34)
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
        self.assertEqual(len(operations), 49)  # Includes draft BOM CSV as well as material import.
        self.assertTrue({
            (self.path, "get"),
            (self.path, "post"),
            (self.path + "/{legend_id}", "put"),
            (self.path + "/import-trained", "post"),
        }.issubset(operations))


if __name__ == "__main__":
    unittest.main()
