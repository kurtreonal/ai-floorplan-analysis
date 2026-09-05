import json
import unittest
import uuid
from base64 import b64encode
from datetime import datetime, timedelta
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
from app.models import Base, FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.services.processing_job_service import (
    FLOOR_PLAN_ANALYSIS_JOB_TYPE,
    SAFE_PROCESSING_STATUS_ERROR_MESSAGE,
)


SESSION_SECRET = "pre2-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"


class ProcessingJobHistoryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.marker = f"pre2-{uuid.uuid4().hex}"
        cls.database_session = Session(cls.engine, autoflush=False, expire_on_commit=False)
        cls.baseline_counts = cls._counts()
        roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(roles) != {"ADMIN", "DESIGNER"}:
            raise unittest.SkipTest("Seeded ADMIN and DESIGNER roles are required.")

        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            role=roles["DESIGNER"],
        )
        cls.other_designer = User(
            oauth_provider=cls.marker,
            oauth_subject="other-designer",
            role=roles["DESIGNER"],
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            role=roles["ADMIN"],
        )
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.project_floor = ProjectFloor(project=cls.project, name="Ground")
        cls.floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="owned.png",
            storage_path="originals/private-owned.png",
            mime_type="image/png",
            file_size=100,
        )
        cls.empty_floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="empty.png",
            storage_path="originals/private-empty.png",
            mime_type="image/png",
            file_size=101,
        )
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"{cls.marker}-other",
        )
        cls.other_floor = ProjectFloor(project=cls.other_project, name="Other")
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_floor,
            original_filename="other.png",
            storage_path="originals/private-other.png",
            mime_type="image/png",
            file_size=102,
        )
        cls.database_session.add_all((cls.admin, cls.floor_plan, cls.empty_floor_plan, cls.other_floor_plan))
        cls.database_session.flush()
        now = datetime(2026, 1, 2, 3, 4, 5)
        cls.older_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="completed",
            progress=100,
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=1),
        )
        cls.failed_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="failed",
            progress=44,
            error_message=r"password=hunter2 C:\private\model.pt SELECT Traceback",
            created_at=now,
            updated_at=now + timedelta(minutes=1),
        )
        cls.unrelated_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="unrelated_private_job",
            status="queued",
            progress=0,
            created_at=now + timedelta(minutes=2),
            updated_at=now + timedelta(minutes=2),
        )
        cls.other_job = ProcessingJob(
            floor_plan_id=cls.other_floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="processing",
            progress=20,
            created_at=now + timedelta(minutes=3),
            updated_at=now + timedelta(minutes=3),
        )
        cls.database_session.add_all(
            (cls.older_job, cls.failed_job, cls.unrelated_job, cls.other_job)
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
            oauth_client_id="pre2-client",
            oauth_client_secret="pre2-client-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url="https://provider.invalid/.well-known/openid-configuration",
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
                delete(ProcessingJob).where(
                    ProcessingJob.floor_plan_id.in_(
                        (cls.floor_plan.id, cls.empty_floor_plan.id, cls.other_floor_plan.id)
                    )
                )
            )
            session.execute(
                delete(FloorPlan).where(
                    FloorPlan.id.in_(
                        (cls.floor_plan.id, cls.empty_floor_plan.id, cls.other_floor_plan.id)
                    )
                )
            )
            session.execute(delete(ProjectFloor).where(ProjectFloor.id.in_((cls.project_floor.id, cls.other_floor.id))))
            session.execute(delete(Project).where(Project.id.in_((cls.project.id, cls.other_project.id))))
            session.execute(delete(User).where(User.oauth_provider == cls.marker))
            session.commit()
        finally:
            session.close()
        if cls._counts() != cls.baseline_counts:
            raise AssertionError("PRE2 database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()

    def _set_session(self, user: str) -> None:
        encoded = b64encode(json.dumps({"user_id": self.user_ids[user]}).encode())
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode()
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _get(self, *, user: str | None = "designer", floor_plan_id: int | None = None, query: str = ""):
        if user is not None:
            self._set_session(user)
        target = self.floor_plan.id if floor_plan_id is None else floor_plan_id
        return self.client.get(f"/api/floor-plans/{target}/processing-jobs{query}")

    def test_lists_only_analysis_jobs_newest_first_with_safe_fields(self) -> None:
        response = self._get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual([item["job_id"] for item in body], [self.failed_job.id, self.older_job.id])
        self.assertEqual(
            set(body[0]),
            {"job_id", "type", "status", "progress", "error_message", "created_at", "updated_at"},
        )
        self.assertEqual(body[0]["error_message"], SAFE_PROCESSING_STATUS_ERROR_MESSAGE)
        self.assertIsNone(body[1]["error_message"])
        for secret in ("hunter2", "private", "select", "traceback", "unrelated_private_job"):
            self.assertNotIn(secret, response.text.casefold())

    def test_admin_can_read_and_other_designer_cannot_discover_floor_plan(self) -> None:
        self.assertEqual(self._get(user="admin").status_code, 200)
        self.client.cookies.clear()
        denied = self._get(user="other")
        self.assertEqual(denied.status_code, 404, denied.text)
        self.assertEqual(denied.json()["detail"]["error"]["code"], "FLOOR_PLAN_NOT_FOUND")

    def test_missing_and_unauthenticated_requests_are_non_disclosing(self) -> None:
        self.assertEqual(self._get(floor_plan_id=9_000_000_002).status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self._get(user=None).status_code, 401)

    def test_empty_valid_history_returns_empty_array(self) -> None:
        response = self._get(floor_plan_id=self.empty_floor_plan.id)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [])

    def test_limit_is_bounded_and_validated(self) -> None:
        limited = self._get(query="?limit=1")
        self.assertEqual(limited.status_code, 200, limited.text)
        self.assertEqual([item["job_id"] for item in limited.json()], [self.failed_job.id])
        for value in ("0", "101", "invalid"):
            self.client.cookies.clear()
            self.assertEqual(self._get(query=f"?limit={value}").status_code, 422)

    def test_database_failure_is_sanitized_and_rolled_back(self) -> None:
        with patch(
            "app.api.routes.processing.list_accessible_processing_jobs",
            side_effect=SQLAlchemyError(r"SELECT password FROM C:\private Traceback"),
        ), patch.object(self.database_session, "rollback", wraps=self.database_session.rollback) as rollback:
            response = self._get()
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"]["error"]["code"], "PROCESSING_JOB_HISTORY_FAILED")
        rollback.assert_called_once()
        for secret in ("select", "password", "private", "traceback"):
            self.assertNotIn(secret, response.text.casefold())

    def test_listing_has_no_write_lock_or_file_side_effects(self) -> None:
        statements: list[str] = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with patch.object(self.database_session, "commit", side_effect=AssertionError("GET committed")), patch.object(
                self.database_session, "flush", side_effect=AssertionError("GET flushed")
            ), patch.object(Path, "open", side_effect=AssertionError("GET accessed filesystem")):
                response = self._get()
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(any("FOR UPDATE" in statement.upper() for statement in statements))
        self.assertEqual(sum("processing_jobs" in statement.casefold() for statement in statements), 1)

    def test_openapi_adds_exactly_one_bounded_get_operation(self) -> None:
        schema = self.application.openapi()
        path = schema["paths"]["/api/floor-plans/{floor_plan_id}/processing-jobs"]
        self.assertEqual(set(path), {"get"})
        limit = next(item for item in path["get"]["parameters"] if item["name"] == "limit")
        self.assertEqual(limit["schema"]["default"], 50)
        self.assertEqual(limit["schema"]["maximum"], 100)
        operations = {
            (method, route)
            for route, definitions in schema["paths"].items()
            for method in definitions
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 26)


if __name__ == "__main__":
    unittest.main()
