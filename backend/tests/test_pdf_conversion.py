import builtins
import hashlib
import os
import shutil
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pypdfium2 as pdfium
from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from pypdf import PdfWriter

from app.core.config import (
    REPOSITORY_ROOT,
    ProcessedDirectoryConfigurationError,
    Settings,
    get_processed_directory,
)
from app.core.database import get_engine
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.services.pdf_conversion import (
    DEFAULT_PDF_DPI,
    ERROR_MESSAGES,
    PNG_MIME_TYPE,
    SAFE_PDF_CONVERSION_FAILURE_MESSAGE,
    PdfConversionError,
    _remove_partial_output,
    _resolve_original_pdf,
    convert_pdf_page,
    convert_processing_job_pdf,
)


def make_pdf(
    page_sizes=((72, 36),),
    *,
    encrypted=False,
    rotate_first_page=False,
) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for width, height in page_sizes:
        page = writer.add_blank_page(width=width, height=height)
        if rotate_first_page and len(writer.pages) == 1:
            page.rotate(90)
    if encrypted:
        writer.encrypt("synthetic-password")
    writer.write(output)
    return output.getvalue()


def write_original(upload_root: Path, name: str, content: bytes) -> Path:
    originals = upload_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    destination = originals / name
    destination.write_bytes(content)
    return destination


class PartialWriter:
    def __init__(self, destination: Path) -> None:
        self.destination = destination

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool:
        return False

    def write(self, content: bytes) -> int:
        with builtins.open(self.destination, "wb") as output:
            output.write(content[:8])
        raise OSError("private partial-write detail")


class ProcessedDirectoryConfigurationTests(unittest.TestCase):
    def make_settings(self, **overrides) -> Settings:
        values = {
            "_env_file": None,
            "upload_dir": Path("storage/uploads"),
            "processed_dir": Path("storage/processed"),
        }
        values.update(overrides)
        return Settings(**values)

    def test_relative_processed_directory_resolves_from_repository_root(self) -> None:
        result = get_processed_directory(self.make_settings())
        self.assertEqual(result, (REPOSITORY_ROOT / "storage/processed").resolve())

    def test_absolute_processed_directory_is_supported_without_creation(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "not-created"
            result = get_processed_directory(
                self.make_settings(processed_dir=destination)
            )
            self.assertEqual(result, destination.resolve())
            self.assertFalse(destination.exists())

    def test_missing_and_dot_processed_directories_are_rejected(self) -> None:
        for configured in (None, Path(".")):
            with self.subTest(configured=configured):
                with self.assertRaises(ProcessedDirectoryConfigurationError):
                    get_processed_directory(
                        self.make_settings(processed_dir=configured)
                    )

    def test_processed_directory_cannot_equal_or_descend_from_originals(self) -> None:
        for configured in (
            Path("storage/uploads/originals"),
            Path("storage/uploads/originals/derived"),
        ):
            with self.subTest(configured=configured):
                with self.assertRaises(ProcessedDirectoryConfigurationError) as caught:
                    get_processed_directory(
                        self.make_settings(processed_dir=configured)
                    )
                self.assertNotIn(str(REPOSITORY_ROOT), str(caught.exception))


class PdfConversionUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.upload_root = self.root / "uploads"
        self.processed_root = self.root / "processed"
        self.source = write_original(
            self.upload_root,
            "plan.pdf",
            make_pdf(),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def convert(self, **overrides):
        arguments = {
            "source_path": self.source,
            "processed_directory": self.processed_root,
            "floor_plan_id": 42,
            "processing_job_id": 123,
            "dpi": 72,
        }
        arguments.update(overrides)
        return convert_pdf_page(**arguments)

    def assert_error(self, code: str, callable_object) -> PdfConversionError:
        with self.assertRaises(PdfConversionError) as caught:
            callable_object()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.message, ERROR_MESSAGES[code])
        return caught.exception

    def test_valid_pdf_converts_to_openable_rgb_png(self) -> None:
        result = self.convert()
        self.assertTrue(result.absolute_output_path.is_file())
        self.assertEqual(result.mime_type, PNG_MIME_TYPE)
        self.assertEqual(result.output_byte_size, result.absolute_output_path.stat().st_size)
        with Image.open(result.absolute_output_path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (72, 36))

    def test_requested_dpi_controls_dimensions(self) -> None:
        result = self.convert(dpi=144)
        self.assertEqual((result.width, result.height, result.dpi), (144, 72, 144))

    def test_default_dpi_is_150(self) -> None:
        result = convert_pdf_page(
            source_path=self.source,
            processed_directory=self.processed_root,
            floor_plan_id=42,
            processing_job_id=123,
        )
        self.assertEqual(result.dpi, DEFAULT_PDF_DPI)
        self.assertEqual((result.width, result.height), (150, 75))

    def test_default_selects_first_page_and_selection_is_one_based(self) -> None:
        self.source.write_bytes(make_pdf(((72, 36), (36, 72))))
        first = self.convert()
        second = self.convert(processing_job_id=124, page_number=2)
        self.assertEqual((first.width, first.height, first.page_number), (72, 36, 1))
        self.assertEqual((second.width, second.height, second.page_number), (36, 72, 2))

    def test_effective_page_rotation_is_honored(self) -> None:
        self.source.write_bytes(make_pdf(rotate_first_page=True))
        result = self.convert()
        self.assertEqual((result.width, result.height), (36, 72))

    def test_zero_negative_and_boolean_page_numbers_fail(self) -> None:
        for page_number in (0, -1, True):
            with self.subTest(page_number=page_number):
                self.assert_error(
                    "INVALID_PAGE_NUMBER",
                    lambda value=page_number: self.convert(page_number=value),
                )

    def test_invalid_dpi_fails(self) -> None:
        for dpi in (0, -1, True):
            with self.subTest(dpi=dpi):
                self.assert_error(
                    "INVALID_DPI",
                    lambda value=dpi: self.convert(dpi=value),
                )

    def test_page_above_document_count_fails(self) -> None:
        self.assert_error("PAGE_OUT_OF_RANGE", lambda: self.convert(page_number=2))

    def test_output_reference_is_portable_and_has_expected_structure(self) -> None:
        result = self.convert(page_number=1)
        self.assertEqual(
            result.output_reference,
            "pdf-pages/floor-plan-42/job-123/page-0001.png",
        )
        self.assertNotIn("\\", result.output_reference)

    def test_output_remains_beneath_processed_and_outside_originals(self) -> None:
        result = self.convert()
        self.assertTrue(
            result.absolute_output_path.is_relative_to(self.processed_root.resolve())
        )
        self.assertFalse(
            result.absolute_output_path.is_relative_to(
                (self.upload_root / "originals").resolve()
            )
        )

    def test_original_pdf_hash_is_unchanged(self) -> None:
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.convert()
        after = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(after, before)

    def test_repeated_same_job_conversion_never_overwrites(self) -> None:
        first = self.convert()
        before = first.absolute_output_path.read_bytes()
        self.assert_error("OUTPUT_ALREADY_EXISTS", self.convert)
        self.assertEqual(first.absolute_output_path.read_bytes(), before)

    def test_separate_jobs_receive_separate_paths(self) -> None:
        first = self.convert()
        second = self.convert(processing_job_id=124)
        self.assertNotEqual(first.absolute_output_path, second.absolute_output_path)
        self.assertTrue(first.absolute_output_path.exists())
        self.assertTrue(second.absolute_output_path.exists())

    def test_malformed_and_encrypted_pdfs_fail_safely(self) -> None:
        cases = {
            "malformed": b"%PDF-1.7 private malformed content",
            "encrypted": make_pdf(encrypted=True),
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                self.source.write_bytes(content)
                caught = self.assert_error("PDF_OPEN_FAILED", self.convert)
                self.assertNotIn("private", caught.message.casefold())
                shutil.rmtree(self.processed_root, ignore_errors=True)

    def test_non_pdf_and_missing_inputs_are_rejected(self) -> None:
        non_pdf = self.source.with_suffix(".png")
        self.source.rename(non_pdf)
        self.assert_error(
            "UNSUPPORTED_SOURCE",
            lambda: self.convert(source_path=non_pdf),
        )
        self.assert_error(
            "SOURCE_UNAVAILABLE",
            lambda: self.convert(source_path=self.root / "missing.pdf"),
        )

    def test_unsafe_output_ids_are_rejected(self) -> None:
        for field, value in (("floor_plan_id", 0), ("processing_job_id", -1)):
            with self.subTest(field=field):
                self.assert_error(
                    "UNSAFE_OUTPUT_PATH",
                    lambda: self.convert(**{field: value}),
                )

    def test_excessive_dimensions_are_rejected_before_rendering(self) -> None:
        fake_page = MagicMock()
        fake_page.get_size.return_value = (100_000, 100_000)
        fake_document = MagicMock()
        fake_document.__len__.return_value = 1
        fake_document.__getitem__.return_value = fake_page
        with patch(
            "app.services.pdf_conversion.pdfium.PdfDocument",
            return_value=fake_document,
        ):
            self.assert_error("UNSAFE_RENDERED_DIMENSIONS", self.convert)
        fake_page.render.assert_not_called()

    def test_renderer_exception_is_sanitized(self) -> None:
        secret = "password=hunter2 C:\\private\\plan.pdf"
        with patch.object(pdfium.PdfPage, "render", side_effect=RuntimeError(secret)):
            caught = self.assert_error("PDF_RENDER_FAILED", self.convert)
        self.assertNotIn("hunter2", caught.message)
        self.assertFalse(any(self.processed_root.rglob("*.png")))

    def test_png_encoding_failure_is_sanitized(self) -> None:
        with patch.object(
            pdfium.PdfBitmap,
            "to_pil",
            side_effect=RuntimeError("private encoder detail"),
        ):
            caught = self.assert_error("PNG_ENCODING_FAILED", self.convert)
        self.assertNotIn("private", caught.message.casefold())

    def test_partial_write_is_removed(self) -> None:
        original_open = Path.open

        def selective_open(path, mode="r", *args, **kwargs):
            if path.suffix == ".png" and mode == "xb":
                return PartialWriter(path)
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", selective_open):
            self.assert_error("OUTPUT_WRITE_FAILED", self.convert)
        self.assertFalse(any(self.processed_root.rglob("*.png")))

    def test_cleanup_failure_has_stable_error(self) -> None:
        partial = self.root / "partial.png"
        partial.write_bytes(b"partial")
        with patch.object(Path, "unlink", side_effect=OSError("private cleanup")):
            self.assert_error(
                "OUTPUT_CLEANUP_FAILED",
                lambda: _remove_partial_output(partial),
            )

    def test_low_level_service_requires_no_fastapi_http_or_database_context(self) -> None:
        with patch(
            "app.core.database.get_engine",
            side_effect=AssertionError("database must not be used"),
        ):
            result = self.convert()
        self.assertTrue(result.absolute_output_path.exists())

    def test_source_resolver_rejects_traversal_and_absolute_references(self) -> None:
        for storage_path in (
            "originals/../outside.pdf",
            str(self.source.resolve()),
            "C:\\private\\plan.pdf",
        ):
            floor_plan = SimpleNamespace(
                storage_path=storage_path,
                mime_type="application/pdf",
            )
            with self.subTest(storage_path=storage_path):
                self.assert_error(
                    "UNSAFE_SOURCE_PATH",
                    lambda plan=floor_plan: _resolve_original_pdf(
                        upload_directory=self.upload_root,
                        floor_plan=plan,
                    ),
                )

    def test_source_resolver_rejects_non_pdf_metadata(self) -> None:
        floor_plan = SimpleNamespace(
            storage_path="originals/plan.pdf",
            mime_type="image/png",
        )
        self.assert_error(
            "UNSUPPORTED_SOURCE",
            lambda: _resolve_original_pdf(
                upload_directory=self.upload_root,
                floor_plan=floor_plan,
            ),
        )

    def test_source_resolver_rejects_symlink_escape_where_supported(self) -> None:
        outside = self.root / "outside.pdf"
        outside.write_bytes(make_pdf())
        link = self.upload_root / "originals" / "linked.pdf"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("File symlinks are unavailable in this environment.")
        floor_plan = SimpleNamespace(
            storage_path="originals/linked.pdf",
            mime_type="application/pdf",
        )
        self.assert_error(
            "UNSAFE_SOURCE_PATH",
            lambda: _resolve_original_pdf(
                upload_directory=self.upload_root,
                floor_plan=floor_plan,
            ),
        )

    def test_missing_resolved_original_fails_safely(self) -> None:
        floor_plan = SimpleNamespace(
            storage_path="originals/missing.pdf",
            mime_type="application/pdf",
        )
        self.assert_error(
            "SOURCE_UNAVAILABLE",
            lambda: _resolve_original_pdf(
                upload_directory=self.upload_root,
                floor_plan=floor_plan,
            ),
        )


class PdfConversionMySqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.temporary = TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.upload_root = cls.root / "uploads"
        cls.processed_root = cls.root / "processed"
        cls.valid_bytes = make_pdf()
        cls.valid_path = write_original(cls.upload_root, "valid.pdf", cls.valid_bytes)
        cls.corrupt_path = write_original(cls.upload_root, "corrupt.pdf", b"not a pdf")
        cls.session = Session(cls.engine, expire_on_commit=False)

        with Session(cls.engine) as snapshot_session:
            cls.preexisting_floor_plan_count = snapshot_session.scalar(
                select(func.count()).select_from(FloorPlan)
            )
            cls.preexisting_job_count = snapshot_session.scalar(
                select(func.count()).select_from(ProcessingJob)
            )

        designer_role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        if designer_role is None:
            raise RuntimeError("The DESIGNER seed role is required.")
        marker = uuid4().hex
        cls.user = User(
            oauth_provider=f"g1-test-{marker}",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="G1 Designer",
            role_id=designer_role.id,
        )
        cls.project = Project(owner=cls.user, name=f"G1 Project {marker}")
        cls.project_floor = ProjectFloor(
            project=cls.project,
            name="Ground Floor",
            sort_order=0,
        )
        cls.valid_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="valid.pdf",
            storage_path="originals/valid.pdf",
            mime_type="application/pdf",
            file_size=len(cls.valid_bytes),
            processing_status="uploaded",
        )
        cls.corrupt_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="corrupt.pdf",
            storage_path="originals/corrupt.pdf",
            mime_type="application/pdf",
            file_size=cls.corrupt_path.stat().st_size,
            processing_status="uploaded",
        )
        cls.session.add_all((cls.valid_plan, cls.corrupt_plan))
        cls.session.commit()
        cls.floor_plan_ids = (cls.valid_plan.id, cls.corrupt_plan.id)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.session.rollback()
            cls.session.execute(
                delete(ProcessingJob).where(
                    ProcessingJob.floor_plan_id.in_(cls.floor_plan_ids)
                )
            )
            cls.session.execute(
                delete(FloorPlan).where(FloorPlan.id.in_(cls.floor_plan_ids))
            )
            cls.session.delete(cls.project_floor)
            cls.session.delete(cls.project)
            cls.session.delete(cls.user)
            cls.session.commit()
        finally:
            cls.session.close()

        if cls.valid_path.read_bytes() != cls.valid_bytes:
            raise AssertionError("The G1 original PDF was modified.")
        cls.temporary.cleanup()

        with Session(cls.engine) as verification_session:
            floor_plan_count = verification_session.scalar(
                select(func.count()).select_from(FloorPlan)
            )
            job_count = verification_session.scalar(
                select(func.count()).select_from(ProcessingJob)
            )
        if floor_plan_count != cls.preexisting_floor_plan_count:
            raise AssertionError("G1 leaked floor-plan test records.")
        if job_count != cls.preexisting_job_count:
            raise AssertionError("G1 leaked processing-job test records.")

    def setUp(self) -> None:
        self.session.rollback()
        self.session.execute(
            delete(ProcessingJob).where(
                ProcessingJob.floor_plan_id.in_(self.floor_plan_ids)
            )
        )
        self.session.commit()
        shutil.rmtree(self.processed_root, ignore_errors=True)
        self.job = ProcessingJob(
            floor_plan_id=self.valid_plan.id,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
        )
        self.session.add(self.job)
        self.session.commit()

    def convert(self, *, floor_plan=None, processing_job=None):
        return convert_processing_job_pdf(
            self.session,
            processing_job=processing_job or self.job,
            floor_plan=floor_plan or self.valid_plan,
            upload_directory=self.upload_root,
            processed_directory=self.processed_root,
            dpi=72,
        )

    def test_valid_job_becomes_processing_and_creates_png(self) -> None:
        result = self.convert()
        with Session(self.engine) as reload_session:
            reloaded = reload_session.get(ProcessingJob, self.job.id)
            self.assertEqual(reloaded.status, "processing")
            self.assertIsNone(reloaded.error_message)
            self.assertNotEqual(reloaded.status, "completed")
        self.assertTrue(result.absolute_output_path.is_file())

    def test_success_preserves_original_and_floor_plan_metadata(self) -> None:
        original_hash = hashlib.sha256(self.valid_path.read_bytes()).hexdigest()
        before = (
            self.valid_plan.original_filename,
            self.valid_plan.storage_path,
            self.valid_plan.mime_type,
            self.valid_plan.file_size,
            self.valid_plan.processing_status,
        )
        self.convert()
        self.session.refresh(self.valid_plan)
        after = (
            self.valid_plan.original_filename,
            self.valid_plan.storage_path,
            self.valid_plan.mime_type,
            self.valid_plan.file_size,
            self.valid_plan.processing_status,
        )
        self.assertEqual(after, before)
        self.assertEqual(
            hashlib.sha256(self.valid_path.read_bytes()).hexdigest(),
            original_hash,
        )

    def test_corrupt_pdf_persists_only_safe_failed_state(self) -> None:
        corrupt_job = ProcessingJob(
            floor_plan_id=self.corrupt_plan.id,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
        )
        self.session.add(corrupt_job)
        self.session.commit()
        with self.assertRaises(PdfConversionError):
            self.convert(floor_plan=self.corrupt_plan, processing_job=corrupt_job)
        with Session(self.engine) as reload_session:
            reloaded = reload_session.get(ProcessingJob, corrupt_job.id)
            self.assertEqual(reloaded.status, "failed")
            self.assertEqual(
                reloaded.error_message,
                SAFE_PDF_CONVERSION_FAILURE_MESSAGE,
            )
            for forbidden in ("pdfium", "traceback", "private", "select"):
                self.assertNotIn(forbidden, reloaded.error_message.casefold())
        self.assertFalse(any(self.processed_root.rglob("*.png")))

    def test_terminal_or_mismatched_jobs_are_rejected_without_changes(self) -> None:
        cases = (
            {"status": "completed"},
            {"status": "failed"},
            {"status": "cancelled"},
            {"job_type": "other"},
            {"floor_plan_id": self.corrupt_plan.id},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.session.refresh(self.job)
                self.job.status = "queued"
                self.job.job_type = "floor_plan_analysis"
                self.job.floor_plan_id = self.valid_plan.id
                for field, value in changes.items():
                    setattr(self.job, field, value)
                self.session.commit()
                with self.assertRaises(PdfConversionError) as caught:
                    self.convert()
                self.assertEqual(caught.exception.code, "PROCESSING_JOB_INVALID")
                self.session.refresh(self.job)
                self.assertEqual(self.job.status, changes.get("status", "queued"))

    def test_start_state_persistence_failure_is_sanitized(self) -> None:
        fake_session = MagicMock(spec=Session)
        fake_session.commit.side_effect = RuntimeError("password=hunter2 SELECT")
        fake_job = SimpleNamespace(
            id=1,
            floor_plan_id=1,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
            error_message=None,
        )
        fake_plan = SimpleNamespace(id=1)
        with self.assertRaises(PdfConversionError) as caught:
            convert_processing_job_pdf(
                fake_session,
                processing_job=fake_job,
                floor_plan=fake_plan,
                upload_directory=self.upload_root,
                processed_directory=self.processed_root,
            )
        self.assertEqual(
            caught.exception.code,
            "PROCESSING_JOB_STATE_PERSISTENCE_FAILED",
        )
        self.assertNotIn("hunter2", caught.exception.message)
        fake_session.rollback.assert_called_once()

    def test_failure_state_persistence_failure_is_sanitized(self) -> None:
        fake_session = MagicMock(spec=Session)
        fake_session.commit.side_effect = (
            None,
            RuntimeError("password=hunter2 SELECT private_table"),
        )
        fake_job = SimpleNamespace(
            id=1,
            floor_plan_id=1,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
            error_message=None,
        )
        fake_plan = SimpleNamespace(
            id=1,
            storage_path="originals/missing.pdf",
            mime_type="application/pdf",
        )
        with self.assertRaises(PdfConversionError) as caught:
            convert_processing_job_pdf(
                fake_session,
                processing_job=fake_job,
                floor_plan=fake_plan,
                upload_directory=self.upload_root,
                processed_directory=self.processed_root,
            )
        self.assertEqual(
            caught.exception.code,
            "PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED",
        )
        self.assertNotIn("hunter2", caught.exception.message)
        fake_session.rollback.assert_called_once()

    def test_job_ids_must_match_floor_plan(self) -> None:
        self.job.floor_plan_id = self.corrupt_plan.id
        self.session.commit()
        with self.assertRaises(PdfConversionError) as caught:
            self.convert()
        self.assertEqual(caught.exception.code, "PROCESSING_JOB_INVALID")

    def test_no_database_path_reference_is_persisted(self) -> None:
        result = self.convert()
        with Session(self.engine) as reload_session:
            reloaded = reload_session.get(ProcessingJob, self.job.id)
            values = (
                reloaded.job_type,
                reloaded.status,
                reloaded.error_message,
            )
        self.assertFalse(any(result.output_reference in (value or "") for value in values))


if __name__ == "__main__":
    unittest.main()
