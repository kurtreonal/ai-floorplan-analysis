import json
import socket
import subprocess
import unittest
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_engine
from app.main import create_app
from app.models import (
    Base,
    FloorPlan,
    ProcessingJob,
    ProcessingJobAttempt,
    ProcessingJobCancellation,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.services.processing_execution_service import (
    MAXIMUM_ATTEMPTS,
    ProcessingExecutionError,
    claim_processing_job,
    finish_processing_attempt,
    heartbeat_processing_attempt,
    recover_legacy_processing_job,
    request_processing_cancellation,
)


SESSION_SECRET = "pre9-processing-execution-test-secret"


class ProcessingExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.baseline = cls._counts()
        marker = uuid4().hex
        with Session(cls.engine, expire_on_commit=False) as session:
            roles = {
                role.name: role
                for role in session.scalars(select(Role).where(Role.name.in_(("ADMIN", "DESIGNER"))))
            }
            cls.designer = User(
                oauth_provider=f"pre9-{marker}",
                oauth_subject="designer",
                role=roles["DESIGNER"],
            )
            cls.other_designer = User(
                oauth_provider=f"pre9-{marker}",
                oauth_subject="other",
                role=roles["DESIGNER"],
            )
            cls.admin = User(
                oauth_provider=f"pre9-{marker}",
                oauth_subject="admin",
                role=roles["ADMIN"],
            )
            project = Project(owner=cls.designer, name=f"PRE9 {marker}")
            floor = ProjectFloor(project=project, name="Ground Floor", sort_order=0)
            cls.floor_plan = FloorPlan(
                project_floor=floor,
                original_filename="pre9.png",
                storage_path="originals/pre9.png",
                mime_type="image/png",
                file_size=100,
                processing_status="uploaded",
            )
            session.add_all((cls.floor_plan, cls.other_designer, cls.admin))
            session.commit()
            cls.user_ids = {
                "designer": cls.designer.id,
                "other": cls.other_designer.id,
                "admin": cls.admin.id,
            }
            cls.project_id = project.id
            cls.floor_id = floor.id
            cls.floor_plan_id = cls.floor_plan.id

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            oauth_provider="synthetic",
            oauth_client_id="pre9-client",
            oauth_client_secret="pre9-secret",
            oauth_redirect_uri="http://localhost:8000/api/auth/callback",
            oauth_discovery_url="https://provider.invalid/.well-known/openid-configuration",
            oauth_scopes="openid profile email",
            session_secret=SESSION_SECRET,
        )
        cls.application = create_app(settings)
        cls.client = TestClient(cls.application)

    @classmethod
    def _counts(cls):
        with Session(cls.engine) as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        with Session(cls.engine) as session:
            job_ids = select(ProcessingJob.id).where(ProcessingJob.floor_plan_id == cls.floor_plan_id)
            session.execute(delete(ProcessingJobCancellation).where(ProcessingJobCancellation.processing_job_id.in_(job_ids)))
            session.execute(delete(ProcessingJobAttempt).where(ProcessingJobAttempt.processing_job_id.in_(job_ids)))
            session.execute(delete(ProcessingJob).where(ProcessingJob.floor_plan_id == cls.floor_plan_id))
            session.execute(delete(FloorPlan).where(FloorPlan.id == cls.floor_plan_id))
            session.execute(delete(ProjectFloor).where(ProjectFloor.id == cls.floor_id))
            session.execute(delete(Project).where(Project.id == cls.project_id))
            session.execute(delete(User).where(User.id.in_(tuple(cls.user_ids.values()))))
            session.commit()
        if cls._counts() != cls.baseline:
            raise AssertionError("PRE9 database rows were not restored.")

    def setUp(self) -> None:
        self.application.dependency_overrides.clear()
        self.client.cookies.clear()
        with Session(self.engine) as session:
            job_ids = select(ProcessingJob.id).where(ProcessingJob.floor_plan_id == self.floor_plan_id)
            session.execute(delete(ProcessingJobCancellation).where(ProcessingJobCancellation.processing_job_id.in_(job_ids)))
            session.execute(delete(ProcessingJobAttempt).where(ProcessingJobAttempt.processing_job_id.in_(job_ids)))
            session.execute(delete(ProcessingJob).where(ProcessingJob.floor_plan_id == self.floor_plan_id))
            session.commit()

    def _job(self, status="queued") -> int:
        with Session(self.engine) as session:
            job = ProcessingJob(
                floor_plan_id=self.floor_plan_id,
                job_type="floor_plan_analysis",
                status=status,
            )
            session.add(job)
            session.commit()
            return job.id

    def _user(self, session: Session, name="designer"):
        return session.get(User, self.user_ids[name])

    def _session_cookie(self, user_id: int) -> None:
        encoded = b64encode(json.dumps({"user_id": user_id}).encode())
        value = TimestampSigner(SESSION_SECRET).sign(encoded).decode()
        self.client.cookies.set("ved_session", value, domain="testserver.local")

    def test_schema_and_openapi_contract(self) -> None:
        inspector = inspect(self.engine)
        self.assertEqual(len(Base.metadata.tables), 23)
        self.assertEqual(set(inspector.get_table_names()), set(Base.metadata.tables))
        self.assertEqual(
            {item["name"] for item in inspector.get_unique_constraints("processing_job_attempts")},
            {"uq_processing_job_attempts_job_active", "uq_processing_job_attempts_job_number"},
        )
        schema = self.application.openapi()
        self.assertIn("post", schema["paths"]["/api/processing-jobs/{job_id}/cancel"])
        operations = sum(
            method in {"get", "post", "put", "patch", "delete"}
            for path in schema["paths"].values()
            for method in path
        )
        self.assertEqual(operations, 34)

    def test_concurrent_claim_has_exactly_one_active_owner(self) -> None:
        job_id = self._job()

        def submit(worker):
            try:
                with Session(self.engine, expire_on_commit=False) as session:
                    return claim_processing_job(
                        session,
                        job_id=job_id,
                        worker_identity=worker,
                        lease_seconds=30,
                    )
            except ProcessingExecutionError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(submit, ("worker-a", "worker-b")))
        claims = [result for result in results if not isinstance(result, str)]
        self.assertEqual(len(claims), 1)
        self.assertIn("PROCESSING_JOB_ALREADY_CLAIMED", results)
        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ProcessingJobAttempt).where(ProcessingJobAttempt.active_marker.is_(True))),
                1,
            )

    def test_named_heartbeat_success_and_no_timer_progress(self) -> None:
        job_id = self._job()
        moment = datetime(2026, 1, 1, 12, 0, 0)
        with Session(self.engine, expire_on_commit=False) as session:
            claim = claim_processing_job(session, job_id=job_id, worker_identity="worker-a", lease_seconds=30, now=moment)
        with Session(self.engine) as session:
            cancelled = heartbeat_processing_attempt(
                session,
                attempt_id=claim.attempt_id,
                worker_identity="worker-a",
                stage="normalization",
                lease_seconds=60,
                now=moment + timedelta(seconds=10),
            )
            self.assertFalse(cancelled)
        with Session(self.engine) as session:
            self.assertEqual(session.get(ProcessingJob, job_id).progress, 30)
            attempt = session.get(ProcessingJobAttempt, claim.attempt_id)
            self.assertEqual(attempt.stage, "normalization")
            self.assertEqual(attempt.lease_expires_at, moment + timedelta(seconds=70))
        with Session(self.engine) as session:
            finish_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity="worker-a", outcome="succeeded", now=moment + timedelta(seconds=20))
        with Session(self.engine) as session:
            self.assertEqual((session.get(ProcessingJob, job_id).status, session.get(ProcessingJob, job_id).progress), ("completed", 100))

    def test_execution_primitive_validation_is_bounded(self) -> None:
        job_id = self._job()
        with Session(self.engine, expire_on_commit=False) as session:
            claim = claim_processing_job(
                session,
                job_id=job_id,
                worker_identity="worker-a",
                lease_seconds=30,
            )
        with Session(self.engine) as session:
            with self.assertRaises(ProcessingExecutionError) as caught:
                finish_processing_attempt(
                    session,
                    attempt_id=claim.attempt_id,
                    worker_identity="worker-a",
                    outcome="failed",
                    failure_code="unsafe failure detail",
                )
        self.assertEqual(caught.exception.code, "INVALID_FAILURE_CODE")
        with Session(self.engine) as session:
            with self.assertRaises(ProcessingExecutionError) as caught:
                claim_processing_job(
                    session,
                    job_id=0,
                    worker_identity="worker-a",
                    lease_seconds=30,
                )
        self.assertEqual(caught.exception.code, "INVALID_IDENTIFIER")

    def test_expired_lease_recovers_and_retry_exhaustion_is_terminal(self) -> None:
        job_id = self._job()
        moment = datetime(2026, 1, 1, 12, 0, 0)
        for attempt_number in range(1, MAXIMUM_ATTEMPTS + 1):
            with Session(self.engine, expire_on_commit=False) as session:
                claim = claim_processing_job(
                    session,
                    job_id=job_id,
                    worker_identity=f"worker-{attempt_number}",
                    lease_seconds=15,
                    now=moment + timedelta(minutes=attempt_number),
                )
            if attempt_number < MAXIMUM_ATTEMPTS:
                with Session(self.engine) as session:
                    finish_processing_attempt(
                        session,
                        attempt_id=claim.attempt_id,
                        worker_identity=f"worker-{attempt_number}",
                        outcome="failed",
                        failure_code="STAGE_FAILED",
                        now=moment + timedelta(minutes=attempt_number, seconds=1),
                    )
        with Session(self.engine) as session:
            finish_processing_attempt(
                session,
                attempt_id=claim.attempt_id,
                worker_identity=f"worker-{MAXIMUM_ATTEMPTS}",
                outcome="failed",
                failure_code="STAGE_FAILED",
                now=moment + timedelta(minutes=4),
            )
        with Session(self.engine) as session:
            self.assertEqual(session.get(ProcessingJob, job_id).status, "failed")

        crash_job_id = self._job()
        with Session(self.engine, expire_on_commit=False) as session:
            first = claim_processing_job(session, job_id=crash_job_id, worker_identity="crashed-worker", lease_seconds=15, now=moment)
        with Session(self.engine, expire_on_commit=False) as session:
            replacement = claim_processing_job(session, job_id=crash_job_id, worker_identity="replacement", lease_seconds=15, now=moment + timedelta(seconds=16))
        self.assertEqual(replacement.attempt_number, 2)
        with Session(self.engine) as session:
            self.assertEqual(session.get(ProcessingJobAttempt, first.attempt_id).status, "lease_expired")

    def test_queued_and_cooperative_cancellation(self) -> None:
        queued_job = self._job()
        with Session(self.engine) as session:
            result = request_processing_cancellation(session, current_user=self._user(session), job_id=queued_job)
        self.assertEqual((result.status, result.mode), ("cancelled", "queued_cancelled"))

        active_job = self._job()
        with Session(self.engine, expire_on_commit=False) as session:
            claim = claim_processing_job(session, job_id=active_job, worker_identity="worker-a", lease_seconds=30)
        with Session(self.engine) as session:
            result = request_processing_cancellation(session, current_user=self._user(session), job_id=active_job)
        self.assertEqual((result.status, result.mode), ("processing", "cooperative_requested"))
        with Session(self.engine) as session:
            self.assertTrue(heartbeat_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity="worker-a", stage="source_preparation", lease_seconds=30))
        with Session(self.engine) as session:
            finish_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity="worker-a", outcome="cancelled")
        with Session(self.engine) as session:
            self.assertEqual(session.get(ProcessingJob, active_job).status, "cancelled")

    def test_legacy_processing_requires_explicit_recovery(self) -> None:
        job_id = self._job(status="processing")
        with Session(self.engine) as session:
            with self.assertRaises(ProcessingExecutionError) as caught:
                claim_processing_job(session, job_id=job_id, worker_identity="worker-a", lease_seconds=30)
        self.assertEqual(caught.exception.code, "LEGACY_PROCESSING_JOB_REQUIRES_RECOVERY")
        with Session(self.engine) as session:
            recover_legacy_processing_job(session, job_id=job_id)
        with Session(self.engine, expire_on_commit=False) as session:
            self.assertEqual(claim_processing_job(session, job_id=job_id, worker_identity="worker-a", lease_seconds=30).attempt_number, 1)

    def test_cancellation_api_authorization_scope_and_idempotency(self) -> None:
        job_id = self._job()
        path = f"/api/processing-jobs/{job_id}/cancel"
        self.assertEqual(self.client.post(path).status_code, 401)
        self._session_cookie(self.user_ids["admin"])
        self.assertEqual(self.client.post(path).status_code, 403)
        self.client.cookies.clear()
        self._session_cookie(self.user_ids["other"])
        self.assertEqual(self.client.post(path).status_code, 404)
        self.client.cookies.clear()
        self._session_cookie(self.user_ids["designer"])
        first = self.client.post(path)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), {"job_id": job_id, "status": "cancelled", "cancellation_mode": "queued_cancelled"})
        second = self.client.post(path)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())

    def test_foundation_invokes_no_processing_or_model_pipeline(self) -> None:
        job_id = self._job()
        with (
            patch("builtins.open", side_effect=AssertionError("file invoked")),
            patch.object(socket, "create_connection", side_effect=AssertionError("network invoked")),
            patch.object(subprocess, "run", side_effect=AssertionError("process invoked")),
        ):
            with Session(self.engine) as session:
                result = claim_processing_job(session, job_id=job_id, worker_identity="worker-a", lease_seconds=30)
        self.assertEqual(result.attempt_number, 1)


if __name__ == "__main__":
    unittest.main()
