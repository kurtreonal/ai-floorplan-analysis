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

from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from pypdf import PdfWriter

from app.core.database import get_engine
from app.models import FloorPlan, ProcessingJob, Project, ProjectFloor, Role, User
from app.services.image_normalization import (
    DEFAULT_MAXIMUM_DIMENSION,
    ERROR_MESSAGES,
    SAFE_NORMALIZATION_FAILURE_MESSAGE,
    ImageNormalizationError,
    _g1_reference_and_path,
    _remove_partial_output,
    _resolve_uploaded_raster,
    normalize_image,
    normalize_processing_job_image,
)
from app.services.pdf_conversion import convert_pdf_page


def make_image(
    image_format: str,
    size=(32, 20),
    *,
    mode="RGB",
    color=None,
    orientation=None,
) -> bytes:
    output = BytesIO()
    if color is None:
        color = 128 if mode == "L" else (25, 50, 75)
    image = Image.new(mode, size, color)
    try:
        save_options = {}
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            save_options["exif"] = exif
        image.save(output, format=image_format, **save_options)
    finally:
        image.close()
    return output.getvalue()


def make_transparent_png() -> bytes:
    output = BytesIO()
    image = Image.new("RGBA", (2, 1), (255, 0, 0, 0))
    image.putpixel((1, 0), (0, 0, 255, 255))
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def make_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=36)
    writer.write(output)
    return output.getvalue()


def write_file(root: Path, reference: str, content: bytes) -> Path:
    destination = root.joinpath(*reference.split("/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
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


class ImageNormalizationUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.upload_root = self.root / "uploads"
        self.processed_root = self.root / "processed"
        self.jpeg = write_file(
            self.upload_root,
            "originals/plan.jpg",
            make_image("JPEG"),
        )
        self.png = write_file(
            self.upload_root,
            "originals/plan.png",
            make_image("PNG"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def normalize(self, **overrides):
        arguments = {
            "source_path": self.png,
            "source_mime_type": "image/png",
            "processed_directory": self.processed_root,
            "floor_plan_id": 42,
            "processing_job_id": 123,
            "maximum_dimension": 4096,
        }
        arguments.update(overrides)
        return normalize_image(**arguments)

    def assert_error(self, code: str, callable_object) -> ImageNormalizationError:
        with self.assertRaises(ImageNormalizationError) as caught:
            callable_object()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.message, ERROR_MESSAGES[code])
        return caught.exception

    def test_valid_jpeg_and_png_become_rgb_png(self) -> None:
        cases = (
            (self.jpeg, "image/jpeg", 123),
            (self.png, "image/png", 124),
        )
        for source, mime_type, job_id in cases:
            with self.subTest(mime_type=mime_type):
                result = self.normalize(
                    source_path=source,
                    source_mime_type=mime_type,
                    processing_job_id=job_id,
                )
                with Image.open(result.absolute_output_path) as output:
                    self.assertEqual(output.format, "PNG")
                    self.assertEqual(output.mode, "RGB")
                    self.assertEqual(output.size, (32, 20))

    def test_actual_g1_pdf_page_can_be_normalized_without_modification(self) -> None:
        pdf = write_file(self.upload_root, "originals/plan.pdf", make_pdf())
        g1 = convert_pdf_page(
            source_path=pdf,
            processed_directory=self.processed_root,
            floor_plan_id=42,
            processing_job_id=123,
            dpi=72,
        )
        before = hashlib.sha256(g1.absolute_output_path.read_bytes()).hexdigest()
        result = self.normalize(source_path=g1.absolute_output_path)
        after = hashlib.sha256(g1.absolute_output_path.read_bytes()).hexdigest()
        self.assertEqual(after, before)
        self.assertEqual((result.normalized_width, result.normalized_height), (72, 36))

    def test_uppercase_supported_extension_is_accepted(self) -> None:
        uppercase = self.png.with_name("PLAN.PNG")
        self.png.rename(uppercase)
        result = self.normalize(source_path=uppercase)
        self.assertTrue(result.absolute_output_path.exists())

    def test_exif_orientation_swaps_dimensions_and_is_recorded(self) -> None:
        oriented = write_file(
            self.upload_root,
            "originals/oriented.jpg",
            make_image("JPEG", (40, 20), orientation=6),
        )
        result = self.normalize(
            source_path=oriented,
            source_mime_type="image/jpeg",
        )
        self.assertEqual((result.encoded_source_width, result.encoded_source_height), (40, 20))
        self.assertEqual((result.oriented_width, result.oriented_height), (20, 40))
        self.assertEqual((result.normalized_width, result.normalized_height), (20, 40))
        self.assertTrue(result.orientation_corrected)

    def test_image_without_orientation_is_not_rotated(self) -> None:
        result = self.normalize()
        self.assertFalse(result.orientation_corrected)
        self.assertEqual((result.oriented_width, result.oriented_height), (32, 20))

    def test_cmyk_jpeg_and_grayscale_png_become_rgb(self) -> None:
        cmyk = write_file(
            self.upload_root,
            "originals/cmyk.jpg",
            make_image("JPEG", mode="CMYK", color=(10, 20, 30, 0)),
        )
        grayscale = write_file(
            self.upload_root,
            "originals/gray.png",
            make_image("PNG", mode="L"),
        )
        for source, mime_type, job_id in (
            (cmyk, "image/jpeg", 123),
            (grayscale, "image/png", 124),
        ):
            with self.subTest(source=source.name):
                result = self.normalize(
                    source_path=source,
                    source_mime_type=mime_type,
                    processing_job_id=job_id,
                )
                with Image.open(result.absolute_output_path) as output:
                    self.assertEqual(output.mode, "RGB")

    def test_transparency_is_composited_on_white(self) -> None:
        transparent = write_file(
            self.upload_root,
            "originals/transparent.png",
            make_transparent_png(),
        )
        result = self.normalize(source_path=transparent)
        with Image.open(result.absolute_output_path) as output:
            self.assertEqual(output.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(output.getpixel((1, 0)), (0, 0, 255))

    def test_small_images_are_not_upscaled(self) -> None:
        result = self.normalize(maximum_dimension=4096)
        self.assertFalse(result.resized)
        self.assertEqual((result.normalized_width, result.normalized_height), (32, 20))

    def test_long_edge_over_limit_is_reduced_with_aspect_ratio(self) -> None:
        large = write_file(
            self.upload_root,
            "originals/large.png",
            make_image("PNG", (4100, 100)),
        )
        result = self.normalize(source_path=large)
        self.assertTrue(result.resized)
        self.assertEqual(result.normalized_width, DEFAULT_MAXIMUM_DIMENSION)
        self.assertEqual(result.normalized_height, 100)

    def test_exact_limit_is_not_resized(self) -> None:
        exact = write_file(
            self.upload_root,
            "originals/exact.png",
            make_image("PNG", (4096, 4)),
        )
        result = self.normalize(source_path=exact)
        self.assertFalse(result.resized)
        self.assertEqual(result.normalized_width, 4096)

    def test_internal_limit_override_is_honored(self) -> None:
        result = self.normalize(maximum_dimension=16)
        self.assertTrue(result.resized)
        self.assertEqual((result.normalized_width, result.normalized_height), (16, 10))

    def test_invalid_limits_and_identifiers_are_rejected(self) -> None:
        for field, value, code in (
            ("maximum_dimension", 0, "INVALID_MAXIMUM_DIMENSION"),
            ("maximum_dimension", -1, "INVALID_MAXIMUM_DIMENSION"),
            ("maximum_dimension", True, "INVALID_MAXIMUM_DIMENSION"),
            ("floor_plan_id", 0, "INVALID_IDENTIFIERS"),
            ("processing_job_id", False, "INVALID_IDENTIFIERS"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_error(code, lambda f=field, v=value: self.normalize(**{f: v}))

    def test_unsafe_pixel_count_is_rejected_before_load(self) -> None:
        fake = MagicMock()
        fake.format = "PNG"
        fake.size = (20_000, 20_000)
        with patch("app.services.image_normalization.Image.open", return_value=fake):
            self.assert_error("UNSAFE_SOURCE_DIMENSIONS", self.normalize)
        fake.load.assert_not_called()

    def test_exact_output_reference_and_result_metadata(self) -> None:
        result = self.normalize()
        self.assertEqual(
            result.output_reference,
            "normalized/floor-plan-42/job-123/image.png",
        )
        self.assertNotIn("\\", result.output_reference)
        self.assertEqual(result.source_mime_type, "image/png")
        self.assertEqual(result.output_mime_type, "image/png")
        self.assertEqual(result.output_byte_size, result.absolute_output_path.stat().st_size)

    def test_original_hash_is_unchanged_and_output_is_separate(self) -> None:
        before = hashlib.sha256(self.png.read_bytes()).hexdigest()
        result = self.normalize()
        self.assertEqual(hashlib.sha256(self.png.read_bytes()).hexdigest(), before)
        self.assertTrue(result.absolute_output_path.is_relative_to(self.processed_root.resolve()))
        self.assertFalse(result.absolute_output_path.is_relative_to(self.upload_root.resolve()))

    def test_output_drops_source_exif_metadata(self) -> None:
        oriented = write_file(
            self.upload_root,
            "originals/metadata.jpg",
            make_image("JPEG", orientation=3),
        )
        result = self.normalize(
            source_path=oriented,
            source_mime_type="image/jpeg",
        )
        with Image.open(result.absolute_output_path) as output:
            self.assertEqual(len(output.getexif()), 0)

    def test_repeated_normalization_never_overwrites(self) -> None:
        first = self.normalize()
        before = first.absolute_output_path.read_bytes()
        self.assert_error("OUTPUT_ALREADY_EXISTS", self.normalize)
        self.assertEqual(first.absolute_output_path.read_bytes(), before)

    def test_separate_jobs_receive_separate_directories(self) -> None:
        first = self.normalize()
        second = self.normalize(processing_job_id=124)
        self.assertNotEqual(first.absolute_output_path, second.absolute_output_path)

    def test_partial_write_is_removed(self) -> None:
        original_open = Path.open

        def selective_open(path, mode="r", *args, **kwargs):
            if path.suffix == ".png" and mode == "xb":
                return PartialWriter(path)
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", selective_open):
            self.assert_error("OUTPUT_WRITE_FAILED", self.normalize)
        self.assertFalse(any(self.processed_root.rglob("image.png")))

    def test_cleanup_failure_uses_stable_error(self) -> None:
        partial = self.root / "partial.png"
        partial.write_bytes(b"partial")
        with patch.object(Path, "unlink", side_effect=OSError("private cleanup")):
            self.assert_error(
                "OUTPUT_CLEANUP_FAILED",
                lambda: _remove_partial_output(partial),
            )

    def test_corrupt_truncated_and_disguised_content_fail_safely(self) -> None:
        valid = make_image("PNG")
        cases = (
            ("corrupt.jpg", b"not an image", "image/jpeg", "CORRUPT_SOURCE"),
            ("truncated.png", valid[:20], "image/png", "CORRUPT_SOURCE"),
            ("disguised.jpg", valid, "image/jpeg", "UNSUPPORTED_SOURCE"),
        )
        for name, content, mime_type, code in cases:
            source = write_file(self.upload_root, f"originals/{name}", content)
            with self.subTest(name=name):
                self.assert_error(
                    code,
                    lambda s=source, m=mime_type: self.normalize(
                        source_path=s,
                        source_mime_type=m,
                    ),
                )
                shutil.rmtree(self.processed_root, ignore_errors=True)

    def test_extension_and_mime_mismatches_fail(self) -> None:
        self.assert_error(
            "UNSUPPORTED_SOURCE",
            lambda: self.normalize(
                source_path=self.png,
                source_mime_type="image/jpeg",
            ),
        )
        self.assert_error(
            "UNSUPPORTED_SOURCE",
            lambda: self.normalize(source_mime_type="application/pdf"),
        )

    def test_missing_source_fails_safely(self) -> None:
        self.assert_error(
            "SOURCE_UNAVAILABLE",
            lambda: self.normalize(source_path=self.root / "missing.png"),
        )

    def test_decompression_bomb_failure_is_sanitized(self) -> None:
        with patch(
            "app.services.image_normalization.Image.open",
            side_effect=Image.DecompressionBombError("private dimensions"),
        ):
            caught = self.assert_error("UNSAFE_SOURCE_DIMENSIONS", self.normalize)
        self.assertNotIn("private", caught.message)

    def test_orientation_resize_and_encoder_failures_are_sanitized(self) -> None:
        cases = (
            (
                "ORIENTATION_FAILED",
                patch(
                    "app.services.image_normalization.ImageOps.exif_transpose",
                    side_effect=RuntimeError("private orientation"),
                ),
                {},
            ),
            (
                "RESIZE_FAILED",
                patch.object(
                    Image.Image,
                    "resize",
                    side_effect=RuntimeError("private resize"),
                ),
                {"maximum_dimension": 16},
            ),
            (
                "ENCODE_FAILED",
                patch.object(
                    Image.Image,
                    "save",
                    side_effect=RuntimeError("private encoder"),
                ),
                {},
            ),
        )
        for code, active_patch, arguments in cases:
            with self.subTest(code=code), active_patch:
                caught = self.assert_error(code, lambda: self.normalize(**arguments))
                self.assertNotIn("private", caught.message)

    def test_empty_encoder_output_is_rejected(self) -> None:
        with patch.object(Image.Image, "save", return_value=None):
            self.assert_error("ENCODE_FAILED", self.normalize)

    def test_uploaded_source_traversal_absolute_and_symlink_escape_fail(self) -> None:
        base = {
            "mime_type": "image/png",
            "storage_path": "originals/plan.png",
        }
        for storage_path in (
            "originals/../outside.png",
            str(self.png.resolve()),
            "C:\\private\\plan.png",
        ):
            plan = SimpleNamespace(**{**base, "storage_path": storage_path})
            with self.subTest(storage_path=storage_path):
                self.assert_error(
                    "UNSAFE_SOURCE_PATH",
                    lambda p=plan: _resolve_uploaded_raster(
                        upload_directory=self.upload_root,
                        floor_plan=p,
                    ),
                )

        outside = self.root / "outside.png"
        outside.write_bytes(make_image("PNG"))
        link = self.upload_root / "originals" / "linked.png"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            return
        plan = SimpleNamespace(mime_type="image/png", storage_path="originals/linked.png")
        self.assert_error(
            "UNSAFE_SOURCE_PATH",
            lambda: _resolve_uploaded_raster(
                upload_directory=self.upload_root,
                floor_plan=plan,
            ),
        )

    def test_g1_reference_rejects_traversal_absolute_and_mismatched_ids(self) -> None:
        references = (
            "../pdf-pages/floor-plan-42/job-123/page-0001.png",
            str(self.png.resolve()),
            "pdf-pages/floor-plan-41/job-123/page-0001.png",
            "pdf-pages/floor-plan-42/job-124/page-0001.png",
        )
        for reference in references:
            with self.subTest(reference=reference):
                self.assert_error(
                    "G1_RESULT_MISMATCH",
                    lambda value=reference: _g1_reference_and_path(
                        value,
                        processed_directory=self.processed_root,
                        floor_plan_id=42,
                        processing_job_id=123,
                    ),
                )

    def test_low_level_service_needs_no_http_fastapi_or_database(self) -> None:
        with patch(
            "app.core.database.get_engine",
            side_effect=AssertionError("database must not be used"),
        ):
            result = self.normalize()
        self.assertTrue(result.absolute_output_path.exists())


class ImageNormalizationMySqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = get_engine()
        cls.temporary = TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.upload_root = cls.root / "uploads"
        cls.processed_root = cls.root / "processed"
        cls.valid_bytes = make_image("PNG")
        cls.valid_path = write_file(
            cls.upload_root,
            "originals/valid.png",
            cls.valid_bytes,
        )
        cls.corrupt_path = write_file(
            cls.upload_root,
            "originals/corrupt.png",
            b"not a png",
        )
        cls.pdf_bytes = make_pdf()
        cls.pdf_path = write_file(
            cls.upload_root,
            "originals/valid.pdf",
            cls.pdf_bytes,
        )
        cls.session = Session(cls.engine, expire_on_commit=False)
        with Session(cls.engine) as snapshot:
            cls.preexisting_floor_plans = snapshot.scalar(
                select(func.count()).select_from(FloorPlan)
            )
            cls.preexisting_jobs = snapshot.scalar(
                select(func.count()).select_from(ProcessingJob)
            )

        designer_role = cls.session.scalar(select(Role).where(Role.name == "DESIGNER"))
        if designer_role is None:
            raise RuntimeError("The DESIGNER seed role is required.")
        marker = uuid4().hex
        cls.user = User(
            oauth_provider=f"g2-test-{marker}",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="G2 Designer",
            role_id=designer_role.id,
        )
        cls.project = Project(owner=cls.user, name=f"G2 Project {marker}")
        cls.project_floor = ProjectFloor(
            project=cls.project,
            name="Ground Floor",
            sort_order=0,
        )
        cls.valid_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="valid.png",
            storage_path="originals/valid.png",
            mime_type="image/png",
            file_size=len(cls.valid_bytes),
            processing_status="uploaded",
        )
        cls.corrupt_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="corrupt.png",
            storage_path="originals/corrupt.png",
            mime_type="image/png",
            file_size=cls.corrupt_path.stat().st_size,
            processing_status="uploaded",
        )
        cls.pdf_plan = FloorPlan(
            project_floor=cls.project_floor,
            original_filename="valid.pdf",
            storage_path="originals/valid.pdf",
            mime_type="application/pdf",
            file_size=len(cls.pdf_bytes),
            processing_status="uploaded",
        )
        cls.session.add_all((cls.valid_plan, cls.corrupt_plan, cls.pdf_plan))
        cls.session.commit()
        cls.floor_plan_ids = (
            cls.valid_plan.id,
            cls.corrupt_plan.id,
            cls.pdf_plan.id,
        )

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
            raise AssertionError("The G2 original was modified.")
        cls.temporary.cleanup()
        with Session(cls.engine) as verification:
            floor_plan_count = verification.scalar(
                select(func.count()).select_from(FloorPlan)
            )
            job_count = verification.scalar(
                select(func.count()).select_from(ProcessingJob)
            )
        if floor_plan_count != cls.preexisting_floor_plans:
            raise AssertionError("G2 leaked floor-plan records.")
        if job_count != cls.preexisting_jobs:
            raise AssertionError("G2 leaked processing-job records.")

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
            progress=17,
            error_message="obsolete safe message",
        )
        self.session.add(self.job)
        self.session.commit()

    def normalize(self, *, floor_plan=None, processing_job=None, **overrides):
        return normalize_processing_job_image(
            self.session,
            processing_job=processing_job or self.job,
            floor_plan=floor_plan or self.valid_plan,
            upload_directory=self.upload_root,
            processed_directory=self.processed_root,
            **overrides,
        )

    def test_queued_job_becomes_and_remains_processing_with_progress(self) -> None:
        result = self.normalize()
        with Session(self.engine) as reload_session:
            job = reload_session.get(ProcessingJob, self.job.id)
            self.assertEqual(job.status, "processing")
            self.assertEqual(job.progress, 17)
            self.assertIsNone(job.error_message)
            self.assertNotEqual(job.status, "completed")
        self.assertTrue(result.absolute_output_path.exists())

    def test_already_processing_job_is_accepted(self) -> None:
        self.job.status = "processing"
        self.session.commit()
        self.normalize()
        self.session.refresh(self.job)
        self.assertEqual(self.job.status, "processing")
        self.assertEqual(self.job.progress, 17)

    def test_success_preserves_original_and_floor_plan_metadata(self) -> None:
        before_hash = hashlib.sha256(self.valid_path.read_bytes()).hexdigest()
        before = (
            self.valid_plan.original_filename,
            self.valid_plan.storage_path,
            self.valid_plan.mime_type,
            self.valid_plan.file_size,
            self.valid_plan.processing_status,
        )
        result = self.normalize()
        self.session.refresh(self.valid_plan)
        after = (
            self.valid_plan.original_filename,
            self.valid_plan.storage_path,
            self.valid_plan.mime_type,
            self.valid_plan.file_size,
            self.valid_plan.processing_status,
        )
        self.assertEqual(after, before)
        self.assertEqual(hashlib.sha256(self.valid_path.read_bytes()).hexdigest(), before_hash)
        values = (self.job.job_type, self.job.status, self.job.error_message)
        self.assertFalse(any(result.output_reference in (value or "") for value in values))

    def test_database_wrapper_accepts_actual_g1_result(self) -> None:
        pdf_job = ProcessingJob(
            floor_plan_id=self.pdf_plan.id,
            job_type="floor_plan_analysis",
            status="queued",
            progress=8,
        )
        self.session.add(pdf_job)
        self.session.commit()
        g1_page = convert_pdf_page(
            source_path=self.pdf_path,
            processed_directory=self.processed_root,
            floor_plan_id=self.pdf_plan.id,
            processing_job_id=pdf_job.id,
            dpi=72,
        )
        before_hash = hashlib.sha256(
            g1_page.absolute_output_path.read_bytes()
        ).hexdigest()

        result = self.normalize(
            floor_plan=self.pdf_plan,
            processing_job=pdf_job,
            g1_page=g1_page,
        )

        self.assertEqual(result.source_mime_type, "image/png")
        self.assertEqual(
            hashlib.sha256(g1_page.absolute_output_path.read_bytes()).hexdigest(),
            before_hash,
        )
        self.session.refresh(pdf_job)
        self.assertEqual(pdf_job.status, "processing")
        self.assertEqual(pdf_job.progress, 8)

    def test_corrupt_source_persists_only_safe_failure(self) -> None:
        job = ProcessingJob(
            floor_plan_id=self.corrupt_plan.id,
            job_type="floor_plan_analysis",
            status="queued",
            progress=3,
        )
        self.session.add(job)
        self.session.commit()
        with self.assertRaises(ImageNormalizationError):
            self.normalize(floor_plan=self.corrupt_plan, processing_job=job)
        with Session(self.engine) as reload_session:
            reloaded = reload_session.get(ProcessingJob, job.id)
            self.assertEqual(reloaded.status, "failed")
            self.assertEqual(reloaded.error_message, SAFE_NORMALIZATION_FAILURE_MESSAGE)
            self.assertEqual(reloaded.progress, 3)
            for forbidden in ("pillow", "traceback", "private", "select"):
                self.assertNotIn(forbidden, reloaded.error_message.casefold())
        self.assertFalse(any(self.processed_root.rglob("image.png")))

    def test_terminal_type_and_floor_mismatches_remain_unchanged(self) -> None:
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
                with self.assertRaises(ImageNormalizationError) as caught:
                    self.normalize()
                self.assertEqual(caught.exception.code, "PROCESSING_JOB_INVALID")
                self.session.refresh(self.job)
                self.assertEqual(self.job.status, changes.get("status", "queued"))

    def test_start_persistence_failure_is_sanitized_and_rolled_back(self) -> None:
        fake_session = MagicMock(spec=Session)
        fake_session.commit.side_effect = RuntimeError("password=hunter2 SELECT")
        job = SimpleNamespace(
            id=1,
            floor_plan_id=1,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
            error_message=None,
        )
        plan = SimpleNamespace(id=1)
        with self.assertRaises(ImageNormalizationError) as caught:
            normalize_processing_job_image(
                fake_session,
                processing_job=job,
                floor_plan=plan,
                upload_directory=self.upload_root,
                processed_directory=self.processed_root,
            )
        self.assertEqual(caught.exception.code, "PROCESSING_JOB_STATE_PERSISTENCE_FAILED")
        self.assertNotIn("hunter2", caught.exception.message)
        fake_session.rollback.assert_called_once()

    def test_failure_persistence_failure_is_sanitized_and_rolled_back(self) -> None:
        fake_session = MagicMock(spec=Session)
        fake_session.commit.side_effect = (
            None,
            RuntimeError("password=hunter2 SELECT private_table"),
        )
        job = SimpleNamespace(
            id=1,
            floor_plan_id=1,
            job_type="floor_plan_analysis",
            status="queued",
            progress=0,
            error_message=None,
        )
        plan = SimpleNamespace(
            id=1,
            mime_type="image/png",
            storage_path="originals/missing.png",
        )
        with self.assertRaises(ImageNormalizationError) as caught:
            normalize_processing_job_image(
                fake_session,
                processing_job=job,
                floor_plan=plan,
                upload_directory=self.upload_root,
                processed_directory=self.processed_root,
            )
        self.assertEqual(caught.exception.code, "PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED")
        self.assertNotIn("hunter2", caught.exception.message)
        fake_session.rollback.assert_called_once()

    def test_raster_job_rejects_g1_input_and_marks_failure(self) -> None:
        with self.assertRaises(ImageNormalizationError) as caught:
            self.normalize(g1_page="pdf-pages/floor-plan-1/job-1/page-0001.png")
        self.assertEqual(caught.exception.code, "G1_RESULT_MISMATCH")
        self.session.refresh(self.job)
        self.assertEqual(self.job.status, "failed")


if __name__ == "__main__":
    unittest.main()
