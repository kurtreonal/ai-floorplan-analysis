import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import FloorPlan, FloorPlanPage, FloorPlanSource, ProcessingArtifact, ProcessingJob, Project, ProjectFloor, Role, User
from app.services.processing_artifact_service import (
    ProcessingArtifactError,
    register_processing_artifact,
    resolve_trusted_processing_artifact,
)


class ProcessingArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.session = Session(bind=cls.connection, expire_on_commit=False)
        role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        marker = uuid4().hex
        user = User(oauth_provider="pre5-test", oauth_subject=marker, role=role)
        project = Project(owner=user, name=f"PRE5 {marker}")
        floor = ProjectFloor(project=project, name="Ground")
        plan = FloorPlan(
            project_floor=floor,
            original_filename="plan.png",
            storage_path="originals/plan.png",
            mime_type="image/png",
            file_size=1,
        )
        source = FloorPlanSource(
            floor_plan=plan,
            original_sha256="a" * 64,
            pages=[FloorPlanPage(page_number=1)],
        )
        cls.job = ProcessingJob(floor_plan=plan, job_type="floor_plan_analysis")
        cls.session.add_all((source, cls.job))
        cls.session.flush()
        cls.page = source.pages[0]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.savepoint = self.connection.begin_nested()
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.relative = f"normalized/floor-plan-{self.job.floor_plan_id}/job-{self.job.id}/image.png"
        self.path = self.root.joinpath(*self.relative.split("/"))
        self.path.parent.mkdir(parents=True)
        Image.new("RGB", (16, 10), "white").save(self.path, "PNG")

    def tearDown(self) -> None:
        self.session.expire_all()
        if self.savepoint.is_active:
            self.savepoint.rollback()
        self.temp.cleanup()

    def register(self):
        return register_processing_artifact(
            self.session,
            processing_job=self.job,
            floor_plan_id=self.job.floor_plan_id,
            page_number=1,
            artifact_kind="normalized_image",
            processed_directory=self.root,
            relative_path=self.relative,
            mime_type="image/png",
        )

    def test_live_schema_has_bounded_manifest_contract(self) -> None:
        inspector = inspect(get_engine())
        self.assertEqual(len(inspector.get_table_names()), 19)
        self.assertIn("processing_artifacts", inspector.get_table_names())
        checks = {item["name"] for item in inspector.get_check_constraints("processing_artifacts")}
        self.assertTrue({"ck_processing_artifacts_kind", "ck_processing_artifacts_byte_size", "ck_processing_artifacts_sha256_length", "ck_processing_artifacts_dimensions"}.issubset(checks))
        self.assertIn("uq_processing_artifacts_relative_path", {item["name"] for item in inspector.get_unique_constraints("processing_artifacts")})

    def test_registration_records_exact_job_page_path_hash_mime_size_and_dimensions(self) -> None:
        artifact = self.register()
        content = self.path.read_bytes()
        self.assertEqual(artifact.processing_job_id, self.job.id)
        self.assertEqual(artifact.floor_plan_page_id, self.page.id)
        self.assertEqual(artifact.relative_path, self.relative)
        self.assertEqual(artifact.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual((artifact.mime_type, artifact.byte_size), ("image/png", len(content)))
        self.assertEqual((artifact.pixel_width, artifact.pixel_height), (16, 10))

    def test_identical_retry_is_idempotent_and_changed_content_conflicts(self) -> None:
        first = self.register()
        self.assertIs(self.register(), first)
        Image.new("RGB", (17, 10), "black").save(self.path, "PNG")
        with self.assertRaises(ProcessingArtifactError):
            self.register()

    def test_resolution_revalidates_hash_size_and_dimensions(self) -> None:
        artifact = self.register()
        trusted = resolve_trusted_processing_artifact(
            self.session,
            floor_plan_id=self.job.floor_plan_id,
            processing_job_id=self.job.id,
            artifact_kind="normalized_image",
            processed_directory=self.root,
        )
        self.assertEqual(trusted.record.id, artifact.id)
        self.path.write_bytes(b"not a png")
        with self.assertRaises(ProcessingArtifactError):
            resolve_trusted_processing_artifact(
                self.session,
                floor_plan_id=self.job.floor_plan_id,
                processing_job_id=self.job.id,
                artifact_kind="normalized_image",
                processed_directory=self.root,
            )

    def test_rejects_traversal_wrong_mime_kind_page_and_job(self) -> None:
        cases = (
            {"relative_path": "../image.png"},
            {"mime_type": "image/jpeg"},
            {"artifact_kind": "unknown"},
            {"page_number": 2},
            {"floor_plan_id": self.job.floor_plan_id + 1},
        )
        base = {
            "processing_job": self.job,
            "floor_plan_id": self.job.floor_plan_id,
            "page_number": 1,
            "artifact_kind": "normalized_image",
            "processed_directory": self.root,
            "relative_path": self.relative,
            "mime_type": "image/png",
        }
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ProcessingArtifactError):
                register_processing_artifact(self.session, **{**base, **changes})


if __name__ == "__main__":
    unittest.main()
