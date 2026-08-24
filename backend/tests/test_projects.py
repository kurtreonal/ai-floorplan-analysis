import json
import unittest
from base64 import b64encode
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Project, Role, User


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "d1-automated-test-session-secret"


class ProjectCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        base_settings = get_settings()
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=base_settings.database_url,
            oauth_provider="synthetic",
            oauth_client_id="d1-client",
            oauth_client_secret="d1-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url=(
                "https://provider.invalid/.well-known/openid-configuration"
            ),
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )

        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(bind=cls.connection, expire_on_commit=False)
        cls.roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(cls.roles) != {"ADMIN", "DESIGNER"}:
            raise RuntimeError("The ADMIN and DESIGNER seed roles are required.")

        marker = uuid4().hex
        cls.admin = User(
            oauth_provider="d1-test",
            oauth_subject=f"admin-{marker}",
            email=f"admin-{marker}@example.test",
            display_name="D1 Admin",
            role_id=cls.roles["ADMIN"].id,
        )
        cls.designer = User(
            oauth_provider="d1-test",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="D1 Designer",
            role_id=cls.roles["DESIGNER"].id,
        )
        cls.database_session.add_all((cls.admin, cls.designer))
        cls.database_session.flush()

        cls.application = create_app(settings)

        def override_database():
            yield cls.database_session

        cls.application.dependency_overrides[get_db] = override_database
        cls.client = TestClient(cls.application)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.database_session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.client.cookies.clear()

    def _set_session(self, user: User) -> None:
        encoded = b64encode(json.dumps({"user_id": user.id}).encode("utf-8"))
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(
            SESSION_COOKIE,
            cookie,
            domain="testserver.local",
        )

    def _create_project(self, **overrides: object):
        self._set_session(self.designer)
        payload = {
            "name": f"D1 Project {uuid4().hex}",
            "client_name": "Juan Dela Cruz",
            "location": "Quezon City",
            **overrides,
        }
        return self.client.post("/api/projects", json=payload)

    def test_designer_receives_201(self) -> None:
        response = self._create_project()

        self.assertEqual(response.status_code, 201)

    def test_response_matches_declared_contract(self) -> None:
        response = self._create_project(name="  Three-Storey Residence  ")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "id",
                "owner_id",
                "name",
                "status",
                "client_name",
                "location",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(body["name"], "Three-Storey Residence")
        self.assertIsInstance(body["id"], int)
        self.assertIsInstance(body["created_at"], str)
        self.assertIsInstance(body["updated_at"], str)

    def test_created_project_defaults_to_draft(self) -> None:
        response = self._create_project()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")

    def test_created_project_is_persisted(self) -> None:
        response = self._create_project()
        project = self.database_session.get(Project, response.json()["id"])

        self.assertIsNotNone(project)
        self.assertEqual(project.name, response.json()["name"])

    def test_owner_is_authenticated_designer(self) -> None:
        response = self._create_project()
        project = self.database_session.get(Project, response.json()["id"])

        self.assertEqual(response.json()["owner_id"], self.designer.id)
        self.assertEqual(project.owner_id, self.designer.id)

    def test_omitted_owner_id_is_accepted(self) -> None:
        response = self._create_project()

        self.assertEqual(response.status_code, 201)

    def test_submitted_owner_id_is_rejected(self) -> None:
        response = self._create_project(owner_id=self.admin.id)

        self.assertEqual(response.status_code, 422)

    def test_server_controlled_fields_are_rejected(self) -> None:
        for field, value in (
            ("status", "archived"),
            ("id", 99),
            ("created_at", "2026-08-24T20:00:00"),
            ("updated_at", "2026-08-24T20:00:00"),
        ):
            with self.subTest(field=field):
                response = self._create_project(**{field: value})
                self.assertEqual(response.status_code, 422)

    def test_missing_name_is_rejected(self) -> None:
        self._set_session(self.designer)

        response = self.client.post("/api/projects", json={})

        self.assertEqual(response.status_code, 422)

    def test_empty_and_whitespace_names_are_rejected(self) -> None:
        for name in ("", "   "):
            with self.subTest(name=repr(name)):
                response = self._create_project(name=name)
                self.assertEqual(response.status_code, 422)

    def test_overlong_name_is_rejected(self) -> None:
        response = self._create_project(name="x" * 256)

        self.assertEqual(response.status_code, 422)

    def test_overlong_optional_fields_are_rejected(self) -> None:
        for field, value in (("client_name", "x" * 256), ("location", "x" * 501)):
            with self.subTest(field=field):
                response = self._create_project(**{field: value})
                self.assertEqual(response.status_code, 422)

    def test_unauthenticated_creation_returns_401(self) -> None:
        response = self.client.post("/api/projects", json={"name": "Denied"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHENTICATION_REQUIRED",
        )

    def test_admin_creation_returns_403(self) -> None:
        self._set_session(self.admin)

        response = self.client.post("/api/projects", json={"name": "Denied"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_database_failure_rolls_back_and_is_sanitized(self) -> None:
        self._set_session(self.designer)
        sensitive_detail = "mysql+pymysql://root:private@127.0.0.1/ved_electrical"

        with (
            patch(
                "app.api.routes.projects.create_project",
                side_effect=SQLAlchemyError(sensitive_detail),
            ),
            patch.object(self.database_session, "rollback") as rollback,
        ):
            response = self.client.post(
                "/api/projects",
                json={"name": "Database Failure"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "error": {
                        "code": "PROJECT_CREATION_FAILED",
                        "message": "The project could not be created.",
                        "details": {},
                    }
                }
            },
        )
        rollback.assert_called_once_with()
        self.assertNotIn(sensitive_detail, response.text)

    def test_existing_health_and_authentication_routes_remain_available(self) -> None:
        health = self.client.get("/health")
        self._set_session(self.designer)
        current_user = self.client.get("/api/auth/me")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(
            health.json(),
            {"status": "ok", "service": "VED Electrical Services API"},
        )
        self.assertEqual(current_user.status_code, 200)
        self.assertEqual(current_user.json()["id"], self.designer.id)

    def test_openapi_declares_only_post_with_project_schemas(self) -> None:
        schema = self.application.openapi()
        project_path = schema["paths"]["/api/projects"]
        operation = project_path["post"]

        self.assertEqual(set(project_path), {"post"})
        self.assertEqual(
            operation["requestBody"]["content"]["application/json"]["schema"][
                "$ref"
            ],
            "#/components/schemas/ProjectCreate",
        )
        self.assertEqual(
            operation["responses"]["201"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/ProjectResponse",
        )


if __name__ == "__main__":
    unittest.main()
