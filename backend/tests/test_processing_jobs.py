import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    delete,
    func,
    inspect,
    select,
)
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import (
    Base,
    FloorPlan,
    ProcessingJob,
    Project,
    ProjectFloor,
    Role,
    User,
)
from app.models.processing_job import PROCESSING_JOB_STATUSES


class ProcessingJobModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.inspector = inspect(cls.engine)
        if "processing_jobs" not in cls.inspector.get_table_names():
            raise RuntimeError(
                "Run the development schema initializer before F1 tests."
            )

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
            cls.preexisting_processing_job_count = baseline_session.scalar(
                select(func.count()).select_from(ProcessingJob)
            )

        cls.connection = cls.engine.connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        designer_role = cls.database_session.scalar(
            select(Role).where(Role.name == "DESIGNER")
        )
        if designer_role is None:
            raise RuntimeError("The DESIGNER seed role is required.")

        cls.marker = uuid4().hex
        cls.user = User(
            oauth_provider="f1-test",
            oauth_subject=f"designer-{cls.marker}",
            email=f"designer-{cls.marker}@example.test",
            display_name="F1 Designer",
            role_id=designer_role.id,
        )
        cls.project = Project(
            owner=cls.user,
            name=f"F1 Processing Project {cls.marker}",
        )
        cls.project_floor = ProjectFloor(
            project=cls.project,
            name="Ground Floor",
        )
        cls.floor_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="f1-original.png",
            storage_path="originals/f1-original.png",
            mime_type="image/png",
            file_size=24,
            processing_status="uploaded",
        )
        cls.database_session.add(cls.floor_plan)
        cls.database_session.flush()
        cls.database_session.commit()
        cls.user_id = cls.user.id
        cls.project_id = cls.project.id
        cls.project_floor_id = cls.project_floor.id
        cls.floor_plan_id = cls.floor_plan.id

        cls.temporary_directory = TemporaryDirectory()
        cls.original_path = Path(cls.temporary_directory.name) / "f1-original.png"
        cls.original_bytes = b"unchanged-f1-original-bytes"
        cls.original_path.write_bytes(cls.original_bytes)
        cls.original_digest = hashlib.sha256(cls.original_bytes).hexdigest()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.database_session.execute(
                delete(ProcessingJob).where(
                    ProcessingJob.floor_plan_id == cls.floor_plan_id
                )
            )
            cls.database_session.execute(
                delete(FloorPlan).where(FloorPlan.id == cls.floor_plan_id)
            )
            cls.database_session.execute(
                delete(ProjectFloor).where(ProjectFloor.id == cls.project_floor_id)
            )
            cls.database_session.execute(
                delete(Project).where(Project.id == cls.project_id)
            )
            cls.database_session.execute(delete(User).where(User.id == cls.user_id))
            cls.database_session.flush()
        finally:
            cls.database_session.close()
            if cls.transaction.is_active:
                cls.transaction.rollback()
            cls.connection.close()

        try:
            if hashlib.sha256(cls.original_path.read_bytes()).hexdigest() != cls.original_digest:
                raise AssertionError("The F1 original test file was modified.")
        finally:
            cls.temporary_directory.cleanup()

        with Session(cls.engine) as verification_session:
            remaining_test_users = verification_session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.oauth_provider == "f1-test")
            )
            remaining_test_jobs = verification_session.scalar(
                select(func.count())
                .select_from(ProcessingJob)
                .where(ProcessingJob.job_type.like(f"f1-{cls.marker}%"))
            )
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
            current_processing_job_count = verification_session.scalar(
                select(func.count()).select_from(ProcessingJob)
            )

        if remaining_test_users != 0 or remaining_test_jobs != 0:
            raise AssertionError("F1 database test records were not cleaned up.")
        if current_floor_plans != cls.preexisting_floor_plans:
            raise AssertionError("Pre-existing floor-plan records changed during F1 tests.")
        if current_processing_job_count != cls.preexisting_processing_job_count:
            raise AssertionError("Pre-existing processing-job records changed during F1 tests.")

    def create_job(self, **overrides: object) -> ProcessingJob:
        values = {
            "floor_plan_id": self.floor_plan_id,
            "job_type": f"f1-{self.marker}-floor-plan-analysis",
            **overrides,
        }
        job = ProcessingJob(**values)
        self.database_session.add(job)
        self.database_session.flush()
        return job

    def assert_integrity_error(self, **values: object) -> None:
        self.database_session.add(ProcessingJob(**values))
        try:
            with self.assertRaises(DatabaseError):
                self.database_session.flush()
        finally:
            self.database_session.rollback()

    def test_processing_jobs_is_registered_in_metadata(self) -> None:
        self.assertIn("processing_jobs", Base.metadata.tables)
        self.assertIs(ProcessingJob.__table__, Base.metadata.tables["processing_jobs"])

    def test_exact_columns_types_and_nullability(self) -> None:
        table = ProcessingJob.__table__
        self.assertEqual(
            tuple(table.columns.keys()),
            (
                "id",
                "floor_plan_id",
                "type",
                "status",
                "progress",
                "error_message",
                "created_at",
                "updated_at",
            ),
        )
        expected = {
            "id": (BigInteger, False),
            "floor_plan_id": (BigInteger, False),
            "type": (String, False),
            "status": (String, False),
            "progress": (Integer, False),
            "error_message": (Text, True),
            "created_at": (DateTime, False),
            "updated_at": (DateTime, False),
        }
        for name, (column_type, nullable) in expected.items():
            with self.subTest(column=name):
                self.assertIsInstance(table.c[name].type, column_type)
                self.assertEqual(table.c[name].nullable, nullable)
        self.assertEqual(table.c["type"].type.length, 64)
        self.assertEqual(table.c.status.type.length, 32)

    def test_defaults_and_timestamp_update_contract(self) -> None:
        table = ProcessingJob.__table__
        self.assertIsNotNone(table.c.status.server_default)
        self.assertIsNotNone(table.c.progress.server_default)
        self.assertIsNotNone(table.c.created_at.server_default)
        self.assertIsNotNone(table.c.updated_at.server_default)
        self.assertIsNotNone(table.c.updated_at.onupdate)

    def test_named_constraints_are_registered_and_live(self) -> None:
        model_names = {constraint.name for constraint in ProcessingJob.__table__.constraints}
        live_names = {
            constraint["name"]
            for constraint in self.inspector.get_check_constraints("processing_jobs")
        }
        for name in ("ck_processing_jobs_status", "ck_processing_jobs_progress"):
            self.assertIn(name, model_names)
            self.assertIn(name, live_names)

    def test_floor_plan_foreign_key_contract(self) -> None:
        foreign_keys = tuple(ProcessingJob.__table__.c.floor_plan_id.foreign_keys)
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0].target_fullname, "floor_plans.id")
        live_foreign_keys = self.inspector.get_foreign_keys("processing_jobs")
        self.assertEqual(len(live_foreign_keys), 1)
        self.assertEqual(live_foreign_keys[0]["constrained_columns"], ["floor_plan_id"])
        self.assertEqual(live_foreign_keys[0]["referred_table"], "floor_plans")
        self.assertEqual(live_foreign_keys[0]["referred_columns"], ["id"])

    def test_floor_plan_foreign_key_is_indexed(self) -> None:
        indexed_columns = {
            tuple(index["column_names"])
            for index in self.inspector.get_indexes("processing_jobs")
        }
        self.assertIn(("floor_plan_id",), indexed_columns)

    def test_valid_job_persists_with_defaults_and_timestamps(self) -> None:
        job = self.create_job()
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        self.assertIsNone(job.error_message)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)
        self.assertIs(self.database_session.get(ProcessingJob, job.id), job)

    def test_failed_job_stores_safe_error_message(self) -> None:
        job = self.create_job(
            status="failed",
            progress=35,
            error_message="The floor plan could not be processed.",
        )
        self.assertEqual(job.error_message, "The floor plan could not be processed.")

    def test_each_allowed_status_persists(self) -> None:
        for job_status in PROCESSING_JOB_STATUSES:
            with self.subTest(status=job_status):
                job = self.create_job(status=job_status)
                self.assertEqual(job.status, job_status)

    def test_unknown_status_is_rejected_by_database(self) -> None:
        self.assert_integrity_error(
            floor_plan_id=self.floor_plan_id,
            job_type=f"f1-{self.marker}-unknown-status",
            status="unknown",
        )

    def test_progress_boundaries_are_accepted(self) -> None:
        for progress in (0, 100):
            with self.subTest(progress=progress):
                job = self.create_job(progress=progress)
                self.assertEqual(job.progress, progress)

    def test_progress_outside_boundaries_is_rejected(self) -> None:
        for progress in (-1, 101):
            with self.subTest(progress=progress):
                self.assert_integrity_error(
                    floor_plan_id=self.floor_plan_id,
                    job_type=f"f1-{self.marker}-progress-{progress}",
                    progress=progress,
                )

    def test_missing_job_type_is_rejected(self) -> None:
        self.assert_integrity_error(floor_plan_id=self.floor_plan.id)

    def test_missing_or_nonexistent_floor_plan_is_rejected(self) -> None:
        self.assert_integrity_error(
            job_type=f"f1-{self.marker}-missing-floor-plan"
        )
        self.assert_integrity_error(
            floor_plan_id=9223372036854775807,
            job_type=f"f1-{self.marker}-nonexistent-floor-plan",
        )

    def test_bidirectional_floor_plan_relationship(self) -> None:
        job = self.create_job()
        self.assertIs(job.floor_plan, self.floor_plan)
        self.assertIn(job, self.floor_plan.processing_jobs)

    def test_job_operations_do_not_modify_original_file(self) -> None:
        job = self.create_job()
        self.database_session.get(ProcessingJob, job.id)
        self.assertEqual(self.original_path.read_bytes(), self.original_bytes)
        self.assertEqual(
            hashlib.sha256(self.original_path.read_bytes()).hexdigest(),
            self.original_digest,
        )

    def test_job_creation_does_not_change_floor_plan_processing_status(self) -> None:
        before = self.floor_plan.processing_status
        self.create_job(status="processing", progress=50)
        self.database_session.refresh(self.floor_plan)
        self.assertEqual(before, "uploaded")
        self.assertEqual(self.floor_plan.processing_status, before)


if __name__ == "__main__":
    unittest.main()
