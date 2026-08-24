import json
import unittest
from base64 import b64encode
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import select
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Project, Role, User
from app.services.project_service import get_accessible_project


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
        cls.other_designer = User(
            oauth_provider="d2-test",
            oauth_subject=f"other-designer-{marker}",
            email=f"other-designer-{marker}@example.test",
            display_name="D2 Other Designer",
            role_id=cls.roles["DESIGNER"].id,
        )
        cls.empty_designer = User(
            oauth_provider="d2-test",
            oauth_subject=f"empty-designer-{marker}",
            email=f"empty-designer-{marker}@example.test",
            display_name="D2 Empty Designer",
            role_id=cls.roles["DESIGNER"].id,
        )
        cls.database_session.add_all(
            (cls.admin, cls.designer, cls.other_designer, cls.empty_designer)
        )
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

    def _set_session(self, user: User, **untrusted_values: object) -> None:
        payload = {"user_id": user.id, **untrusted_values}
        encoded = b64encode(json.dumps(payload).encode("utf-8"))
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

    def _add_project(
        self,
        owner: User,
        *,
        name: str | None = None,
        updated_at: datetime | None = None,
    ) -> Project:
        project = Project(
            owner_id=owner.id,
            name=name or f"D2 Project {uuid4().hex}",
            updated_at=updated_at or datetime.now().replace(microsecond=0),
        )
        self.database_session.add(project)
        self.database_session.flush()
        return project

    def test_list_designer_receives_200_and_owned_projects(self) -> None:
        owned = self._add_project(self.designer)
        self._set_session(self.designer)

        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertIn(owned.id, {project["id"] for project in response.json()})

    def test_list_designer_cannot_see_another_designer_projects(self) -> None:
        owned = self._add_project(self.designer)
        another = self._add_project(self.other_designer)
        self._set_session(self.designer)

        response = self.client.get("/api/projects")
        project_ids = {project["id"] for project in response.json()}

        self.assertIn(owned.id, project_ids)
        self.assertNotIn(another.id, project_ids)

    def test_list_uses_session_identity_and_ignores_owner_forgery(self) -> None:
        another = self._add_project(self.other_designer)
        self._set_session(
            self.designer,
            owner_id=self.other_designer.id,
            role="ADMIN",
        )

        response = self.client.get(
            f"/api/projects?owner_id={self.other_designer.id}",
            headers={"X-Owner-ID": str(self.other_designer.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(another.id, {project["id"] for project in response.json()})

    def test_list_admin_receives_200_and_projects_from_multiple_owners(self) -> None:
        first = self._add_project(self.designer)
        second = self._add_project(self.other_designer)
        self._set_session(self.admin)

        response = self.client.get("/api/projects")
        project_ids = {project["id"] for project in response.json()}

        self.assertEqual(response.status_code, 200)
        self.assertIn(first.id, project_ids)
        self.assertIn(second.id, project_ids)

    def test_list_results_match_response_contract(self) -> None:
        project = self._add_project(self.designer)
        self._set_session(self.designer)

        response = self.client.get("/api/projects")
        result = next(item for item in response.json() if item["id"] == project.id)

        self.assertEqual(
            set(result),
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
        self.assertEqual(result["status"], "draft")
        self.assertIsInstance(result["updated_at"], str)

    def test_list_results_use_deterministic_order(self) -> None:
        baseline = datetime(2026, 1, 1, 12, 0, 0)
        older = self._add_project(self.other_designer, updated_at=baseline)
        tied_first = self._add_project(
            self.other_designer,
            updated_at=baseline + timedelta(days=1),
        )
        tied_second = self._add_project(
            self.other_designer,
            updated_at=baseline + timedelta(days=1),
        )
        self._set_session(self.other_designer)

        response = self.client.get("/api/projects")
        relevant_ids = {older.id, tied_first.id, tied_second.id}
        ordered_ids = [
            project["id"]
            for project in response.json()
            if project["id"] in relevant_ids
        ]

        self.assertEqual(ordered_ids, [tied_second.id, tied_first.id, older.id])

    def test_list_designer_with_no_projects_receives_empty_list(self) -> None:
        self._set_session(self.empty_designer)

        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_admin_with_no_projects_receives_empty_list(self) -> None:
        self._set_session(self.admin)

        with patch(
            "app.api.routes.projects.list_accessible_projects",
            return_value=[],
        ):
            response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_unauthenticated_request_returns_401(self) -> None:
        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHENTICATION_REQUIRED",
        )

    def test_list_unsupported_role_returns_403(self) -> None:
        unsupported_user = SimpleNamespace(role=SimpleNamespace(name="VIEWER"))
        self.application.dependency_overrides[get_current_user] = (
            lambda: unsupported_user
        )
        try:
            response = self.client.get("/api/projects")
        finally:
            self.application.dependency_overrides.pop(get_current_user)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_list_database_failure_is_sanitized(self) -> None:
        self._set_session(self.designer)
        sensitive_detail = "mysql+pymysql://root:private@127.0.0.1/ved_electrical"

        with (
            patch(
                "app.api.routes.projects.list_accessible_projects",
                side_effect=SQLAlchemyError(sensitive_detail),
            ),
            patch.object(self.database_session, "rollback") as rollback,
        ):
            response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "error": {
                        "code": "PROJECT_LIST_FAILED",
                        "message": "Projects could not be loaded.",
                        "details": {},
                    }
                }
            },
        )
        rollback.assert_called_once_with()
        self.assertNotIn(sensitive_detail, response.text)

    def test_detail_designer_receives_own_project_metadata(self) -> None:
        project = self._add_project(self.designer, name="D3 Designer Project")
        project.client_name = "D3 Client"
        project.location = "D3 Location"
        self.database_session.flush()
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": project.id,
                "owner_id": self.designer.id,
                "name": "D3 Designer Project",
                "status": "draft",
                "client_name": "D3 Client",
                "location": "D3 Location",
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            },
        )

    def test_detail_response_excludes_unrelated_payloads(self) -> None:
        project = self._add_project(self.designer)
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{project.id}")
        excluded_fields = {
            "project_floors",
            "floor_plans",
            "uploads",
            "detections",
            "ai_results",
            "geometry",
            "routes",
            "estimates",
            "reports",
            "owner",
        }

        self.assertEqual(response.status_code, 200)
        self.assertTrue(excluded_fields.isdisjoint(response.json()))

    def test_detail_designer_cannot_retrieve_another_project(self) -> None:
        project = self._add_project(self.other_designer)
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "PROJECT_NOT_FOUND",
        )

    def test_detail_owner_query_forgery_does_not_grant_access(self) -> None:
        project = self._add_project(self.other_designer)
        self._set_session(self.designer)

        response = self.client.get(
            f"/api/projects/{project.id}?owner_id={self.other_designer.id}"
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_owner_header_forgery_does_not_grant_access(self) -> None:
        project = self._add_project(self.other_designer)
        self._set_session(self.designer)

        response = self.client.get(
            f"/api/projects/{project.id}",
            headers={
                "X-Owner-ID": str(self.other_designer.id),
                "X-Role": "ADMIN",
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_session_forgery_does_not_grant_access(self) -> None:
        project = self._add_project(self.other_designer)
        self._set_session(
            self.designer,
            owner_id=self.other_designer.id,
            role="ADMIN",
        )

        response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 404)

    def test_detail_admin_can_retrieve_designer_project(self) -> None:
        project = self._add_project(self.designer)
        self._set_session(self.admin)

        response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], project.id)
        self.assertEqual(response.json()["owner_id"], self.designer.id)

    def test_detail_unauthenticated_request_returns_401(self) -> None:
        project = self._add_project(self.designer)

        response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHENTICATION_REQUIRED",
        )

    def test_detail_unsupported_role_returns_403(self) -> None:
        project = self._add_project(self.designer)
        unsupported_user = SimpleNamespace(role=SimpleNamespace(name="VIEWER"))
        self.application.dependency_overrides[get_current_user] = (
            lambda: unsupported_user
        )
        try:
            response = self.client.get(f"/api/projects/{project.id}")
        finally:
            self.application.dependency_overrides.pop(get_current_user)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_detail_nonexistent_project_returns_sanitized_404(self) -> None:
        self._set_session(self.admin)

        response = self.client.get("/api/projects/9223372036854775807")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "error": {
                        "code": "PROJECT_NOT_FOUND",
                        "message": "The requested project was not found.",
                        "details": {},
                    }
                }
            },
        )

    def test_detail_invalid_project_ids_return_422(self) -> None:
        self._set_session(self.designer)

        for project_id in ("not-an-integer", "0", "-1"):
            with self.subTest(project_id=project_id):
                response = self.client.get(f"/api/projects/{project_id}")
                self.assertEqual(response.status_code, 422)

    def test_detail_database_failure_is_sanitized(self) -> None:
        project = self._add_project(self.designer)
        self._set_session(self.designer)
        sensitive_detail = "mysql+pymysql://root:private@127.0.0.1/ved_electrical"

        with (
            patch(
                "app.api.routes.projects.get_accessible_project",
                side_effect=SQLAlchemyError(sensitive_detail),
            ),
            patch.object(self.database_session, "rollback") as rollback,
        ):
            response = self.client.get(f"/api/projects/{project.id}")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail": {
                    "error": {
                        "code": "PROJECT_DETAIL_FAILED",
                        "message": "The project could not be loaded.",
                        "details": {},
                    }
                }
            },
        )
        rollback.assert_called_once_with()
        self.assertNotIn(sensitive_detail, response.text)

    def test_detail_lookup_does_not_modify_project(self) -> None:
        project = self._add_project(self.designer, name="D3 Unchanged Project")
        before = (
            project.owner_id,
            project.name,
            project.status,
            project.client_name,
            project.location,
            project.created_at,
            project.updated_at,
        )
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{project.id}")
        self.database_session.refresh(project)
        after = (
            project.owner_id,
            project.name,
            project.status,
            project.client_name,
            project.location,
            project.created_at,
            project.updated_at,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(after, before)

    def test_detail_lookup_keeps_relationships_unloaded(self) -> None:
        project = self._add_project(self.designer)

        found = get_accessible_project(
            self.database_session,
            current_user=self.designer,
            project_id=project.id,
        )

        self.assertTrue(
            {"owner", "project_floors"}.issubset(
                sqlalchemy_inspect(found).unloaded
            )
        )
        with self.assertRaises(InvalidRequestError):
            _ = found.owner

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

    def test_openapi_declares_collection_and_detail_operations(self) -> None:
        schema = self.application.openapi()
        project_path = schema["paths"]["/api/projects"]
        detail_path = schema["paths"]["/api/projects/{project_id}"]
        post_operation = project_path["post"]
        get_operation = project_path["get"]

        self.assertEqual(set(project_path), {"get", "post"})
        self.assertEqual(
            post_operation["requestBody"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/ProjectCreate",
        )
        self.assertEqual(
            post_operation["responses"]["201"]["content"]["application/json"][
                "schema"
            ]["$ref"],
            "#/components/schemas/ProjectResponse",
        )
        get_schema = get_operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(get_schema["type"], "array")
        self.assertEqual(
            get_schema["items"]["$ref"],
            "#/components/schemas/ProjectResponse",
        )
        self.assertEqual(set(detail_path), {"get"})
        self.assertEqual(
            detail_path["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["$ref"],
            "#/components/schemas/ProjectResponse",
        )
        project_paths = {
            path: set(operations)
            for path, operations in schema["paths"].items()
            if path.startswith("/api/projects")
        }
        self.assertEqual(
            project_paths,
            {
                "/api/projects": {"get", "post"},
                "/api/projects/{project_id}": {"get"},
            },
        )


if __name__ == "__main__":
    unittest.main()
