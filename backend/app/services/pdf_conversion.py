from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from math import ceil, isfinite
from pathlib import Path, PurePosixPath, PureWindowsPath

import pypdfium2 as pdfium
from sqlalchemy.orm import Session

from app.models import FloorPlan, ProcessingJob


DEFAULT_PDF_DPI = 150
MAX_RENDERED_PIXEL_COUNT = 100_000_000
PDF_MIME_TYPE = "application/pdf"
PNG_MIME_TYPE = "image/png"
PDF_JOB_TYPE = "floor_plan_analysis"
SAFE_PDF_CONVERSION_FAILURE_MESSAGE = "Floor-plan PDF conversion failed."
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})

ERROR_MESSAGES = {
    "INVALID_PAGE_NUMBER": "The PDF page number must be a positive one-based integer.",
    "PAGE_OUT_OF_RANGE": "The requested PDF page is outside the document.",
    "INVALID_DPI": "The PDF rendering resolution is invalid.",
    "UNSUPPORTED_SOURCE": "The floor-plan source is not a supported PDF.",
    "SOURCE_UNAVAILABLE": "The floor-plan PDF is unavailable.",
    "UNSAFE_SOURCE_PATH": "The floor-plan source path is unsafe.",
    "INVALID_PROCESSED_DIRECTORY": "The processed-file directory is invalid.",
    "UNSAFE_OUTPUT_PATH": "The derived floor-plan output path is unsafe.",
    "PDF_OPEN_FAILED": "The floor-plan PDF could not be opened.",
    "PDF_RENDER_FAILED": "The floor-plan PDF page could not be rendered.",
    "UNSAFE_RENDERED_DIMENSIONS": "The rendered floor-plan dimensions are unsafe.",
    "OUTPUT_ALREADY_EXISTS": "The derived floor-plan page already exists.",
    "PNG_ENCODING_FAILED": "The rendered floor-plan page could not be encoded.",
    "OUTPUT_WRITE_FAILED": "The derived floor-plan page could not be stored.",
    "OUTPUT_CLEANUP_FAILED": "A failed PDF conversion could not be cleaned up safely.",
    "PROCESSING_JOB_INVALID": "The processing job cannot run PDF conversion.",
    "PROCESSING_JOB_STATE_PERSISTENCE_FAILED": (
        "The PDF conversion state could not be saved."
    ),
    "PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED": (
        "The PDF conversion failure state could not be saved."
    ),
}


@dataclass(frozen=True)
class ConvertedPdfPage:
    absolute_output_path: Path
    output_reference: str
    floor_plan_id: int
    processing_job_id: int
    page_number: int
    width: int
    height: int
    dpi: int
    mime_type: str
    output_byte_size: int


class PdfConversionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _conversion_error(code: str) -> PdfConversionError:
    return PdfConversionError(code, ERROR_MESSAGES[code])


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_render_request(
    *,
    floor_plan_id: int,
    processing_job_id: int,
    page_number: int,
    dpi: int,
    max_pixel_count: int,
) -> None:
    if not _is_positive_integer(page_number):
        raise _conversion_error("INVALID_PAGE_NUMBER")
    if not _is_positive_integer(dpi):
        raise _conversion_error("INVALID_DPI")
    if not _is_positive_integer(max_pixel_count):
        raise _conversion_error("UNSAFE_RENDERED_DIMENSIONS")
    if not (
        _is_positive_integer(floor_plan_id)
        and _is_positive_integer(processing_job_id)
    ):
        raise _conversion_error("UNSAFE_OUTPUT_PATH")


def _resolve_low_level_source(source_path: Path) -> Path:
    try:
        source = Path(source_path)
        resolved_source = source.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _conversion_error("SOURCE_UNAVAILABLE") from None

    if resolved_source.suffix.casefold() != ".pdf":
        raise _conversion_error("UNSUPPORTED_SOURCE")
    if not resolved_source.is_file():
        raise _conversion_error("SOURCE_UNAVAILABLE")
    return resolved_source


def _prepare_output_destination(
    *,
    processed_directory: Path,
    source_path: Path,
    floor_plan_id: int,
    processing_job_id: int,
    page_number: int,
) -> tuple[Path, Path, str]:
    try:
        configured_root = Path(processed_directory)
        if configured_root == Path("."):
            raise ValueError
        processed_root = configured_root.resolve(strict=False)
        processed_root.mkdir(parents=True, exist_ok=True)
        processed_root = processed_root.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _conversion_error("INVALID_PROCESSED_DIRECTORY") from None

    relative_reference = PurePosixPath(
        "pdf-pages",
        f"floor-plan-{floor_plan_id}",
        f"job-{processing_job_id}",
        f"page-{page_number:04d}.png",
    ).as_posix()
    destination = processed_root.joinpath(*PurePosixPath(relative_reference).parts)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = destination.parent.resolve(strict=True)
        resolved_destination = resolved_parent / destination.name
    except (OSError, RuntimeError):
        raise _conversion_error("UNSAFE_OUTPUT_PATH") from None

    if (
        not resolved_parent.is_relative_to(processed_root)
        or resolved_destination.is_relative_to(source_path.parent)
        or resolved_destination == source_path
    ):
        raise _conversion_error("UNSAFE_OUTPUT_PATH")
    if resolved_destination.exists():
        raise _conversion_error("OUTPUT_ALREADY_EXISTS")

    return processed_root, resolved_destination, relative_reference


def _close_pdf_resources(*resources: object | None) -> None:
    cleanup_failed = False
    for resource in resources:
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:
            cleanup_failed = True
    if cleanup_failed:
        raise _conversion_error("OUTPUT_CLEANUP_FAILED")


def _encode_pdf_page(
    source_path: Path,
    *,
    page_number: int,
    dpi: int,
    max_pixel_count: int,
) -> tuple[bytes, int, int]:
    document = None
    page = None
    bitmap = None
    try:
        try:
            document = pdfium.PdfDocument(str(source_path))
            page_count = len(document)
        except Exception:
            raise _conversion_error("PDF_OPEN_FAILED") from None

        if page_number > page_count:
            raise _conversion_error("PAGE_OUT_OF_RANGE")

        try:
            page = document[page_number - 1]
            width_points, height_points = page.get_size()
            scale = dpi / 72
            predicted_width = ceil(width_points * scale)
            predicted_height = ceil(height_points * scale)
        except PdfConversionError:
            raise
        except Exception:
            raise _conversion_error("PDF_RENDER_FAILED") from None

        if (
            not all(isfinite(value) and value > 0 for value in (width_points, height_points))
            or predicted_width <= 0
            or predicted_height <= 0
            or predicted_width * predicted_height > max_pixel_count
        ):
            raise _conversion_error("UNSAFE_RENDERED_DIMENSIONS")

        try:
            bitmap = page.render(scale=scale)
            width = int(bitmap.width)
            height = int(bitmap.height)
        except Exception:
            raise _conversion_error("PDF_RENDER_FAILED") from None

        if (
            width <= 0
            or height <= 0
            or width * height > max_pixel_count
        ):
            raise _conversion_error("UNSAFE_RENDERED_DIMENSIONS")

        try:
            encoded = BytesIO()
            pil_image = bitmap.to_pil()
            try:
                rgb_image = pil_image.convert("RGB")
                try:
                    rgb_image.save(encoded, format="PNG")
                finally:
                    rgb_image.close()
            finally:
                pil_image.close()
            png_bytes = encoded.getvalue()
        except Exception:
            raise _conversion_error("PNG_ENCODING_FAILED") from None

        if not png_bytes:
            raise _conversion_error("PNG_ENCODING_FAILED")
        return png_bytes, width, height
    finally:
        _close_pdf_resources(bitmap, page, document)


def _remove_partial_output(destination: Path) -> None:
    try:
        destination.unlink(missing_ok=True)
    except OSError:
        raise _conversion_error("OUTPUT_CLEANUP_FAILED") from None


def _write_png_exclusively(destination: Path, png_bytes: bytes) -> None:
    try:
        destination_file = destination.open("xb")
    except FileExistsError:
        raise _conversion_error("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        _remove_partial_output(destination)
        raise _conversion_error("OUTPUT_WRITE_FAILED") from None

    try:
        with destination_file:
            bytes_written = destination_file.write(png_bytes)
            if bytes_written != len(png_bytes):
                raise OSError("incomplete write")
    except Exception:
        _remove_partial_output(destination)
        raise _conversion_error("OUTPUT_WRITE_FAILED") from None


def convert_pdf_page(
    *,
    source_path: Path,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
    page_number: int = 1,
    dpi: int = DEFAULT_PDF_DPI,
    max_pixel_count: int = MAX_RENDERED_PIXEL_COUNT,
) -> ConvertedPdfPage:
    """Render exactly one one-based PDF page without HTTP or database state."""
    _validate_render_request(
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        page_number=page_number,
        dpi=dpi,
        max_pixel_count=max_pixel_count,
    )
    source = _resolve_low_level_source(source_path)
    processed_root, destination, _ = _prepare_output_destination(
        processed_directory=processed_directory,
        source_path=source,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        page_number=page_number,
    )
    png_bytes, width, height = _encode_pdf_page(
        source,
        page_number=page_number,
        dpi=dpi,
        max_pixel_count=max_pixel_count,
    )
    _write_png_exclusively(destination, png_bytes)

    return ConvertedPdfPage(
        absolute_output_path=destination,
        output_reference=destination.relative_to(processed_root).as_posix(),
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        page_number=page_number,
        width=width,
        height=height,
        dpi=dpi,
        mime_type=PNG_MIME_TYPE,
        output_byte_size=len(png_bytes),
    )


def _resolve_original_pdf(
    *,
    upload_directory: Path,
    floor_plan: FloorPlan,
) -> Path:
    storage_path = floor_plan.storage_path
    if not isinstance(storage_path, str) or not storage_path:
        raise _conversion_error("UNSAFE_SOURCE_PATH")

    portable_path = PurePosixPath(storage_path.replace("\\", "/"))
    windows_path = PureWindowsPath(storage_path)
    if (
        portable_path.is_absolute()
        or windows_path.is_absolute()
        or portable_path.parts[0:1] != ("originals",)
        or any(part in {"", ".", ".."} for part in portable_path.parts)
        or portable_path.suffix.casefold() != ".pdf"
    ):
        raise _conversion_error("UNSAFE_SOURCE_PATH")
    if floor_plan.mime_type != PDF_MIME_TYPE:
        raise _conversion_error("UNSUPPORTED_SOURCE")

    try:
        upload_root = Path(upload_directory).resolve(strict=True)
        originals_root = (upload_root / "originals").resolve(strict=True)
        source = upload_root.joinpath(*portable_path.parts).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _conversion_error("SOURCE_UNAVAILABLE") from None

    if (
        not upload_root.is_dir()
        or not originals_root.is_dir()
        or not originals_root.is_relative_to(upload_root)
        or not source.is_relative_to(originals_root)
    ):
        raise _conversion_error("UNSAFE_SOURCE_PATH")
    if not source.is_file():
        raise _conversion_error("SOURCE_UNAVAILABLE")
    return source


def _rollback_quietly(database_session: Session) -> None:
    try:
        database_session.rollback()
    except Exception:
        pass


def _persist_processing_start(
    database_session: Session,
    processing_job: ProcessingJob,
) -> None:
    processing_job.status = "processing"
    processing_job.error_message = None
    if (
        not isinstance(processing_job.progress, int)
        or not 0 <= processing_job.progress <= 100
    ):
        processing_job.progress = 0
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _conversion_error("PROCESSING_JOB_STATE_PERSISTENCE_FAILED") from None


def _persist_processing_failure(
    database_session: Session,
    processing_job: ProcessingJob,
) -> None:
    processing_job.status = "failed"
    processing_job.error_message = SAFE_PDF_CONVERSION_FAILURE_MESSAGE
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _conversion_error("PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED") from None


def convert_processing_job_pdf(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    floor_plan: FloorPlan,
    upload_directory: Path,
    processed_directory: Path,
    page_number: int = 1,
    dpi: int = DEFAULT_PDF_DPI,
    max_pixel_count: int = MAX_RENDERED_PIXEL_COUNT,
) -> ConvertedPdfPage:
    """Run G1 for an existing job while owning its state commits."""
    if not (
        _is_positive_integer(processing_job.id)
        and _is_positive_integer(floor_plan.id)
        and processing_job.job_type == PDF_JOB_TYPE
        and processing_job.floor_plan_id == floor_plan.id
        and processing_job.status not in TERMINAL_JOB_STATUSES
    ):
        raise _conversion_error("PROCESSING_JOB_INVALID")

    _persist_processing_start(database_session, processing_job)
    try:
        source_path = _resolve_original_pdf(
            upload_directory=upload_directory,
            floor_plan=floor_plan,
        )
        return convert_pdf_page(
            source_path=source_path,
            processed_directory=processed_directory,
            floor_plan_id=floor_plan.id,
            processing_job_id=processing_job.id,
            page_number=page_number,
            dpi=dpi,
            max_pixel_count=max_pixel_count,
        )
    except PdfConversionError:
        _persist_processing_failure(database_session, processing_job)
        raise
