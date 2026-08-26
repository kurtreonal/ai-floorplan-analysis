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
from sqlalchemy.exc import DatabaseError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.repositories.floor_plan_repository import find_owned_floor_plan_for_update
from app.services.processing_job_service import (
    FLOOR_PLAN_ANALYSIS_JOB_TYPE,
    SAFE_PROCESSING_FAILURE_MESSAGE,
    mark_processing_job_failed,
)


SESSION_COOKIE = "ved_session"
SESSION_SECRET = "f2-automated-test-session-secret"
PROCESS_PATH = "/api/floor-plans/{floor_plan_id}/process"
EXISTING_OPERATIONS = {
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
}


class ProcessingJobApiTests(unittest.TestCase):
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

        cls.unsupported_role = Role(name=f"F2_TEST_{cls.marker[:8].upper()}")
        cls.designer = User(
            oauth_provider="f2-test",
            oauth_subject=f"designer-{cls.marker}",
            email=f"designer-{cls.marker}@example.test",
            role=roles["DESIGNER"],
        )
        cls.other_designer = User(
            oauth_provider="f2-test",
            oauth_subject=f"other-{cls.marker}",
            email=f"other-{cls.marker}@example.test",
            role=roles["DESIGNER"],
        )
        cls.admin = User(
            oauth_provider="f2-test",
            oauth_subject=f"admin-{cls.marker}",
            email=f"admin-{cls.marker}@example.test",
            role=roles["ADMIN"],
        )
        cls.unsupported_user = User(
            oauth_provider="f2-test",
            oauth_subject=f"unsupported-{cls.marker}",
            email=f"unsupported-{cls.marker}@example.test",
            role=cls.unsupported_role,
        )
        cls.project = Project(owner=cls.designer, name=f"F2 Project {cls.marker}")
        cls.project_floor = ProjectFloor(project=cls.project, name="Ground Floor")
        cls.other_project = Project(
            owner=cls.other_designer,
            name=f"F2 Other Project {cls.marker}",
        )
        cls.other_project_floor = ProjectFloor(
            project=cls.other_project,
            name="Other Floor",
        )

        cls.storage_root = TemporaryDirectory()
        cls.original_path = Path(cls.storage_root.name) / "original.png"
        cls.original_bytes = b"f2-original-floor-plan-bytes"
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
        cls.second_floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="second.png",
            storage_path="originals/second.png",
            mime_type="image/png",
            file_size=12,
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
                cls.second_floor_plan,
                cls.other_floor_plan,
                cls.admin,
                cls.unsupported_user,
            )
        )
        cls.database_session.commit()
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported_user.id,
        }
        cls.floor_plan_ids = (
            cls.floor_plan.id,
            cls.second_floor_plan.id,
            cls.other_floor_plan.id,
        )

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="f2-client",
            oauth_client_secret="f2-client-secret",
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
                delete(ProcessingJob).where(
                    ProcessingJob.floor_plan_id.in_(cls.floor_plan_ids)
                )
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
                delete(User).where(User.oauth_provider == "f2-test")
            )
            cls.database_session.execute(
                delete(Role).where(Role.id == cls.unsupported_role.id)
            )
            cls.database_session.commit()
        finally:
            cls.database_session.close()

        try:
            current_digest = hashlib.sha256(cls.original_path.read_bytes()).hexdigest()
            if current_digest != cls.original_digest:
                raise AssertionError("The F2 original test file was modified.")
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
                .where(User.oauth_provider == "f2-test")
            )

        if remaining_users != 0:
            raise AssertionError("F2 test users were not cleaned up.")
        if current_floor_plans != cls.preexisting_floor_plans:
            raise AssertionError("Pre-existing floor-plan records changed.")
        if current_jobs != cls.preexisting_jobs:
            raise AssertionError("Pre-existing processing-job records changed.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()
        self.database_session.execute(
            delete(ProcessingJob).where(
                ProcessingJob.floor_plan_id.in_(self.floor_plan_ids)
            )
        )
        self.database_session.commit()

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

    def _post(
        self,
        floor_plan_id: int | str,
        *,
        user_id: int | None = None,
        query: str = "",
        headers: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
    ):
        if user_id is not None:
            self._set_session(user_id)
        return self.client.post(
            f"/api/floor-plans/{floor_plan_id}/process{query}",
            headers=headers,
            json=body,
        )

    def _add_job(
        self,
        *,
        floor_plan_id: int | None = None,
        status: str = "queued",
        job_type: str = FLOOR_PLAN_ANALYSIS_JOB_TYPE,
    ) -> ProcessingJob:
        job = ProcessingJob(
            floor_plan_id=floor_plan_id or self.floor_plan.id,
            job_type=job_type,
            status=status,
        )
        self.database_session.add(job)
        self.database_session.commit()
        return job

    def _count_fixture_jobs(self) -> int:
        return self.database_session.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(ProcessingJob.floor_plan_id.in_(self.floor_plan_ids))
        )

    def test_openapi_contract_adds_only_the_f2_post_operation(self) -> None:
        schema = self.application.openapi()
        path = schema["paths"][PROCESS_PATH]
        self.assertEqual(set(path), {"post"})
        operation = path["post"]
        self.assertNotIn("requestBody", operation)
        response_schema = operation["responses"]["202"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(
            response_schema["$ref"],
            "#/components/schemas/ProcessingJobStartResponse",
        )
        operations = {
            (method, route)
            for route, definition in schema["paths"].items()
            for method in definition
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(
            operations,
            EXISTING_OPERATIONS | {("post", PROCESS_PATH)},
        )
        self.assertEqual(len(operations), 12)

    def test_owning_designer_creates_durable_queued_job(self) -> None:
        response = self._post(
            self.floor_plan.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["status"], "queued")
        job_id = response.json()["job_id"]

        with Session(self.engine) as reload_session:
            job = reload_session.get(ProcessingJob, job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.floor_plan_id, self.floor_plan.id)
            self.assertEqual(job.job_type, FLOOR_PLAN_ANALYSIS_JOB_TYPE)
            self.assertEqual(job.status, "queued")
            self.assertEqual(job.progress, 0)
            self.assertIsNone(job.error_message)
            self.assertIsNotNone(job.created_at)
            self.assertIsNotNone(job.updated_at)

    def test_unauthenticated_admin_and_unsupported_roles_are_denied(self) -> None:
        unauthenticated = self._post(self.floor_plan.id)
        self.assertEqual(unauthenticated.status_code, 401)

        for role_name in ("admin", "unsupported"):
            with self.subTest(role=role_name):
                response = self._post(
                    self.floor_plan.id,
                    user_id=self.user_ids[role_name],
                )
                self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self._count_fixture_jobs(), 0)

    def test_inaccessible_and_missing_floor_plans_share_sanitized_404(self) -> None:
        responses = (
            self._post(
                self.other_floor_plan.id,
                user_id=self.user_ids["designer"],
            ),
            self._post(9223372036854775807, user_id=self.user_ids["designer"]),
        )
        for response in responses:
            self.assertEqual(response.status_code, 404, response.text)
            self.assertEqual(
                response.json(),
                {
                    "detail": {
                        "error": {
                            "code": "FLOOR_PLAN_NOT_FOUND",
                            "message": "The requested floor plan was not found.",
                            "details": {},
                        }
                    }
                },
            )

    def test_invalid_and_missing_path_ids_are_rejected(self) -> None:
        self._set_session(self.user_ids["designer"])
        missing = self.client.post("/api/floor-plans/process")
        self.assertEqual(missing.status_code, 404)
        for value in ("not-an-integer", 0, -1):
            with self.subTest(value=value):
                response = self._post(value, user_id=self.user_ids["designer"])
                self.assertEqual(response.status_code, 422, response.text)

    def test_untrusted_inputs_cannot_change_ownership_or_job_fields(self) -> None:
        self._set_session(
            self.user_ids["designer"],
            owner_id=self.user_ids["other"],
            role="ADMIN",
        )
        denied = self.client.post(
            f"/api/floor-plans/{self.other_floor_plan.id}/process"
            f"?owner_id={self.user_ids['designer']}",
            headers={"X-Owner-Id": str(self.user_ids["designer"])},
            json={
                "floor_plan_id": self.floor_plan.id,
                "type": "forged",
                "status": "completed",
                "progress": 100,
                "error_message": "forged",
            },
        )
        self.assertEqual(denied.status_code, 404, denied.text)

        response = self._post(
            self.floor_plan.id,
            user_id=self.user_ids["designer"],
            body={
                "floor_plan_id": self.other_floor_plan.id,
                "type": "forged",
                "status": "completed",
                "progress": 100,
                "error_message": "forged",
            },
        )
        self.assertEqual(response.status_code, 202, response.text)
        job = self.database_session.get(ProcessingJob, response.json()["job_id"])
        self.assertEqual(job.floor_plan_id, self.floor_plan.id)
        self.assertEqual(job.job_type, FLOOR_PLAN_ANALYSIS_JOB_TYPE)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        self.assertIsNone(job.error_message)

    def test_queued_and_processing_jobs_return_deterministic_conflict(self) -> None:
        for active_status in ("queued", "processing"):
            with self.subTest(status=active_status):
                self.database_session.execute(
                    delete(ProcessingJob).where(
                        ProcessingJob.floor_plan_id == self.floor_plan.id
                    )
                )
                self.database_session.commit()
                older = self._add_job(status=active_status)
                newer = self._add_job(status=active_status)

                response = self._post(
                    self.floor_plan.id,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 409, response.text)
                error = response.json()["detail"]["error"]
                self.assertEqual(error["code"], "PROCESSING_JOB_ALREADY_ACTIVE")
                self.assertEqual(error["details"], {"job_id": newer.id})
                self.assertGreater(newer.id, older.id)
                self.assertEqual(self._count_fixture_jobs(), 2)

    def test_second_start_request_returns_existing_job_and_count_stays_one(self) -> None:
        first = self._post(
            self.floor_plan.id,
            user_id=self.user_ids["designer"],
        )
        second = self._post(
            self.floor_plan.id,
            user_id=self.user_ids["designer"],
        )

        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(
            second.json()["detail"]["error"]["details"]["job_id"],
            first.json()["job_id"],
        )
        self.assertEqual(self._count_fixture_jobs(), 1)

    def test_terminal_jobs_each_permit_a_new_attempt(self) -> None:
        for terminal_status in ("completed", "failed", "cancelled"):
            with self.subTest(status=terminal_status):
                self.database_session.execute(
                    delete(ProcessingJob).where(
                        ProcessingJob.floor_plan_id == self.floor_plan.id
                    )
                )
                self.database_session.commit()
                terminal_job = self._add_job(status=terminal_status)
                response = self._post(
                    self.floor_plan.id,
                    user_id=self.user_ids["designer"],
                )
                self.assertEqual(response.status_code, 202, response.text)
                self.assertNotEqual(response.json()["job_id"], terminal_job.id)
                self.assertEqual(self._count_fixture_jobs(), 2)

    def test_different_floor_plans_may_have_active_jobs(self) -> None:
        responses = (
            self._post(
                self.floor_plan.id,
                user_id=self.user_ids["designer"],
            ),
            self._post(
                self.second_floor_plan.id,
                user_id=self.user_ids["designer"],
            ),
        )
        self.assertEqual([response.status_code for response in responses], [202, 202])
        self.assertEqual(self._count_fixture_jobs(), 2)

    def test_owned_floor_plan_query_uses_for_update(self) -> None:
        mock_session = Mock(spec=Session)
        mock_session.scalar.return_value = self.floor_plan
        result = find_owned_floor_plan_for_update(
            mock_session,
            floor_plan_id=self.floor_plan.id,
            owner_id=self.designer.id,
        )
        self.assertIs(result, self.floor_plan)
        statement = mock_session.scalar.call_args.args[0]
        compiled = str(
            statement.compile(
                dialect=mysql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        self.assertIn("FOR UPDATE", compiled.upper())
        self.assertIn("projects.owner_id", compiled)

    def test_failure_state_persists_safely_without_floor_plan_side_effects(self) -> None:
        job = self._add_job(status="processing")
        original_status = self.floor_plan.processing_status
        synthetic_secret = "password=hunter2 C:\\private\\model.pt SQL SELECT"

        mark_processing_job_failed(
            self.database_session,
            processing_job=job,
        )
        self.database_session.commit()

        with Session(self.engine) as reload_session:
            reloaded = reload_session.get(ProcessingJob, job.id)
            floor_plan = reload_session.get(FloorPlan, self.floor_plan.id)
            self.assertEqual(reloaded.status, "failed")
            self.assertEqual(reloaded.error_message, SAFE_PROCESSING_FAILURE_MESSAGE)
            self.assertEqual(reloaded.progress, 0)
            self.assertNotIn(synthetic_secret, reloaded.error_message)
            self.assertEqual(floor_plan.processing_status, original_status)
        self.assertEqual(self.original_path.read_bytes(), self.original_bytes)

    def test_database_failure_is_sanitized_rolled_back_and_leaves_no_job(self) -> None:
        raw_error = "password=hunter2 SELECT * FROM users C:\\private\\db.sql"

        def fail_after_flush(database_session, processing_job):
            database_session.add(processing_job)
            database_session.flush()
            raise SQLAlchemyError(raw_error)

        with (
            patch(
                "app.services.processing_job_service.add_processing_job",
                side_effect=fail_after_flush,
            ),
            patch.object(
                self.database_session,
                "rollback",
                wraps=self.database_session.rollback,
            ) as rollback,
        ):
            response = self._post(
                self.floor_plan.id,
                user_id=self.user_ids["designer"],
            )

        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(
            response.json()["detail"]["error"]["code"],
            "PROCESSING_JOB_CREATION_FAILED",
        )
        rollback.assert_called()
        self.assertEqual(self._count_fixture_jobs(), 0)
        response_text = response.text.casefold()
        for forbidden in ("hunter2", "select", "users", "private", "traceback"):
            self.assertNotIn(forbidden, response_text)

    def test_f1_constraints_still_reject_invalid_progress(self) -> None:
        invalid = ProcessingJob(
            floor_plan_id=self.floor_plan.id,
            job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
            progress=101,
        )
        self.database_session.add(invalid)
        try:
            with self.assertRaises(DatabaseError):
                self.database_session.flush()
        finally:
            self.database_session.rollback()

    def test_job_lifecycle_never_changes_original_or_floor_plan_status(self) -> None:
        before_metadata = (
            self.floor_plan.original_filename,
            self.floor_plan.storage_path,
            self.floor_plan.mime_type,
            self.floor_plan.file_size,
            self.floor_plan.processing_status,
        )
        response = self._post(
            self.floor_plan.id,
            user_id=self.user_ids["designer"],
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.database_session.refresh(self.floor_plan)
        after_metadata = (
            self.floor_plan.original_filename,
            self.floor_plan.storage_path,
            self.floor_plan.mime_type,
            self.floor_plan.file_size,
            self.floor_plan.processing_status,
        )
        self.assertEqual(after_metadata, before_metadata)
        self.assertEqual(
            hashlib.sha256(self.original_path.read_bytes()).hexdigest(),
            self.original_digest,
        )


if __name__ == "__main__":
    unittest.main()
