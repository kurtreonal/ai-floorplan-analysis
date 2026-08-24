from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


FORMAT_BY_EXTENSION = {
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".png": ("image/png", "PNG"),
    ".pdf": ("application/pdf", "PDF"),
}
SUPPORTED_MIME_TYPES = frozenset(
    mime_type for mime_type, _ in FORMAT_BY_EXTENSION.values()
)
CONTENT_SIGNATURES = {
    "JPEG": (b"\xff\xd8\xff",),
    "PNG": (b"\x89PNG\r\n\x1a\n",),
    "PDF": (b"%PDF-",),
}

ERROR_MESSAGES = {
    "UPLOAD_FILENAME_REQUIRED": "A floor-plan filename is required.",
    "UPLOAD_EXTENSION_UNSUPPORTED": "The floor-plan file extension is not supported.",
    "UPLOAD_MIME_UNSUPPORTED": "The declared floor-plan MIME type is not supported.",
    "UPLOAD_MIME_EXTENSION_MISMATCH": (
        "The declared MIME type does not match the floor-plan file extension."
    ),
    "UPLOAD_EMPTY": "The floor-plan file is empty.",
    "UPLOAD_SIZE_LIMIT_INVALID": "The configured upload-size limit is invalid.",
    "UPLOAD_TOO_LARGE": "The floor-plan file exceeds the configured size limit.",
    "UPLOAD_CONTENT_MISMATCH": (
        "The floor-plan content does not match its extension and MIME type."
    ),
    "UPLOAD_IMAGE_CORRUPT": "The floor-plan image is corrupt or unreadable.",
    "UPLOAD_IMAGE_DIMENSIONS_INVALID": (
        "The floor-plan image dimensions are invalid or unsafe."
    ),
    "UPLOAD_PDF_CORRUPT": "The floor-plan PDF is corrupt or unreadable.",
    "UPLOAD_PDF_ENCRYPTED": "Encrypted floor-plan PDFs are not supported.",
    "UPLOAD_PDF_NO_PAGES": "The floor-plan PDF does not contain an accessible page.",
}


@dataclass(frozen=True)
class ValidatedFloorPlan:
    original_filename: str
    extension: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    page_count: int | None


class UploadValidationError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


def _validation_error(
    code: str,
    *,
    details: dict[str, object] | None = None,
) -> UploadValidationError:
    return UploadValidationError(code, ERROR_MESSAGES[code], details)


def _has_expected_signature(content: bytes, expected_format: str) -> bool:
    return any(
        content.startswith(signature)
        for signature in CONTENT_SIGNATURES[expected_format]
    )


def _validate_image(content: bytes, expected_format: str) -> tuple[int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    raise _validation_error("UPLOAD_CONTENT_MISMATCH")
                image.verify()

            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    raise _validation_error("UPLOAD_CONTENT_MISMATCH")
                width, height = image.size
                if width <= 0 or height <= 0:
                    raise _validation_error("UPLOAD_IMAGE_DIMENSIONS_INVALID")
                image.load()
    except UploadValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _validation_error("UPLOAD_IMAGE_DIMENSIONS_INVALID") from None
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        raise _validation_error("UPLOAD_IMAGE_CORRUPT") from None
    except Exception:
        raise _validation_error("UPLOAD_IMAGE_CORRUPT") from None

    return width, height


def _validate_pdf(content: bytes) -> int:
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise _validation_error("UPLOAD_PDF_ENCRYPTED")

        page_count = len(reader.pages)
        if page_count == 0:
            raise _validation_error("UPLOAD_PDF_NO_PAGES")

        for page in reader.pages:
            page.get_object()
    except UploadValidationError:
        raise
    except Exception:
        raise _validation_error("UPLOAD_PDF_CORRUPT") from None

    return page_count


def validate_floor_plan_upload(
    *,
    filename: str,
    declared_mime_type: str,
    content: bytes,
    max_file_size_bytes: int,
) -> ValidatedFloorPlan:
    if not isinstance(filename, str) or not filename.strip():
        raise _validation_error("UPLOAD_FILENAME_REQUIRED")

    extension = Path(filename.strip()).suffix.casefold()
    format_policy = FORMAT_BY_EXTENSION.get(extension)
    if format_policy is None:
        raise _validation_error("UPLOAD_EXTENSION_UNSUPPORTED")

    mime_type = (
        declared_mime_type.strip().casefold()
        if isinstance(declared_mime_type, str)
        else ""
    )
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise _validation_error("UPLOAD_MIME_UNSUPPORTED")

    expected_mime_type, expected_format = format_policy
    if mime_type != expected_mime_type:
        raise _validation_error("UPLOAD_MIME_EXTENSION_MISMATCH")

    if not isinstance(content, (bytes, bytearray, memoryview)):
        raise _validation_error("UPLOAD_CONTENT_MISMATCH")
    content_bytes = bytes(content)
    if not content_bytes:
        raise _validation_error("UPLOAD_EMPTY")

    if (
        isinstance(max_file_size_bytes, bool)
        or not isinstance(max_file_size_bytes, int)
        or max_file_size_bytes <= 0
    ):
        raise _validation_error("UPLOAD_SIZE_LIMIT_INVALID")
    if len(content_bytes) > max_file_size_bytes:
        raise _validation_error(
            "UPLOAD_TOO_LARGE",
            details={
                "file_size": len(content_bytes),
                "max_file_size_bytes": max_file_size_bytes,
            },
        )

    if not _has_expected_signature(content_bytes, expected_format):
        raise _validation_error("UPLOAD_CONTENT_MISMATCH")

    if expected_format in {"JPEG", "PNG"}:
        width, height = _validate_image(content_bytes, expected_format)
        page_count = None
    else:
        width = None
        height = None
        page_count = _validate_pdf(content_bytes)

    return ValidatedFloorPlan(
        original_filename=filename,
        extension=extension,
        mime_type=expected_mime_type,
        file_size=len(content_bytes),
        width=width,
        height=height,
        page_count=page_count,
    )
