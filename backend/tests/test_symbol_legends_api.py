import json
import unittest
import uuid
from base64 import b64encode
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, event, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Base, Role, SymbolLegend, User


SESSION_SECRET = "j3a-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


class SymbolLegendModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(bind=cls.engine, tables=[SymbolLegend.__table__])

    def test_exact_symbol_legend_model_contract(self) -> None:
        table = SymbolLegend.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            ("id", "class_id", "name", "is_active", "created_at", "updated_at"),
        )
        self.assertEqual(
            {constraint.name for constraint in table.constraints if constraint.name},
            {
                "uq_symbol_legends_class_id",
                "uq_symbol_legends_name",
                "ck_symbol_legends_class_id",
                "ck_symbol_legends_name",
            },
        )
        self.assertEqual(
            {index.name for index in table.indexes},
            {"ix_symbol_legends_active_class_order"},
        )
        self.assertEqual(tuple(table.foreign_keys), ())
        self.assertEqual(table.c.name.type.length, 255)
        self.assertEqual(table.c.name.type.collation, "utf8mb4_bin")
        self.assertFalse(table.c.class_id.nullable)
        self.assertFalse(table.c.name.nullable)
        self.assertFalse(table.c.is_active.nullable)

    def test_model_registration_and_live_schema_match_exactly(self) -> None:
        expected = {
            "detected_symbols",
            "detection_class_corrections",
            "detection_reviews",
            "floor_plans",
            "manual_symbols",
            "processing_jobs",
            "project_floors",
            "projects",
            "roles",
            "symbol_legends",
            "users",
            "walls",
        }
        self.assertEqual(set(Base.metadata.tables), expected)
        self.assertEqual(set(inspect(self.engine).get_table_names()), expected)
        self.assertEqual(len(Base.metadata.tables), 12)


class SymbolLegendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        Base.metadata.create_all(bind=cls.engine, tables=[SymbolLegend.__table__])
        cls.marker = f"j3a-{uuid.uuid4().hex}"
        cls.database_session = Session(
            cls.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        cls.baseline_counts = cls._counts()
        designer_role = cls.database_session.scalar(
            select(Role).where(Role.name == "DESIGNER")
        )
        admin_role = cls.database_session.scalar(
            select(Role).where(Role.name == "ADMIN")
        )
        if designer_role is None or admin_role is None:
            raise unittest.SkipTest("Seeded ADMIN and DESIGNER roles are required.")
        cls.unsupported_role = Role(name=f"J3A_{uuid.uuid4().hex[:19].upper()}")
        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            role=designer_role,
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            role=admin_role,
        )
        cls.unsupported = User(
            oauth_provider=cls.marker,
            oauth_subject="unsupported",
            role=cls.unsupported_role,
        )
        cls.active_later = SymbolLegend(
            class_id=20,
            name=f"{cls.marker}-test-class-2",
            is_active=True,
        )
        cls.active_first = SymbolLegend(
            class_id=10,
            name=f"{cls.marker}-test-class-1",
            is_active=True,
        )
        cls.inactive = SymbolLegend(
            class_id=5,
            name=f"{cls.marker}-inactive",
            is_active=False,
        )
        cls.database_session.add_all(
            (
                cls.designer,
                cls.admin,
                cls.unsupported,
                cls.active_later,
                cls.active_first,
                cls.inactive,
            )
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported.id,
        }
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="j3a-client",
            oauth_client_secret="j3a-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.application = create_app(settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.application)

    @classmethod
    def _counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        session = cls.database_session
        try:
            session.rollback()
            session.execute(
                delete(SymbolLegend).where(SymbolLegend.name.like(f"{cls.marker}%"))
            )
            session.execute(delete(User).where(User.oauth_provider == cls.marker))
            session.execute(delete(Role).where(Role.id == cls.unsupported_role.id))
            session.commit()
        finally:
            session.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("J3A database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()
        for legend in (self.active_later, self.active_first, self.inactive):
            self.database_session.refresh(legend)
        self.active_later.is_active = True
        self.active_first.is_active = True
        self.inactive.is_active = False
        self.database_session.commit()

    def _set_session(self, user_id: int) -> None:
        encoded = b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _get(self, user: str | None = "designer"):
        if user is not None:
            self._set_session(self.user_ids[user])
        return self.client.get("/api/symbol-legends")

    def test_active_only_deterministic_retrieval_for_designer_and_admin(self) -> None:
        expected = [
            {
                "id": self.active_first.id,
                "class_id": 10,
                "name": self.active_first.name,
            },
            {
                "id": self.active_later.id,
                "class_id": 20,
                "name": self.active_later.name,
            },
        ]
        designer = self._get("designer")
        self.assertEqual(designer.status_code, 200, designer.text)
        self.assertEqual(designer.json(), expected)
        self.client.cookies.clear()
        admin = self._get("admin")
        self.assertEqual(admin.status_code, 200, admin.text)
        self.assertEqual(admin.json(), expected)
        self.assertNotIn(self.inactive.name, admin.text)

    def test_empty_catalog_returns_200_with_empty_array(self) -> None:
        self.active_first.is_active = False
        self.active_later.is_active = False
        self.database_session.commit()
        response = self._get()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

    def test_unauthenticated_and_unsupported_roles_are_rejected(self) -> None:
        self.assertEqual(self._get(None).status_code, 401)
        self.client.cookies.clear()
        self.assertEqual(self._get("unsupported").status_code, 403)

    def test_database_constraints_reject_duplicates_and_invalid_values(self) -> None:
        invalid = (
            SymbolLegend(
                class_id=self.active_first.class_id,
                name=f"{self.marker}-duplicate-id",
                is_active=True,
            ),
            SymbolLegend(
                class_id=30,
                name=self.active_first.name,
                is_active=True,
            ),
            SymbolLegend(
                class_id=-1,
                name=f"{self.marker}-negative",
                is_active=True,
            ),
        )
        for legend in invalid:
            with self.subTest(class_id=legend.class_id, name=legend.name[:30]):
                self.database_session.add(legend)
                with self.assertRaises(SQLAlchemyError):
                    self.database_session.commit()
                self.database_session.rollback()

        for name in ("", " not-normalized ", "x" * 256, "null\x00name"):
            with self.subTest(invalid_name=name[:30]):
                with self.assertRaises(ValueError):
                    SymbolLegend(class_id=40, name=name, is_active=True)

    def test_database_failure_is_sanitized_and_rolled_back(self) -> None:
        private = r"SELECT secret FROM C:\private Traceback password=hunter2"
        with patch(
            "app.services.symbol_legend_service.list_active_symbol_legends",
            side_effect=SQLAlchemyError(private),
        ), patch.object(
            self.database_session,
            "rollback",
            wraps=self.database_session.rollback,
        ) as rollback:
            response = self._get()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "SYMBOL_LEGENDS_RETRIEVAL_FAILED",
        )
        rollback.assert_called_once()
        for private_part in ("select", "private", "traceback", "hunter2"):
            self.assertNotIn(private_part, response.text.casefold())

    def test_retrieval_has_no_mutation_lock_model_or_file_side_effects(self) -> None:
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with patch.object(
                self.database_session,
                "commit",
                side_effect=AssertionError("GET committed"),
            ), patch.object(
                self.database_session,
                "flush",
                side_effect=AssertionError("GET flushed"),
            ), patch(
                "app.ai.symbol_detection.model_loader.load_symbol_detection_model",
                side_effect=AssertionError("GET loaded YOLO"),
            ), patch.object(
                Path,
                "open",
                side_effect=AssertionError("GET accessed the filesystem"),
            ):
                response = self._get()
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        legend_queries = [
            statement
            for statement in statements
            if "symbol_legends" in statement.casefold()
            and statement.lstrip().casefold().startswith("select")
        ]
        self.assertEqual(len(legend_queries), 1)
        self.assertNotIn("FOR UPDATE", legend_queries[0].upper())

    def test_openapi_adds_exactly_one_read_only_operation(self) -> None:
        schema = self.application.openapi()
        path = schema["paths"]["/api/symbol-legends"]
        self.assertEqual(set(path), {"get"})
        response_schema = path["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(response_schema["type"], "array")
        operations = {
            (method, route)
            for route, definitions in schema["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 19)


if __name__ == "__main__":
    unittest.main()
