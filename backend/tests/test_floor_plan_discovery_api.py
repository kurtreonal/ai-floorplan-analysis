import json
import unittest
import uuid
from base64 import b64encode
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import Base, FloorPlan, Project, ProjectFloor, Role, User


SESSION_SECRET = "pre1-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


class FloorPlanDiscoveryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.marker = f"pre1-{uuid.uuid4().hex}"
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

        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            role=designer_role,
        )
        cls.other_designer = User(
            oauth_provider=cls.marker,
            oauth_subject="other-designer",
            role=designer_role,
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            role=admin_role,
        )
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.earlier_floor = ProjectFloor(
            project=cls.project,
            name="Earlier",
            sort_order=-1,
        )
        cls.later_floor = ProjectFloor(
            project=cls.project,
            name="Later",
            sort_order=2,
        )
        cls.empty_project = Project(
            owner=cls.designer,
            name=f"{cls.marker}-empty",
        )
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"{cls.marker}-other",
        )
        cls.other_floor = ProjectFloor(
            project=cls.other_project,
            name="Other",
            sort_order=0,
        )
        cls.database_session.add_all(
            (
                cls.earlier_floor,
                cls.later_floor,
                cls.empty_project,
                cls.other_floor,
                cls.admin,
            )
        )
        cls.database_session.flush()
        cls.later_first = FloorPlan(
            project_floor_id=cls.later_floor.id,
            original_filename="later-first.png",
            storage_path="originals/private-later-first.png",
            mime_type="image/png",
            file_size=101,
        )
        cls.earlier = FloorPlan(
            project_floor_id=cls.earlier_floor.id,
            original_filename="earlier.pdf",
            storage_path="originals/private-earlier.pdf",
            mime_type="application/pdf",
            file_size=202,
            processing_status="processed",
        )
        cls.later_second = FloorPlan(
            project_floor_id=cls.later_floor.id,
            original_filename="later-second.jpg",
            storage_path="originals/private-later-second.jpg",
            mime_type="image/jpeg",
            file_size=303,
        )
        cls.other_plan = FloorPlan(
            project_floor_id=cls.other_floor.id,
            original_filename="other.png",
            storage_path="originals/private-other.png",
            mime_type="image/png",
            file_size=404,
        )
        cls.database_session.add_all(
            (cls.later_first, cls.earlier, cls.later_second, cls.other_plan)
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
        }
        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="pre1-client",
            oauth_client_secret="pre1-client-secret",
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
            project_ids = (cls.project.id, cls.empty_project.id, cls.other_project.id)
            floor_ids = (cls.earlier_floor.id, cls.later_floor.id, cls.other_floor.id)
            session.execute(delete(FloorPlan).where(FloorPlan.project_floor_id.in_(floor_ids)))
            session.execute(delete(ProjectFloor).where(ProjectFloor.id.in_(floor_ids)))
            session.execute(delete(Project).where(Project.id.in_(project_ids)))
            session.execute(delete(User).where(User.oauth_provider == cls.marker))
            session.commit()
        finally:
            session.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("PRE1 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()

    def _set_session(self, user: str) -> None:
        encoded = b64encode(
            json.dumps({"user_id": self.user_ids[user]}).encode("utf-8")
        )
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _get(
        self,
        *,
        user: str | None = "designer",
        project_id: int | None = None,
        query: str = "",
    ):
        if user is not None:
            self._set_session(user)
        target_project_id = self.project.id if project_id is None else project_id
        return self.client.get(
            f"/api/projects/{target_project_id}/floor-plans{query}"
        )

    def test_designer_receives_safe_deterministically_ordered_metadata(self) -> None:
        response = self._get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(
            [item["id"] for item in body],
            [self.earlier.id, self.later_first.id, self.later_second.id],
        )
        self.assertEqual(
            set(body[0]),
            {
                "id",
                "project_floor_id",
                "original_filename",
                "mime_type",
                "file_size",
                "processing_status",
            },
        )
        self.assertNotIn("storage_path", response.text)
        self.assertNotIn("sha256", response.text.casefold())
        self.assertNotIn("private-", response.text)
        self.assertEqual(body[0]["processing_status"], "processed")

    def test_admin_can_read_and_other_designer_cannot_discover_project(self) -> None:
        admin_response = self._get(user="admin")
        self.assertEqual(admin_response.status_code, 200, admin_response.text)
        self.client.cookies.clear()
        denied = self._get(user="other")
        self.assertEqual(denied.status_code, 404, denied.text)
        self.assertEqual(
            denied.json()["detail"]["error"]["code"],
            "PROJECT_NOT_FOUND",
        )

    def test_missing_project_and_authentication_are_non_disclosing(self) -> None:
        missing = self._get(project_id=9_000_000_001)
        self.assertEqual(missing.status_code, 404, missing.text)
        self.client.cookies.clear()
        unauthenticated = self._get(user=None)
        self.assertEqual(unauthenticated.status_code, 401, unauthenticated.text)

    def test_floor_filter_returns_only_that_floor(self) -> None:
        response = self._get(query=f"?project_floor_id={self.later_floor.id}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["id"] for item in response.json()],
            [self.later_first.id, self.later_second.id],
        )

    def test_floor_filter_cannot_escape_project_and_is_validated(self) -> None:
        outside = self._get(query=f"?project_floor_id={self.other_floor.id}")
        self.assertEqual(outside.status_code, 404, outside.text)
        self.assertEqual(
            outside.json()["detail"]["error"]["code"],
            "PROJECT_FLOOR_NOT_FOUND",
        )
        self.client.cookies.clear()
        invalid = self._get(query="?project_floor_id=0")
        self.assertEqual(invalid.status_code, 422, invalid.text)

    def test_empty_project_returns_empty_array(self) -> None:
        response = self._get(project_id=self.empty_project.id)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

    def test_database_failure_is_sanitized_and_rolled_back(self) -> None:
        private = r"SELECT secret FROM C:\private Traceback password=hunter2"
        with patch(
            "app.api.routes.floor_plans.list_accessible_floor_plans",
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
            "FLOOR_PLAN_LIST_FAILED",
        )
        rollback.assert_called_once()
        for private_part in ("select", "private", "traceback", "hunter2"):
            self.assertNotIn(private_part, response.text.casefold())

    def test_retrieval_has_no_write_lock_or_file_side_effects(self) -> None:
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
            ), patch.object(
                Path,
                "open",
                side_effect=AssertionError("GET accessed the filesystem"),
            ):
                response = self._get()
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        floor_plan_queries = [
            statement
            for statement in statements
            if "floor_plans" in statement.casefold()
            and statement.lstrip().casefold().startswith("select")
        ]
        self.assertEqual(len(floor_plan_queries), 1)
        self.assertNotIn("FOR UPDATE", floor_plan_queries[0].upper())

    def test_openapi_adds_exactly_one_get_operation(self) -> None:
        schema = self.application.openapi()
        endpoint = schema["paths"]["/api/projects/{project_id}/floor-plans"]
        self.assertEqual(set(endpoint), {"get", "post"})
        operations = {
            (method, route)
            for route, definitions in schema["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 22)


if __name__ == "__main__":
    unittest.main()
