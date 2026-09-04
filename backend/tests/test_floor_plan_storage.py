import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pypdf import PdfWriter

from app.core.config import (
    REPOSITORY_ROOT,
    Settings,
    UploadDirectoryConfigurationError,
    get_upload_directory,
)
from app.core.database import get_engine
from app.models import FloorPlan, Project, ProjectFloor, Role, User
from app.services.floor_plan_storage import (
    ERROR_MESSAGES,
    MAX_STORAGE_NAME_ATTEMPTS,
    FloorPlanStorageError,
    store_floor_plan_upload,
)
from app.services.upload_validation import UploadValidationError


def make_image(image_format: str) -> bytes:
    output = BytesIO()
    with Image.new("RGB", (16, 10), color=(255, 255, 255)) as image:
        image.save(output, format=image_format)
    return output.getvalue()


def make_pdf() -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return output.getvalue()


class MidWriteFailure:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool:
        return False

    def write(self, content: bytes) -> int:
        with open(self.path, "wb") as partial_file:
            partial_file.write(content[:8])
        raise OSError("synthetic mid-write failure")


class FloorPlanStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.connection = get_engine().connect()
        cls.transaction = cls.connection.begin()
        cls.database_session = Session(
            bind=cls.connection,
            expire_on_commit=False,
        )
        designer_role = cls.database_session.scalar(
            select(Role).where(Role.name == "DESIGNER")
        )
        if designer_role is None:
            raise RuntimeError("The DESIGNER seed role is required.")

        marker = uuid4().hex
        cls.user = User(
            oauth_provider="e2-test",
            oauth_subject=f"designer-{marker}",
            email=f"designer-{marker}@example.test",
            display_name="E2 Designer",
            role_id=designer_role.id,
        )
        cls.project = Project(
            owner=cls.user,
            name=f"E2 Storage Project {marker}",
        )
        cls.project_floor = ProjectFloor(
            project=cls.project,
            name="Ground Floor",
            sort_order=0,
        )
        cls.database_session.add(cls.project_floor)
        cls.database_session.flush()

        cls.jpeg = make_image("JPEG")
        cls.png = make_image("PNG")
        cls.pdf = make_pdf()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.database_session.close()
        if cls.transaction.is_active:
            cls.transaction.rollback()
        cls.connection.close()

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.upload_directory = Path(self.temporary_directory.name) / "uploads"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def store(
        self,
        *,
        database_session: Session | None = None,
        filename: str = "floor-plan.jpg",
        mime_type: str = "image/jpeg",
        content: bytes | None = None,
        upload_directory: Path | None = None,
    ) -> FloorPlan:
        payload = self.jpeg if content is None else content
        return store_floor_plan_upload(
            database_session or self.database_session,
            project_floor_id=self.project_floor.id,
            filename=filename,
            declared_mime_type=mime_type,
            content=payload,
            upload_directory=upload_directory or self.upload_directory,
            max_file_size_bytes=len(payload),
        )

    def count_floor_plans(self) -> int:
        return self.database_session.scalar(
            select(func.count())
            .select_from(FloorPlan)
            .where(FloorPlan.project_floor_id == self.project_floor.id)
        )

    def stored_path(self, floor_plan: FloorPlan) -> Path:
        return self.upload_directory / Path(floor_plan.storage_path)

    def assert_storage_error(
        self,
        expected_code: str,
        **arguments: object,
    ) -> FloorPlanStorageError:
        with self.assertRaises(FloorPlanStorageError) as context:
            self.store(**arguments)
        error = context.exception
        self.assertEqual(error.code, expected_code)
        self.assertEqual(error.message, ERROR_MESSAGES[expected_code])
        self.assertEqual(str(error), ERROR_MESSAGES[expected_code])
        return error

    def assert_successful_storage(
        self,
        *,
        filename: str,
        mime_type: str,
        content: bytes,
        extension: str,
    ) -> FloorPlan:
        floor_plan = self.store(
            filename=filename,
            mime_type=mime_type,
            content=content,
        )
        stored_path = self.stored_path(floor_plan)

        self.assertTrue(stored_path.is_file())
        self.assertEqual(stored_path.parent, self.upload_directory / "originals")
        self.assertEqual(stored_path.read_bytes(), content)
        self.assertTrue(stored_path.name.endswith(extension))
        self.assertEqual(floor_plan.project_floor_id, self.project_floor.id)
        self.assertEqual(floor_plan.original_filename, filename)
        self.assertEqual(floor_plan.mime_type, mime_type)
        self.assertEqual(floor_plan.file_size, len(content))
        self.assertEqual(floor_plan.processing_status, "uploaded")
        self.assertEqual(
            floor_plan.storage_path,
            f"originals/{stored_path.name}",
        )
        self.assertFalse(Path(floor_plan.storage_path).is_absolute())
        self.assertIsNotNone(floor_plan.id)
        return floor_plan

    def test_valid_jpeg_is_stored_with_persisted_metadata(self) -> None:
        floor_plan = self.assert_successful_storage(
            filename="floor-plan.jpg",
            mime_type="image/jpeg",
            content=self.jpeg,
            extension=".jpg",
        )
        persisted = self.database_session.get(FloorPlan, floor_plan.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.storage_path, floor_plan.storage_path)

    def test_valid_png_is_stored_beneath_originals(self) -> None:
        self.assert_successful_storage(
            filename="floor-plan.png",
            mime_type="image/png",
            content=self.png,
            extension=".png",
        )

    def test_valid_pdf_is_stored_beneath_originals(self) -> None:
        self.assert_successful_storage(
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.pdf,
            extension=".pdf",
        )

    def test_validated_mime_and_extension_are_stored_canonically(self) -> None:
        floor_plan = self.store(
            filename="Floor-Plan.JPEG",
            mime_type="IMAGE/JPEG",
        )
        self.assertEqual(floor_plan.mime_type, "image/jpeg")
        self.assertTrue(floor_plan.storage_path.endswith(".jpeg"))
        self.assertEqual(floor_plan.original_filename, "Floor-Plan.JPEG")

    def test_duplicate_client_names_get_different_storage_paths(self) -> None:
        first = self.store()
        second = self.store()
        self.assertNotEqual(first.storage_path, second.storage_path)

    def test_existing_destination_is_not_overwritten(self) -> None:
        originals = self.upload_directory / "originals"
        originals.mkdir(parents=True)
        collision_name = f"{'a' * 32}.jpg"
        existing = originals / collision_name
        existing.write_bytes(b"existing original")

        with patch(
            "app.services.floor_plan_storage.uuid4",
            side_effect=(
                SimpleNamespace(hex="a" * 32),
                SimpleNamespace(hex="b" * 32),
            ),
        ):
            stored = self.store()

        self.assertEqual(existing.read_bytes(), b"existing original")
        self.assertTrue(stored.storage_path.endswith(f"{'b' * 32}.jpg"))

    def test_forced_uuid_collision_retries(self) -> None:
        originals = self.upload_directory / "originals"
        originals.mkdir(parents=True)
        (originals / f"{'c' * 32}.jpg").write_bytes(b"occupied")

        with patch(
            "app.services.floor_plan_storage.uuid4",
            side_effect=(
                SimpleNamespace(hex="c" * 32),
                SimpleNamespace(hex="d" * 32),
            ),
        ) as uuid_mock:
            stored = self.store()

        self.assertEqual(uuid_mock.call_count, 2)
        self.assertTrue(stored.storage_path.endswith(f"{'d' * 32}.jpg"))

    def test_repeated_allocation_failure_is_sanitized(self) -> None:
        originals = self.upload_directory / "originals"
        originals.mkdir(parents=True)
        collision_hex = "e" * 32
        occupied = originals / f"{collision_hex}.jpg"
        occupied.write_bytes(b"do not overwrite")
        before_count = self.count_floor_plans()

        with patch(
            "app.services.floor_plan_storage.uuid4",
            return_value=SimpleNamespace(hex=collision_hex),
        ) as uuid_mock:
            self.assert_storage_error("STORAGE_NAME_ALLOCATION_FAILED")

        self.assertEqual(uuid_mock.call_count, MAX_STORAGE_NAME_ATTEMPTS)
        self.assertEqual(occupied.read_bytes(), b"do not overwrite")
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_client_path_components_are_removed(self) -> None:
        cases = (
            ("../../outside.jpg", "outside.jpg", "image/jpeg", self.jpeg),
            ("..\\..\\outside.png", "outside.png", "image/png", self.png),
            ("C:\\outside\\plan.pdf", "plan.pdf", "application/pdf", self.pdf),
            ("folder/subfolder/plan.jpg", "plan.jpg", "image/jpeg", self.jpeg),
        )

        for filename, expected_basename, mime_type, content in cases:
            with self.subTest(filename=filename):
                floor_plan = self.store(
                    filename=filename,
                    mime_type=mime_type,
                    content=content,
                )
                stored_path = self.stored_path(floor_plan).resolve()
                originals = (self.upload_directory / "originals").resolve()
                self.assertEqual(stored_path.parent, originals)
                self.assertEqual(floor_plan.original_filename, expected_basename)
                self.assertNotIn("..", floor_plan.storage_path)
                self.assertNotIn(expected_basename, floor_plan.storage_path)

    def test_null_byte_original_filename_is_rejected(self) -> None:
        before_count = self.count_floor_plans()
        self.assert_storage_error(
            "ORIGINAL_FILENAME_INVALID",
            filename="unsafe\x00.jpg",
        )
        self.assertFalse(self.upload_directory.exists())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_overlong_original_filename_is_rejected_without_truncation(self) -> None:
        before_count = self.count_floor_plans()
        self.assert_storage_error(
            "ORIGINAL_FILENAME_TOO_LONG",
            filename=f"{'x' * 252}.jpg",
        )
        self.assertFalse(self.upload_directory.exists())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_missing_basename_is_rejected_before_storage(self) -> None:
        before_count = self.count_floor_plans()
        with self.assertRaises(UploadValidationError):
            self.store(filename="folder/")
        self.assertFalse(self.upload_directory.exists())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_relative_upload_directory_resolves_against_repository_root(self) -> None:
        relative = Path("storage") / f"e2-config-{uuid4().hex}"
        expected = (REPOSITORY_ROOT / relative).resolve()
        settings = Settings(_env_file=None, upload_dir=relative)

        resolved = get_upload_directory(settings)

        self.assertEqual(resolved, expected)
        self.assertFalse(expected.exists())

    def test_absolute_upload_directory_is_supported_without_creation(self) -> None:
        absolute = self.upload_directory.resolve()
        settings = Settings(_env_file=None, upload_dir=absolute)

        self.assertEqual(get_upload_directory(settings), absolute)
        self.assertFalse(absolute.exists())

    def test_missing_upload_configuration_fails_clearly(self) -> None:
        settings = Settings(_env_file=None, upload_dir=None)
        with self.assertRaises(UploadDirectoryConfigurationError) as context:
            get_upload_directory(settings)
        self.assertEqual(
            str(context.exception),
            "UPLOAD_DIR is required when file storage is used.",
        )

    def test_blank_upload_configuration_fails_clearly(self) -> None:
        settings = Settings(_env_file=None, upload_dir="")
        with self.assertRaises(UploadDirectoryConfigurationError):
            get_upload_directory(settings)

    def test_validation_failure_creates_no_file_or_record(self) -> None:
        before_count = self.count_floor_plans()
        with self.assertRaises(UploadValidationError):
            self.store(content=b"not-an-image")
        self.assertFalse(self.upload_directory.exists())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_directory_creation_failure_creates_no_record(self) -> None:
        before_count = self.count_floor_plans()
        with patch.object(Path, "mkdir", side_effect=PermissionError("private path")):
            error = self.assert_storage_error("UPLOAD_DIRECTORY_UNAVAILABLE")
        self.assertNotIn(str(self.upload_directory), error.message)
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_file_open_failure_creates_no_record(self) -> None:
        before_count = self.count_floor_plans()
        with patch.object(Path, "open", side_effect=PermissionError("private path")):
            error = self.assert_storage_error("ORIGINAL_FILE_WRITE_FAILED")
        self.assertNotIn(str(self.upload_directory), error.message)
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_file_open_failure_removes_any_partial_destination(self) -> None:
        def fail_after_creation(path: Path, *args, **kwargs):
            with open(path, "xb") as partial_file:
                partial_file.write(b"partial")
            raise OSError("synthetic open failure")

        before_count = self.count_floor_plans()
        with patch.object(Path, "open", autospec=True, side_effect=fail_after_creation):
            self.assert_storage_error("ORIGINAL_FILE_WRITE_FAILED")

        originals = self.upload_directory / "originals"
        self.assertEqual(tuple(originals.iterdir()), ())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_mid_write_failure_removes_partial_file(self) -> None:
        def fail_after_partial_write(path: Path, *args, **kwargs):
            return MidWriteFailure(path)

        before_count = self.count_floor_plans()
        with patch.object(Path, "open", autospec=True, side_effect=fail_after_partial_write):
            self.assert_storage_error("ORIGINAL_FILE_WRITE_FAILED")

        originals = self.upload_directory / "originals"
        self.assertEqual(tuple(originals.iterdir()), ())
        self.assertEqual(self.count_floor_plans(), before_count)

    def test_repository_flush_failure_rolls_back_and_deletes_file(self) -> None:
        mock_session = MagicMock(spec=Session)
        with patch(
            "app.services.floor_plan_storage.add_floor_plan",
            side_effect=RuntimeError("raw SQL details"),
        ):
            error = self.assert_storage_error(
                "FLOOR_PLAN_RECORD_FAILED",
                database_session=mock_session,
            )

        mock_session.rollback.assert_called_once_with()
        self.assertEqual(tuple((self.upload_directory / "originals").iterdir()), ())
        self.assertNotIn("SQL", error.message)
        self.assertNotIn(str(self.upload_directory), error.message)

    def test_commit_failure_rolls_back_and_deletes_file(self) -> None:
        mock_session = MagicMock(spec=Session)
        mock_session.commit.side_effect = RuntimeError("raw commit details")

        error = self.assert_storage_error(
            "FLOOR_PLAN_RECORD_FAILED",
            database_session=mock_session,
        )

        self.assertEqual(mock_session.add.call_count, 2)
        self.assertEqual(mock_session.flush.call_count, 2)
        mock_session.rollback.assert_called_once_with()
        self.assertEqual(tuple((self.upload_directory / "originals").iterdir()), ())
        self.assertNotIn("commit", error.message.casefold())

    def test_cleanup_failure_is_reported_clearly(self) -> None:
        mock_session = MagicMock(spec=Session)
        with (
            patch(
                "app.services.floor_plan_storage.add_floor_plan",
                side_effect=RuntimeError("raw SQL details"),
            ),
            patch.object(Path, "unlink", side_effect=PermissionError("private path")),
        ):
            error = self.assert_storage_error(
                "STORED_FILE_CLEANUP_FAILED",
                database_session=mock_session,
            )

        mock_session.rollback.assert_called_once_with()
        self.assertNotIn(str(self.upload_directory), error.message)
        self.assertNotIn("private", error.message)

    def test_second_upload_does_not_modify_first_original(self) -> None:
        first = self.store()
        first_path = self.stored_path(first)
        first_bytes = first_path.read_bytes()

        second = self.store(
            filename="second.png",
            mime_type="image/png",
            content=self.png,
        )

        self.assertNotEqual(first.storage_path, second.storage_path)
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertEqual(self.stored_path(second).read_bytes(), self.png)


if __name__ == "__main__":
    unittest.main()
