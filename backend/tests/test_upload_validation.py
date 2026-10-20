import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pydantic import ValidationError
from pypdf import PdfWriter

from app.core.config import Settings, get_max_upload_size_bytes
from app.services.upload_validation import (
    ERROR_MESSAGES,
    UploadValidationError,
    ValidatedFloorPlan,
    validate_floor_plan_upload,
)


def make_image(image_format: str, size: tuple[int, int] = (12, 8)) -> bytes:
    output = BytesIO()
    with Image.new("RGB", size, color=(255, 255, 255)) as image:
        image.save(output, format=image_format)
    return output.getvalue()


def make_pdf(*, pages: int = 1, encrypted: bool = False) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("test-password")
    writer.write(output)
    return output.getvalue()


class UploadValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.jpeg = make_image("JPEG")
        cls.png = make_image("PNG")
        cls.pdf = make_pdf()
        cls.empty_pdf = make_pdf(pages=0)
        cls.encrypted_pdf = make_pdf(encrypted=True)

    def validate(
        self,
        *,
        filename: str = "floor-plan.jpg",
        mime_type: str = "image/jpeg",
        content: bytes | bytearray | memoryview | object | None = None,
        limit: int | None = None,
    ) -> ValidatedFloorPlan:
        payload = self.jpeg if content is None else content
        return validate_floor_plan_upload(
            filename=filename,
            declared_mime_type=mime_type,
            content=payload,
            max_file_size_bytes=len(payload) if limit is None else limit,
        )

    def assert_validation_error(
        self,
        expected_code: str,
        **arguments: object,
    ) -> UploadValidationError:
        with self.assertRaises(UploadValidationError) as context:
            self.validate(**arguments)
        error = context.exception
        self.assertEqual(error.code, expected_code)
        self.assertEqual(error.message, ERROR_MESSAGES[expected_code])
        self.assertEqual(str(error), ERROR_MESSAGES[expected_code])
        return error

    def test_valid_jpg_returns_dimensions(self) -> None:
        result = self.validate()
        self.assertEqual(result.extension, ".jpg")
        self.assertEqual(result.mime_type, "image/jpeg")
        self.assertEqual((result.width, result.height), (12, 8))
        self.assertIsNone(result.page_count)

    def test_valid_jpeg_and_uppercase_extensions_pass(self) -> None:
        jpeg_result = self.validate(filename="floor-plan.jpeg")
        uppercase_result = self.validate(filename="FLOOR-PLAN.JPG")
        self.assertEqual(jpeg_result.extension, ".jpeg")
        self.assertEqual(uppercase_result.extension, ".jpg")

    def test_corrupt_jpeg_is_sanitized(self) -> None:
        error = self.assert_validation_error(
            "UPLOAD_IMAGE_CORRUPT",
            content=b"\xff\xd8\xffcorrupt-jpeg",
            limit=1024,
        )
        self.assertNotIn("PIL", error.message)

    def test_png_content_renamed_as_jpeg_is_rejected(self) -> None:
        self.assert_validation_error("UPLOAD_CONTENT_MISMATCH", content=self.png)

    def test_valid_png_returns_dimensions(self) -> None:
        result = self.validate(
            filename="floor-plan.png",
            mime_type="image/png",
            content=self.png,
        )
        self.assertEqual((result.width, result.height), (12, 8))
        self.assertIsNone(result.page_count)

    def test_corrupt_png_is_sanitized(self) -> None:
        self.assert_validation_error(
            "UPLOAD_IMAGE_CORRUPT",
            filename="floor-plan.png",
            mime_type="image/png",
            content=b"\x89PNG\r\n\x1a\ncorrupt-png",
            limit=1024,
        )

    def test_jpeg_content_renamed_as_png_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_CONTENT_MISMATCH",
            filename="floor-plan.png",
            mime_type="image/png",
            content=self.jpeg,
        )

    def test_decompression_bomb_warning_is_rejected(self) -> None:
        with patch.object(Image, "MAX_IMAGE_PIXELS", 1):
            self.assert_validation_error(
                "UPLOAD_IMAGE_DIMENSIONS_INVALID",
                filename="floor-plan.png",
                mime_type="image/png",
                content=self.png,
            )

    def test_valid_pdf_returns_page_count(self) -> None:
        result = self.validate(
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.pdf,
        )
        self.assertEqual(result.page_count, 1)
        self.assertIsNone(result.width)
        self.assertIsNone(result.height)

    def test_corrupt_pdf_is_sanitized(self) -> None:
        error = self.assert_validation_error(
            "UPLOAD_PDF_CORRUPT",
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=b"%PDF-corrupt",
            limit=1024,
        )
        self.assertNotIn("EOF", error.message)

    def test_pdf_without_pages_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_PDF_NO_PAGES",
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.empty_pdf,
        )

    def test_encrypted_pdf_is_rejected_cleanly(self) -> None:
        self.assert_validation_error(
            "UPLOAD_PDF_ENCRYPTED",
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.encrypted_pdf,
        )

    def test_image_content_renamed_as_pdf_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_CONTENT_MISMATCH",
            filename="floor-plan.pdf",
            mime_type="application/pdf",
            content=self.jpeg,
        )

    def test_unsupported_extension_is_rejected_before_mime(self) -> None:
        self.assert_validation_error(
            "UPLOAD_EXTENSION_UNSUPPORTED",
            filename="floor-plan.gif",
            mime_type="image/gif",
        )

    def test_unsupported_mime_type_is_rejected(self) -> None:
        self.assert_validation_error("UPLOAD_MIME_UNSUPPORTED", mime_type="image/jpg")

    def test_jpeg_extension_with_png_mime_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_MIME_EXTENSION_MISMATCH",
            mime_type="image/png",
        )

    def test_png_extension_with_jpeg_mime_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_MIME_EXTENSION_MISMATCH",
            filename="floor-plan.png",
            content=self.png,
        )

    def test_pdf_extension_with_image_mime_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_MIME_EXTENSION_MISMATCH",
            filename="floor-plan.pdf",
            content=self.pdf,
        )

    def test_supported_mime_with_unsupported_extension_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_EXTENSION_UNSUPPORTED",
            filename="floor-plan.bmp",
            mime_type="image/png",
            content=self.png,
        )

    def test_missing_filename_is_rejected(self) -> None:
        self.assert_validation_error("UPLOAD_FILENAME_REQUIRED", filename="  ")

    def test_filename_without_extension_is_rejected(self) -> None:
        self.assert_validation_error(
            "UPLOAD_EXTENSION_UNSUPPORTED",
            filename="floor-plan",
        )

    def test_empty_content_is_rejected(self) -> None:
        self.assert_validation_error("UPLOAD_EMPTY", content=b"", limit=1)

    def test_content_exactly_at_limit_is_accepted(self) -> None:
        result = self.validate(limit=len(self.jpeg))
        self.assertEqual(result.file_size, len(self.jpeg))

    def test_content_one_byte_over_limit_is_rejected(self) -> None:
        error = self.assert_validation_error(
            "UPLOAD_TOO_LARGE",
            limit=len(self.jpeg) - 1,
        )
        self.assertEqual(error.details["file_size"], len(self.jpeg))
        self.assertEqual(error.details["max_file_size_bytes"], len(self.jpeg) - 1)

    def test_custom_limit_overrides_application_default(self) -> None:
        settings = Settings(_env_file=None, max_upload_size_mb=25)
        self.assertGreater(get_max_upload_size_bytes(settings), len(self.jpeg))
        self.assertEqual(self.validate(limit=len(self.jpeg)).file_size, len(self.jpeg))

    def test_invalid_non_positive_limits_fail_clearly(self) -> None:
        for invalid_limit in (0, -1):
            with self.subTest(limit=invalid_limit):
                self.assert_validation_error(
                    "UPLOAD_SIZE_LIMIT_INVALID",
                    limit=invalid_limit,
                )

    def test_settings_reject_non_positive_megabyte_limit(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, max_upload_size_mb=0)

    def test_configuration_converts_megabytes_to_bytes(self) -> None:
        settings = Settings(_env_file=None, max_upload_size_mb=3)
        self.assertEqual(get_max_upload_size_bytes(settings), 3 * 1024 * 1024)

    def test_original_mutable_content_is_unchanged(self) -> None:
        content = bytearray(self.png)
        original = content[:]
        self.validate(
            filename="floor-plan.png",
            mime_type="image/png",
            content=content,
        )
        self.assertEqual(content, original)

    def test_validation_performs_no_filesystem_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            before = tuple(Path(directory).iterdir())
            self.validate()
            after = tuple(Path(directory).iterdir())
        self.assertEqual(before, after)

    def test_service_uses_plain_inputs_without_http_or_database_context(self) -> None:
        with patch("builtins.open", side_effect=AssertionError("unexpected file open")):
            result = self.validate()
        self.assertEqual(result.original_filename, "floor-plan.jpg")


if __name__ == "__main__":
    unittest.main()
