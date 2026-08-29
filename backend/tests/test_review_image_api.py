import hashlib
import json
import unittest
import uuid
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User


SESSION_SECRET = "j1a-test-session-secret-with-sufficient-length"
SESSION_COOKIE = "ved_session"
PATH = "/api/floor-plans/{floor_plan_id}/review-image"


def _image_bytes(*, mode: str = "RGB", size: tuple[int, int] = (80, 60), format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new(mode, size, 128).save(output, format=format)
    return output.getvalue()


class ReviewImageApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.marker = f"j1a-{uuid.uuid4().hex}"
        cls.database_session = Session(cls.engine, autoflush=False, expire_on_commit=False)
        cls.baseline_counts = cls._table_counts()

        designer_role = cls.database_session.scalar(select(Role).where(Role.name == "DESIGNER"))
        admin_role = cls.database_session.scalar(select(Role).where(Role.name == "ADMIN"))
        if designer_role is None or admin_role is None:
            raise unittest.SkipTest("Seeded ADMIN and DESIGNER roles are required.")

        cls.unsupported_role = Role(name=f"J1A_{uuid.uuid4().hex[:19].upper()}")
        cls.designer = User(
            oauth_provider=cls.marker,
            oauth_subject="designer",
            display_name="J1A Designer",
            role=designer_role,
        )
        cls.other_designer = User(
            oauth_provider=cls.marker,
            oauth_subject="other",
            display_name="J1A Other Designer",
            role=designer_role,
        )
        cls.admin = User(
            oauth_provider=cls.marker,
            oauth_subject="admin",
            display_name="J1A Admin",
            role=admin_role,
        )
        cls.unsupported_user = User(
            oauth_provider=cls.marker,
            oauth_subject="unsupported",
            display_name="J1A Unsupported",
            role=cls.unsupported_role,
        )
        cls.project = Project(owner=cls.designer, name=f"{cls.marker}-project")
        cls.other_project = Project(owner=cls.other_designer, name=f"{cls.marker}-other")
        cls.floor = ProjectFloor(project=cls.project, name="Ground")
        cls.other_floor = ProjectFloor(project=cls.other_project, name="Other")

        cls.storage = TemporaryDirectory()
        cls.root = Path(cls.storage.name)
        cls.upload_root = cls.root / "uploads"
        cls.processed_root = cls.root / "processed"
        (cls.upload_root / "originals").mkdir(parents=True)
        cls.processed_root.mkdir()
        cls.original_path = cls.upload_root / "originals" / "plan.png"
        cls.original_bytes = _image_bytes(size=(30, 20))
        cls.original_path.write_bytes(cls.original_bytes)
        cls.original_digest = hashlib.sha256(cls.original_bytes).hexdigest()

        cls.floor_plan = FloorPlan(
            project_floor=cls.floor,
            original_filename="plan.png",
            storage_path="originals/plan.png",
            mime_type="image/png",
            file_size=len(cls.original_bytes),
            processing_status="processed",
        )
        cls.other_floor_plan = FloorPlan(
            project_floor=cls.other_floor,
            original_filename="other.png",
            storage_path="originals/other.png",
            mime_type="image/png",
            file_size=1,
            processing_status="uploaded",
        )
        cls.database_session.add_all(
            (cls.admin, cls.unsupported_user, cls.floor_plan, cls.other_floor_plan)
        )
        cls.database_session.flush()
        cls.job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="floor_plan_analysis",
            status="completed",
            progress=100,
        )
        cls.wrong_type_job = ProcessingJob(
            floor_plan_id=cls.floor_plan.id,
            job_type="other_job",
            status="completed",
            progress=100,
        )
        cls.other_job = ProcessingJob(
            floor_plan_id=cls.other_floor_plan.id,
            job_type="floor_plan_analysis",
            status="completed",
            progress=100,
        )
        cls.database_session.add_all((cls.job, cls.wrong_type_job, cls.other_job))
        cls.database_session.commit()
        cls.created = {
            "jobs": (cls.job.id, cls.wrong_type_job.id, cls.other_job.id),
            "floor_plans": (cls.floor_plan.id, cls.other_floor_plan.id),
            "projects": (cls.project.id, cls.other_project.id),
        }
        cls.image_path = (
            cls.processed_root
            / "normalized"
            / f"floor-plan-{cls.floor_plan.id}"
            / f"job-{cls.job.id}"
            / "image.png"
        )
        cls.image_path.parent.mkdir(parents=True)
        cls.review_bytes = _image_bytes()
        cls.image_path.write_bytes(cls.review_bytes)

        settings = Settings(
            _env_file=None,
            app_env="development",
            database_url=None,
            upload_dir=cls.upload_root,
            processed_dir=cls.processed_root,
            oauth_provider="synthetic",
            oauth_client_id="j1a-client",
            oauth_client_secret="j1a-client-secret",
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
        cls.user_ids = {
            "designer": cls.designer.id,
            "other": cls.other_designer.id,
            "admin": cls.admin.id,
            "unsupported": cls.unsupported_user.id,
        }

    @classmethod
    def _table_counts(cls) -> dict[str, int]:
        with Session(cls.engine) as session:
            return {
                model.__tablename__: session.scalar(select(func.count()).select_from(model))
                for model in (FloorPlan, ProcessingJob, ProjectFloor, Project, Role, User)
            }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        try:
            cls.database_session.rollback()
            cls.database_session.execute(delete(ProcessingJob).where(ProcessingJob.id.in_(cls.created["jobs"])))
            cls.database_session.execute(delete(FloorPlan).where(FloorPlan.id.in_(cls.created["floor_plans"])))
            cls.database_session.execute(delete(ProjectFloor).where(ProjectFloor.project_id.in_(cls.created["projects"])))
            cls.database_session.execute(delete(Project).where(Project.id.in_(cls.created["projects"])))
            cls.database_session.execute(delete(User).where(User.oauth_provider == cls.marker))
            cls.database_session.execute(delete(Role).where(Role.id == cls.unsupported_role.id))
            cls.database_session.commit()
        finally:
            cls.database_session.close()
        try:
            if hashlib.sha256(cls.original_path.read_bytes()).hexdigest() != cls.original_digest:
                raise AssertionError("The J1A original test file was modified.")
        finally:
            cls.storage.cleanup()
        if cls._table_counts() != cls.baseline_counts:
            raise AssertionError("J1A database row counts were not restored.")

    def setUp(self) -> None:
        self.client.cookies.clear()
        self.database_session.rollback()
        self.image_path.parent.mkdir(parents=True, exist_ok=True)
        self.image_path.write_bytes(self.review_bytes)

    def _set_session(self, user_id: int) -> None:
        encoded = b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
        cookie = TimestampSigner(SESSION_SECRET).sign(encoded).decode("utf-8")
        self.client.cookies.set(SESSION_COOKIE, cookie, domain="testserver.local")

    def _get(self, floor_plan_id, job_id, *, user: str | None = None):
        if user is not None:
            self._set_session(self.user_ids[user])
        return self.client.get(
            PATH.format(floor_plan_id=floor_plan_id),
            params={"processing_job_id": job_id} if job_id is not None else None,
        )

    def test_owner_and_admin_receive_exact_private_png(self) -> None:
        for user in ("designer", "admin"):
            with self.subTest(user=user):
                response = self._get(self.floor_plan.id, self.job.id, user=user)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.content, self.review_bytes)
                self.assertEqual(response.headers["content-type"], "image/png")
                self.assertEqual(response.headers["cache-control"], "private, no-store")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                self.assertNotIn("content-disposition", response.headers)

    def test_authentication_and_role_authorization(self) -> None:
        self.assertEqual(self._get(self.floor_plan.id, self.job.id).status_code, 401)
        response = self._get(self.floor_plan.id, self.job.id, user="unsupported")
        self.assertEqual(response.status_code, 403)

    def test_inaccessible_missing_mismatched_and_wrong_type_share_404(self) -> None:
        cases = (
            (self.floor_plan.id, self.job.id, "other"),
            (9_223_372_036_854_775_000, self.job.id, "admin"),
            (self.floor_plan.id, 9_223_372_036_854_775_000, "admin"),
            (self.floor_plan.id, self.other_job.id, "admin"),
            (self.floor_plan.id, self.wrong_type_job.id, "admin"),
        )
        for floor_plan_id, job_id, user in cases:
            with self.subTest(floor_plan_id=floor_plan_id, job_id=job_id, user=user):
                response = self._get(floor_plan_id, job_id, user=user)
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(response.json()["detail"]["error"]["code"], "REVIEW_IMAGE_NOT_FOUND")

        self.image_path.unlink()
        response = self._get(self.floor_plan.id, self.job.id, user="designer")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["error"]["code"], "REVIEW_IMAGE_NOT_FOUND")

    def test_invalid_identifiers_are_rejected(self) -> None:
        for floor_plan_id, job_id in (
            (0, 1),
            (-1, 1),
            ("1.5", 1),
            (1, 0),
            (1, -1),
            (1, "abc"),
            (1, 9_223_372_036_854_775_808),
            (1, None),
        ):
            with self.subTest(floor_plan_id=floor_plan_id, job_id=job_id):
                response = self._get(floor_plan_id, job_id, user="admin")
                self.assertEqual(response.status_code, 422)

    def test_invalid_image_variants_fail_safely(self) -> None:
        variants = (
            b"",
            b"not-a-png",
            _image_bytes(format="JPEG"),
            _image_bytes(mode="L"),
        )
        for content in variants:
            with self.subTest(size=len(content)):
                self.image_path.write_bytes(content)
                response = self._get(self.floor_plan.id, self.job.id, user="designer")
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json()["detail"]["error"]["code"], "REVIEW_IMAGE_UNAVAILABLE")

    def test_size_and_dimension_limits_fail_safely(self) -> None:
        with patch("app.services.review_image_service.MAXIMUM_REVIEW_IMAGE_BYTES", len(self.review_bytes) - 1):
            self.assertEqual(self._get(self.floor_plan.id, self.job.id, user="designer").status_code, 503)
        with patch("app.services.review_image_service.DEFAULT_MAXIMUM_DIMENSION", 79):
            self.assertEqual(self._get(self.floor_plan.id, self.job.id, user="designer").status_code, 503)

    def test_symlink_escape_is_rejected_where_supported(self) -> None:
        outside = self.root / "outside.png"
        outside.write_bytes(self.review_bytes)
        self.image_path.unlink()
        try:
            self.image_path.symlink_to(outside)
        except OSError:
            self.skipTest("Creating symlinks is not supported in this environment.")
        response = self._get(self.floor_plan.id, self.job.id, user="designer")
        self.assertEqual(response.status_code, 404, response.text)

    def test_endpoint_is_read_only_and_does_not_invoke_pipeline(self) -> None:
        guarded = (
            "app.services.image_normalization.normalize_image",
            "app.services.image_normalization.normalize_processing_job_image",
            "app.services.pdf_conversion.convert_pdf_page",
            "app.ai.preprocessing.pipeline.preprocess_image",
            "app.ai.wall_detection.detect_wall_lines",
            "app.ai.symbol_detection.run_symbol_inference",
        )
        patches = [patch(target, side_effect=AssertionError(target)) for target in guarded]
        for guard in patches:
            guard.start()
        try:
            with (
                patch.object(self.database_session, "commit", wraps=self.database_session.commit) as commit,
                patch.object(self.database_session, "flush", wraps=self.database_session.flush) as flush,
                patch.object(self.database_session, "rollback", wraps=self.database_session.rollback) as rollback,
            ):
                response = self._get(self.floor_plan.id, self.job.id, user="designer")
        finally:
            for guard in reversed(patches):
                guard.stop()
        self.assertEqual(response.status_code, 200, response.text)
        commit.assert_not_called()
        flush.assert_not_called()
        rollback.assert_not_called()
        self.assertEqual(hashlib.sha256(self.original_path.read_bytes()).hexdigest(), self.original_digest)

    def test_file_failure_is_sanitized(self) -> None:
        raw = "C:\\private\\secret.png password=hunter2 Traceback"
        with patch("pathlib.Path.read_bytes", side_effect=OSError(raw)):
            response = self._get(self.floor_plan.id, self.job.id, user="designer")
        self.assertEqual(response.status_code, 503)
        for forbidden in ("private", "secret", "hunter2", "traceback"):
            self.assertNotIn(forbidden, response.text.casefold())

    def test_openapi_and_schema_remain_stable(self) -> None:
        schema = self.application.openapi()
        route = schema["paths"][PATH.format(floor_plan_id="{floor_plan_id}")]["get"]
        self.assertIn("image/png", route["responses"]["200"]["content"])
        operations = {
            (method, path)
            for path, definition in schema["paths"].items()
            for method in definition
            if method in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(len(operations), 18)
        self.assertEqual(len(__import__("sqlalchemy").inspect(self.engine).get_table_names()), 11)


if __name__ == "__main__":
    unittest.main()
