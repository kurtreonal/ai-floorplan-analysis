import json
import unittest
from base64 import b64encode
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import FloorPlan, Project, ProjectFloor, Role, User


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "e3a-automated-test-session-secret"


class ProjectFloorApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(roles) != {"ADMIN", "DESIGNER"}:
            raise RuntimeError("The ADMIN and DESIGNER seed roles are required.")

        marker = uuid4().hex
        cls.designer = User(
            oauth_provider="e3a-test",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="E3A Designer",
            role_id=roles["DESIGNER"].id,
        )
        cls.other_designer = User(
            oauth_provider="e3a-test",
            oauth_subject=f"other-{marker}",
            email=f"other-{marker}@example.test",
            display_name="E3A Other Designer",
            role_id=roles["DESIGNER"].id,
        )
        cls.admin = User(
            oauth_provider="e3a-test",
            oauth_subject=f"admin-{marker}",
            email=f"admin-{marker}@example.test",
            display_name="E3A Admin",
            role_id=roles["ADMIN"].id,
        )
        cls.project = Project(owner=cls.designer, name=f"E3A Project {marker}")
        cls.empty_project = Project(
            owner=cls.designer,
            name=f"E3A Empty Project {marker}",
        )
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"E3A Other Project {marker}",
        )
        cls.database_session.add_all(
            (
                cls.project,
                cls.empty_project,
                cls.other_project,
                cls.admin,
            )
        )
        cls.database_session.flush()
        cls.database_session.commit()

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="e3a-client",
            oauth_client_secret="e3a-client-secret",
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

    def _create_floor(
        self,
        *,
        user: User | None = None,
        project_id: int | None = None,
        payload: dict[str, object] | None = None,
    ):
        if user is not None:
            self._set_session(user)
        return self.client.post(
            f"/api/projects/{project_id or self.project.id}/floors",
            json={"name": f"Floor {uuid4().hex}"} if payload is None else payload,
        )

    def _add_floor(
        self,
        *,
        project: Project | None = None,
        name: str | None = None,
        sort_order: int = 0,
    ) -> ProjectFloor:
        floor = ProjectFloor(
            project_id=(project or self.project).id,
            name=name or f"Floor {uuid4().hex}",
            sort_order=sort_order,
        )
        self.database_session.add(floor)
        self.database_session.flush()
        return floor

    def test_designer_creates_floor_for_owned_project_and_it_persists(self) -> None:
        response = self._create_floor(
            user=self.designer,
            payload={"name": "  Ground Floor  "},
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(
            set(response.json()),
            {"id", "project_id", "name", "sort_order"},
        )
        self.assertEqual(response.json()["project_id"], self.project.id)
        self.assertEqual(response.json()["name"], "Ground Floor")
        self.assertEqual(response.json()["sort_order"], 0)
        floor = self.database_session.get(ProjectFloor, response.json()["id"])
        self.assertIsNotNone(floor)
        self.assertEqual(floor.project_id, self.project.id)

    def test_invalid_names_return_422(self) -> None:
        for payload in ({}, {"name": ""}, {"name": "   "}, {"name": "x" * 101}):
            with self.subTest(payload=payload):
                response = self._create_floor(user=self.designer, payload=payload)
                self.assertEqual(response.status_code, 422, response.text)

    def test_unknown_and_server_controlled_fields_return_422(self) -> None:
        for field, value in (
            ("unknown", "value"),
            ("id", 999),
            ("project_id", self.other_project.id),
            ("sort_order", 99),
        ):
            with self.subTest(field=field):
                response = self._create_floor(
                    user=self.designer,
                    payload={"name": "Ground Floor", field: value},
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_designer_lists_owned_project_floors(self) -> None:
        floor = self._add_floor(name="Owned Floor")
        self._add_floor(project=self.other_project, name="Other Floor")
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{self.project.id}/floors")

        self.assertEqual(response.status_code, 200, response.text)
        by_id = {item["id"]: item for item in response.json()}
        self.assertIn(floor.id, by_id)
        self.assertEqual(
            by_id[floor.id],
            {
                "id": floor.id,
                "project_id": self.project.id,
                "name": "Owned Floor",
                "sort_order": 0,
            },
        )

    def test_empty_project_returns_empty_list(self) -> None:
        self._set_session(self.designer)

        response = self.client.get(
            f"/api/projects/{self.empty_project.id}/floors"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_list_order_is_sort_order_then_id_ascending(self) -> None:
        later_sort = self._add_floor(sort_order=2)
        tied_first = self._add_floor(sort_order=1)
        tied_second = self._add_floor(sort_order=1)
        relevant_ids = {later_sort.id, tied_first.id, tied_second.id}
        self._set_session(self.designer)

        response = self.client.get(f"/api/projects/{self.project.id}/floors")
        ordered_ids = [
            floor["id"]
            for floor in response.json()
            if floor["id"] in relevant_ids
        ]

        self.assertEqual(ordered_ids, [tied_first.id, tied_second.id, later_sort.id])

    def test_cross_owner_designer_list_and_create_return_404(self) -> None:
        self._set_session(self.designer)

        list_response = self.client.get(
            f"/api/projects/{self.other_project.id}/floors"
        )
        create_response = self.client.post(
            f"/api/projects/{self.other_project.id}/floors",
            json={"name": "Denied"},
        )

        for response in (list_response, create_response):
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(
                response.json()["detail"]["error"]["code"],
                "PROJECT_NOT_FOUND",
            )

    def test_admin_can_list_but_cannot_create_floors(self) -> None:
        floor = self._add_floor(name="Admin Visible")
        self._set_session(self.admin)

        list_response = self.client.get(
            f"/api/projects/{self.project.id}/floors"
        )
        create_response = self.client.post(
            f"/api/projects/{self.project.id}/floors",
            json={"name": "Denied"},
        )

        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertIn(floor.id, {item["id"] for item in list_response.json()})
        self.assertEqual(create_response.status_code, 403, create_response.text)
        self.assertEqual(
            create_response.json()["detail"]["error"]["code"],
            "AUTHORIZATION_DENIED",
        )

    def test_unauthenticated_list_and_create_return_401(self) -> None:
        list_response = self.client.get(f"/api/projects/{self.project.id}/floors")
        create_response = self._create_floor(payload={"name": "Denied"})

        for response in (list_response, create_response):
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(
                response.json()["detail"]["error"]["code"],
                "AUTHENTICATION_REQUIRED",
            )

    def test_unsupported_role_list_and_create_return_403(self) -> None:
        unsupported_user = SimpleNamespace(role=SimpleNamespace(name="VIEWER"))
        self.application.dependency_overrides[get_current_user] = (
            lambda: unsupported_user
        )
        try:
            list_response = self.client.get(
                f"/api/projects/{self.project.id}/floors"
            )
            create_response = self.client.post(
                f"/api/projects/{self.project.id}/floors",
                json={"name": "Denied"},
            )
        finally:
            self.application.dependency_overrides.pop(get_current_user)

        for response in (list_response, create_response):
            self.assertEqual(response.status_code, 403, response.text)
            self.assertEqual(
                response.json()["detail"]["error"]["code"],
                "AUTHORIZATION_DENIED",
            )

    def test_missing_project_list_and_create_return_sanitized_404(self) -> None:
        missing_id = 9223372036854775807
        self._set_session(self.designer)

        list_response = self.client.get(f"/api/projects/{missing_id}/floors")
        create_response = self.client.post(
            f"/api/projects/{missing_id}/floors",
            json={"name": "Missing"},
        )

        for response in (list_response, create_response):
            self.assertEqual(response.status_code, 404, response.text)
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

    def test_database_failures_return_sanitized_503(self) -> None:
        sensitive = "mysql+pymysql://root:private@127.0.0.1/ved_electrical"
        self._set_session(self.designer)

        with (
            patch(
                "app.api.routes.project_floors.list_accessible_project_floors",
                side_effect=SQLAlchemyError(sensitive),
            ),
            patch.object(self.database_session, "rollback") as list_rollback,
        ):
            list_response = self.client.get(
                f"/api/projects/{self.project.id}/floors"
            )

        with (
            patch(
                "app.api.routes.project_floors.create_project_floor",
                side_effect=SQLAlchemyError(sensitive),
            ),
            patch.object(self.database_session, "rollback") as create_rollback,
        ):
            create_response = self.client.post(
                f"/api/projects/{self.project.id}/floors",
                json={"name": "Database Failure"},
            )

        self.assertEqual(list_response.status_code, 503, list_response.text)
        self.assertEqual(create_response.status_code, 503, create_response.text)
        self.assertEqual(
            list_response.json()["detail"]["error"]["code"],
            "PROJECT_FLOOR_LIST_FAILED",
        )
        self.assertEqual(
            create_response.json()["detail"]["error"]["code"],
            "PROJECT_FLOOR_CREATION_FAILED",
        )
        self.assertNotIn(sensitive, list_response.text)
        self.assertNotIn(sensitive, create_response.text)
        list_rollback.assert_called_once_with()
        create_rollback.assert_called_once_with()

    def test_floor_creation_does_not_create_floor_plan_or_trigger_upload(self) -> None:
        before = self.database_session.scalar(
            select(func.count()).select_from(FloorPlan)
        )

        with patch("app.api.routes.floor_plans.upload_floor_plan") as upload:
            response = self._create_floor(
                user=self.designer,
                payload={"name": "No Upload"},
            )

        after = self.database_session.scalar(
            select(func.count()).select_from(FloorPlan)
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(after, before)
        upload.assert_not_called()

    def test_openapi_exposes_floor_collection_and_existing_upload(self) -> None:
        paths = self.application.openapi()["paths"]
        floor_collection = paths["/api/projects/{project_id}/floors"]

        self.assertEqual(set(floor_collection), {"get", "post"})
        self.assertEqual(
            floor_collection["post"]["requestBody"]["content"][
                "application/json"
            ]["schema"]["$ref"],
            "#/components/schemas/ProjectFloorCreate",
        )
        self.assertEqual(
            floor_collection["post"]["responses"]["201"]["content"][
                "application/json"
            ]["schema"]["$ref"],
            "#/components/schemas/ProjectFloorResponse",
        )
        self.assertIn("post", paths["/api/projects/{project_id}/floor-plans"])


if __name__ == "__main__":
    unittest.main()
