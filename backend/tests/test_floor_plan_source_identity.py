import hashlib
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.models import FloorPlanPage, FloorPlanSource, Project, ProjectFloor, Role, User
from app.services.floor_plan_storage import FloorPlanStorageError, store_floor_plan_upload
from app.services.source_identity import SourceIdentityError, resolve_stored_original


def make_png() -> bytes:
    output = BytesIO()
    with Image.new("RGB", (12, 8), color="white") as image:
        image.save(output, format="PNG")
    return output.getvalue()


def make_pdf(page_count: int) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


class FloorPlanSourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.session = Session(bind=cls.connection, expire_on_commit=False)
        designer = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        if designer is None:
            raise unittest.SkipTest("The DESIGNER seed role is required.")
        marker = uuid4().hex
        user = User(oauth_provider="pre4-test", oauth_subject=marker, role=designer)
        project = Project(owner=user, name=f"PRE4 {marker}")
        cls.floor = ProjectFloor(project=project, name="Ground")
        cls.session.add(cls.floor)
        cls.session.flush()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.upload_directory = Path(self.temporary_directory.name) / "uploads"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def store(self, filename: str, mime_type: str, content: bytes):
        return store_floor_plan_upload(
            self.session,
            project_floor_id=self.floor.id,
            filename=filename,
            declared_mime_type=mime_type,
            content=content,
            upload_directory=self.upload_directory,
            max_file_size_bytes=len(content),
        )

    def test_live_tables_constraints_indexes_and_relationships_match(self) -> None:
        inspector = inspect(get_engine())
        self.assertIn("floor_plan_sources", inspector.get_table_names())
        self.assertIn("floor_plan_pages", inspector.get_table_names())
        self.assertEqual(len(inspector.get_table_names()), 19)
        self.assertIn(
            "ck_floor_plan_sources_sha256_length",
            {item["name"] for item in inspector.get_check_constraints("floor_plan_sources")},
        )
        self.assertIn(
            "ck_floor_plan_pages_number_positive",
            {item["name"] for item in inspector.get_check_constraints("floor_plan_pages")},
        )
        self.assertIn(
            "uq_floor_plan_pages_source_number",
            {item["name"] for item in inspector.get_unique_constraints("floor_plan_pages")},
        )
        self.assertEqual(len(inspector.get_foreign_keys("floor_plan_sources")), 1)
        self.assertEqual(len(inspector.get_foreign_keys("floor_plan_pages")), 1)

    def test_raster_upload_persists_hash_and_exactly_one_page(self) -> None:
        content = make_png()
        floor_plan = self.store("plan.png", "image/png", content)
        source = self.session.scalar(
            select(FloorPlanSource).where(FloorPlanSource.floor_plan_id == floor_plan.id)
        )
        self.assertIsNotNone(source)
        self.assertEqual(source.original_sha256, hashlib.sha256(content).hexdigest())
        pages = self.session.scalars(
            select(FloorPlanPage).where(FloorPlanPage.floor_plan_source_id == source.id)
        ).all()
        self.assertEqual([page.page_number for page in pages], [1])

    def test_pdf_upload_persists_one_based_page_identity_only(self) -> None:
        floor_plan = self.store("plan.pdf", "application/pdf", make_pdf(3))
        source = self.session.scalar(
            select(FloorPlanSource).where(FloorPlanSource.floor_plan_id == floor_plan.id)
        )
        pages = self.session.scalars(
            select(FloorPlanPage)
            .where(FloorPlanPage.floor_plan_source_id == source.id)
            .order_by(FloorPlanPage.page_number)
        ).all()
        self.assertEqual([page.page_number for page in pages], [1, 2, 3])
        self.assertEqual(set(FloorPlanPage.__table__.columns.keys()), {"id", "floor_plan_source_id", "page_number"})

    def test_source_failure_rolls_back_rows_and_compensates_new_file(self) -> None:
        from unittest.mock import patch

        content = make_png()
        before = set(self.upload_directory.rglob("*")) if self.upload_directory.exists() else set()
        with patch(
            "app.services.floor_plan_storage.persist_source_identity",
            side_effect=RuntimeError("synthetic source failure"),
        ):
            with self.assertRaises(FloorPlanStorageError) as captured:
                self.store("failed.png", "image/png", content)
        self.assertEqual(captured.exception.code, "FLOOR_PLAN_RECORD_FAILED")
        remaining_files = {path for path in self.upload_directory.rglob("*") if path.is_file()}
        self.assertEqual(remaining_files, {path for path in before if path.is_file()})

    def test_storage_resolution_rejects_non_original_and_traversal_paths(self) -> None:
        self.upload_directory.mkdir()
        for unsafe in ("../private.png", "processed/file.png", "/absolute.png"):
            with self.assertRaises(SourceIdentityError):
                resolve_stored_original(self.upload_directory, unsafe)


if __name__ == "__main__":
    unittest.main()
