import hashlib
import json
import unittest
from base64 import b64encode
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.repositories.processing_job_repository import (
    find_processing_job_by_id_and_owner,
)
from app.services.processing_job_service import (
    FLOOR_PLAN_ANALYSIS_JOB_TYPE,
    SAFE_PROCESSING_STATUS_ERROR_MESSAGE,
)


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "f3-automated-test-session-secret"
STATUS_PATH = "/api/processing-jobs/{job_id}"
DETECTION_PATH = "/api/floor-plans/{floor_plan_id}/detections"
REVIEW_IMAGE_PATH = "/api/floor-plans/{floor_plan_id}/review-image"
DETECTION_REVIEW_PATH = (
    "/api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/review"
)
F2_OPERATIONS = {
    ("get", "/health"),
    ("get", "/api/auth/me"),
    ("post", "/api/auth/logout"),
    ("get", "/api/auth/login"),
    ("get", "/api/auth/callback"),
    ("get", "/api/projects"),
    ("post", "/api/projects"),
    ("get", "/api/projects/{project_id}"),
    ("get", "/api/projects/{project_id}/floors"),
    ("post", "/api/projects/{project_id}/floors"),
    ("post", "/api/projects/{project_id}/floor-plans"),
    ("post", "/api/floor-plans/{floor_plan_id}/process"),
}


class ProcessingJobStatusApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        with Session(cls.engine) as baseline_session:
            cls.preexisting_floor_plans = tuple(
                baseline_session.execute(
                    select(
                        FloorPlan.id,
                        FloorPlan.project_floor_id,
                        FloorPlan.original_filename,
                        FloorPlan.storage_path,
                        FloorPlan.mime_type,
                        FloorPlan.file_size,
                        FloorPlan.processing_status,
                    ).order_by(FloorPlan.id)
                ).all()
            )
            cls.preexisting_jobs = tuple(
                baseline_session.execute(
                    select(
                        ProcessingJob.id,
                        ProcessingJob.floor_plan_id,
                        ProcessingJob.job_type,
                        ProcessingJob.status,
                        ProcessingJob.progress,
                        ProcessingJob.error_message,
                        ProcessingJob.created_at,
                        ProcessingJob.updated_at,
                    ).order_by(ProcessingJob.id)
                ).all()
            )

        cls.marker = uuid4().hex
        cls.database_session = Session(cls.engine, expire_on_commit=False)
        roles = {
            role.name: role
            for role in cls.database_session.scalars(
                select(Role).where(Role.name.in_(("ADMIN", "DESIGNER")))
            )
        }
        if set(roles) != {"ADMIN", "DESIGNER"}:
            raise RuntimeError("The ADMIN and DESIGNER seed roles are required.")

        cls.unsupported_role = Role(name=f"F3_TEST_{cls.marker[:8].upper()}")
        cls.designer = User(
            oauth_provider="f3-test",
            oauth_subject=f"designer-{cls.marker}",
            role=roles["DESIGNER"],
        )
        cls.other_designer = User(
            oauth_provider="f3-test",
            oauth_subject=f"other-{cls.marker}",
            role=roles["DESIGNER"],
        )
        cls.admin = User(
            oauth_provider="f3-test",
            oauth_subject=f"admin-{cls.marker}",
            role=roles["ADMIN"],
        )
        cls.unsupported_user = User(
            oauth_provider="f3-test",
            oauth_subject=f"unsupported-{cls.marker}",
            role=cls.unsupported_role,
        )
        cls.project = Project(owner=cls.designer, name=f"F3 Project {cls.marker}")
        cls.project_floor = ProjectFloor(project=cls.project, name="Ground Floor")
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"F3 Other Project {cls.marker}",
        )
        cls.other_project_floor = ProjectFloor(
            project=cls.other_project,
            name="Other Floor",
        )

        cls.storage_root = TemporaryDirectory()
        cls.original_path = Path(cls.storage_root.name) / "original.png"
        cls.original_bytes = b"f3-original-floor-plan-bytes"
        cls.original_path.write_bytes(cls.original_bytes)
        cls.original_digest = hashlib.sha256(cls.original_bytes).hexdigest()
        cls.floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="original.png",
            storage_path=str(cls.original_path),
            mime_type="image/png",
            file_size=len(cls.original_bytes),
            processing_status="uploaded",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_project_floor,
            original_filename="other.png",
            storage_path="originals/other.png",
            mime_type="image/png",
            file_size=12,
            processing_status="uploaded",
        )
        cls.database_session.add_all(
            (
                cls.floor_plan,
                cls.other_floor_plan,
                cls.admin,
                cls.unsupported_user,
            )
        )
        cls.database_session.flush()
        cls.owned_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="queued",
            progress=0,
        )
        cls.failed_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="failed",
            progress=64,
            error_message=(
                "password=hunter2 C:\\private\\model.pt "
                "SELECT * FROM users Traceback"
            ),
        )
        cls.other_job = ProcessingJob(
            floor_plan_id=cls.other_floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            status="processing",
            progress=37,
        )
        cls.database_session.add_all(
            (cls.owned_job, cls.failed_job, cls.other_job)
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported_user.id,
        }
        cls.floor_plan_ids = (cls.floor_plan.id, cls.other_floor_plan.id)
        cls.job_ids = (cls.owned_job.id, cls.failed_job.id, cls.other_job.id)

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="f3-client",
            oauth_client_secret="f3-client-secret",
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
        try:
            cls.database_session.rollback()
            cls.database_session.execute(
                delete(ProcessingJob).where(ProcessingJob.id.in_(cls.job_ids))
            )
            cls.database_session.execute(
                delete(FloorPlan).where(FloorPlan.id.in_(cls.floor_plan_ids))
            )
            cls.database_session.execute(
                delete(ProjectFloor).where(
                    ProjectFloor.project_id.in_(
                        (cls.project.id, cls.other_project.id)
                    )
                )
            )
            cls.database_session.execute(
                delete(Project).where(
                    Project.id.in_((cls.project.id, cls.other_project.id))
                )
            )
            cls.database_session.execute(
                delete(User).where(User.oauth_provider == "f3-test")
            )
            cls.database_session.execute(
                delete(Role).where(Role.id == cls.unsupported_role.id)
            )
            cls.database_session.commit()
        finally:
            cls.database_session.close()

        try:
            if hashlib.sha256(cls.original_path.read_bytes()).hexdigest() != cls.original_digest:
                raise AssertionError("The F3 original test file was modified.")
        finally:
            cls.storage_root.cleanup()

        with Session(cls.engine) as verification_session:
            current_floor_plans = tuple(
                verification_session.execute(
                    select(
                        FloorPlan.id,
                        FloorPlan.project_floor_id,
                        FloorPlan.original_filename,
                        FloorPlan.storage_path,
                        FloorPlan.mime_type,
                        FloorPlan.file_size,
                        FloorPlan.processing_status,
                    ).order_by(FloorPlan.id)
                ).all()
            )
            current_jobs = tuple(
                verification_session.execute(
                    select(
                        ProcessingJob.id,
                        ProcessingJob.floor_plan_id,
                        ProcessingJob.job_type,
                        ProcessingJob.status,
                        ProcessingJob.progress,
                        ProcessingJob.error_message,
                        ProcessingJob.created_at,
                        ProcessingJob.updated_at,
                    ).order_by(ProcessingJob.id)
                ).all()
            )
            remaining_users = verification_session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.oauth_provider == "f3-test")
            )

        if remaining_users != 0:
            raise AssertionError("F3 test users were not cleaned up.")
        if current_floor_plans != cls.preexisting_floor_plans:
            raise AssertionError("Pre-existing floor-plan records changed.")
        if current_jobs != cls.preexisting_jobs:
            raise AssertionError("Pre-existing processing-job records changed.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()

    def _set_session(self, user_id: int, **untrusted: object) -> None:
        encoded = b64encode(
            json.dumps({"user_id": user_id, **untrusted}).encode("utf-8")
        )
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(
            SESSION_COOKIE,
            cookie,
            domain="testserver.local",
        )

    def _get(
        self,
        job_id: int | str,
        *,
        user_id: int | None = None,
        query: str = "",
        headers: dict[str, str] | None = None,
    ):
        if user_id is not None:
            self._set_session(user_id)
        return self.client.get(
            f"/api/processing-jobs/{job_id}{query}",
            headers=headers,
        )

    def test_owning_designer_reads_exact_status_contract(self) -> None:
        response = self._get(
            self.owned_job.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "job_id": self.owned_job.id,
                "type": FLOOR_PLAN_ANALYSIS_JOB_TYPE,
                "status": "queued",
                "progress": 0,
                "error_message": None,
            },
        )

    def test_admin_reads_any_project_job(self) -> None:
        response = self._get(
            self.other_job.id,
            user_id=self.user_ids["admin"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["job_id"], self.other_job.id)
        self.assertEqual(response.json()["status"], "processing")
        self.assertEqual(response.json()["progress"], 37)

    def test_cross_owner_and_missing_jobs_share_sanitized_404(self) -> None:
        responses = (
            self._get(
                self.other_job.id,
                user_id=self.user_ids["designer"],
            ),
            self._get(
                9223372036854775807,
                user_id=self.user_ids["designer"],
            ),
        )
        expected = {
            "detail": {
                "error": {
                    "code": "PROCESSING_JOB_NOT_FOUND",
                    "message": "The requested processing job was not found.",
                    "details": {},
                }
            }
        }
        for response in responses:
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(response.json(), expected)

    def test_unauthenticated_and_unsupported_roles_are_denied(self) -> None:
        unauthenticated = self._get(self.owned_job.id)
        self.assertEqual(unauthenticated.status_code, 401)
        unsupported = self._get(
            self.owned_job.id,
            user_id=self.user_ids["unsupported"],
        )
        self.assertEqual(unsupported.status_code, 403, unsupported.text)

    def test_invalid_and_missing_path_ids_are_rejected(self) -> None:
        self._set_session(self.user_ids["designer"])
        self.assertEqual(self.client.get("/api/processing-jobs").status_code, 404)
        for value in ("not-an-integer", 0, -1):
            with self.subTest(value=value):
                response = self._get(
                    value,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 422, response.text)

    def test_failed_job_returns_generic_error_and_never_raw_storage(self) -> None:
        response = self._get(
            self.failed_job.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["error_message"],
            SAFE_PROCESSING_STATUS_ERROR_MESSAGE,
        )
        response_text = response.text.casefold()
        for forbidden in (
            "hunter2",
            "private",
            "model.pt",
            "select",
            "users",
            "traceback",
        ):
            self.assertNotIn(forbidden, response_text)

    def test_polling_is_read_only_and_preserves_original(self) -> None:
        before_job = (
            self.owned_job.floor_plan_id,
            self.owned_job.job_type,
            self.owned_job.status,
            self.owned_job.progress,
            self.owned_job.error_message,
        )
        before_floor_plan = (
            self.floor_plan.original_filename,
            self.floor_plan.storage_path,
            self.floor_plan.mime_type,
            self.floor_plan.file_size,
            self.floor_plan.processing_status,
        )
        for _ in range(3):
            response = self._get(
                self.owned_job.id,
                user_id=self.user_ids["designer"],
            )
            self.assertEqual(response.status_code, 200, response.text)

        self.database_session.refresh(self.owned_job)
        self.database_session.refresh(self.floor_plan)
        self.assertEqual(
            (
                self.owned_job.floor_plan_id,
                self.owned_job.job_type,
                self.owned_job.status,
                self.owned_job.progress,
                self.owned_job.error_message,
            ),
            before_job,
        )
        self.assertEqual(
            (
                self.floor_plan.original_filename,
                self.floor_plan.storage_path,
                self.floor_plan.mime_type,
                self.floor_plan.file_size,
                self.floor_plan.processing_status,
            ),
            before_floor_plan,
        )
        self.assertEqual(
            hashlib.sha256(self.original_path.read_bytes()).hexdigest(),
            self.original_digest,
        )

    def test_owner_query_is_relationship_free_and_has_no_row_lock(self) -> None:
        mock_session = Mock(spec=Session)
        mock_session.scalar.return_value = self.owned_job
        result = find_processing_job_by_id_and_owner(
            mock_session,
            job_id=self.owned_job.id,
            owner_id=self.designer.id,
        )
        self.assertIs(result, self.owned_job)
        statement = mock_session.scalar.call_args.args[0]
        compiled = str(
            statement.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.assertNotIn("FOR UPDATE", compiled.upper())
        self.assertIn("projects.owner_id", compiled)
        self.assertNotIn("users", compiled)

        with Session(self.engine) as isolated_session:
            loaded = find_processing_job_by_id_and_owner(
                isolated_session,
                job_id=self.owned_job.id,
                owner_id=self.designer.id,
            )
            self.assertIsNotNone(loaded)
            with self.assertRaises(InvalidRequestError):
                _ = loaded.floor_plan

    def test_database_failure_is_sanitized(self) -> None:
        raw_error = "password=hunter2 SELECT users C:\\private\\db.sql Traceback"
        with (
            patch(
                "app.services.processing_job_service.find_processing_job_by_id",
                side_effect=SQLAlchemyError(raw_error),
            ),
            patch.object(
                self.database_session,
                "rollback",
                wraps=self.database_session.rollback,
            ) as rollback,
        ):
            response = self._get(
                self.owned_job.id,
                user_id=self.user_ids["admin"],
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "PROCESSING_JOB_STATUS_FAILED",
        )
        rollback.assert_called()
        response_text = response.text.casefold()
        for forbidden in ("hunter2", "select", "users", "private", "traceback"):
            self.assertNotIn(forbidden, response_text)

    def test_untrusted_identity_inputs_do_not_change_job_access(self) -> None:
        self._set_session(
            self.user_ids["designer"],
            owner_id=self.user_ids["other"],
            role="ADMIN",
        )
        response = self.client.get(
            f"/api/processing-jobs/{self.other_job.id}"
            f"?owner_id={self.user_ids['designer']}",
            headers={"X-Owner-Id": str(self.user_ids["designer"])},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_openapi_adds_only_the_f3_get_operation(self) -> None:
        schema = self.application.openapi()
        path = schema["paths"][STATUS_PATH]
        self.assertEqual(set(path), {"get"})
        response_schema = path["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            response_schema["$ref"],
            "#/components/schemas/ProcessingJobStatusResponse",
        )
        operations = {
            (method, route)
            for route, definition in schema["paths"].items()
            for method in definition
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(
            operations,
            F2_OPERATIONS
            | {
                ("get", STATUS_PATH),
                ("get", DETECTION_PATH),
                ("get", REVIEW_IMAGE_PATH),
                ("put", DETECTION_REVIEW_PATH),
                ("get", "/api/symbol-legends"),
                ("put", "/api/floor-plans/{floor_plan_id}/detections/{detected_symbol_id}/classification"),
                ("post", "/api/floor-plans/{floor_plan_id}/manual-symbols"),
                ("get", "/api/projects/{project_id}/floors/{project_floor_id}/layouts"),
                ("post", "/api/projects/{project_id}/floors/{project_floor_id}/layouts"),
                ("get", "/api/projects/{project_id}/floor-plans"),
                ("get", "/api/floor-plans/{floor_plan_id}/processing-jobs"),
                ("get", "/api/projects/{project_id}/floors/{floor_id}/analysis-settings"),
                ("put", "/api/projects/{project_id}/floors/{floor_id}/analysis-settings/elevation"),
                ("put", "/api/projects/{project_id}/floors/{floor_id}/analysis-settings/pages/{page_id}/scale"),
                ("get", "/api/admin/symbol-legends"),
                ("post", "/api/admin/symbol-legends"),
                ("put", "/api/admin/symbol-legends/{legend_id}"),
                ("post", "/api/processing-jobs/{job_id}/cancel"),
                ("get", "/api/dataset-approver-assignment"),
                ("get", "/api/admin/dataset-approver-assignments"),
                ("post", "/api/admin/dataset-approver-assignments"),
                ("post", "/api/admin/dataset-approver-assignments/{assignment_id}/deactivate"),
                ("get", "/api/floor-plans/{floor_plan_id}/interpretation"),
                ("post", "/api/floor-plans/{floor_plan_id}/interpretation/reviews"),
                ("post", "/api/projects/{project_id}/floors/{project_floor_id}/floor-plans/{floor_plan_id}/interpretation/layout"),
            },
        )
        self.assertEqual(len(operations), 37)


if __name__ == "__main__":
    unittest.main()
