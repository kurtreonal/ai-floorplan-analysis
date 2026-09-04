from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.models import FloorPlan, ProcessingJob
from app.services.pdf_conversion import ConvertedPdfPage
from app.services.processing_artifact_service import (
    ProcessingArtifactError,
    register_processing_artifact,
)


DEFAULT_MAXIMUM_DIMENSION = 4096
MAX_SOURCE_PIXEL_COUNT = 100_000_000
NORMALIZED_MIME_TYPE = "image/png"
NORMALIZATION_JOB_TYPE = "floor_plan_analysis"
SAFE_NORMALIZATION_FAILURE_MESSAGE = "Floor-plan image normalization failed."
SUPPORTED_SOURCE_MIME_TYPES = frozenset({"image/jpeg", "image/png"})
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})
ACTIVE_JOB_STATUSES = frozenset({"queued", "processing"})
G1_REFERENCE_PATTERN = re.compile(
    r"^pdf-pages/floor-plan-(?P<floor_plan_id>[1-9][0-9]*)/"
    r"job-(?P<job_id>[1-9][0-9]*)/page-(?P<page>[0-9]{4,})\.png$"
)

ERROR_MESSAGES = {
    "INVALID_IDENTIFIERS": "The normalization identifiers are invalid.",
    "INVALID_MAXIMUM_DIMENSION": "The normalization size limit is invalid.",
    "UNSUPPORTED_SOURCE": "The floor-plan source is not a supported image.",
    "UNSAFE_SOURCE_PATH": "The floor-plan source path is unsafe.",
    "SOURCE_UNAVAILABLE": "The floor-plan image is unavailable.",
    "G1_RESULT_MISMATCH": "The converted PDF page does not match this job.",
    "CORRUPT_SOURCE": "The floor-plan image could not be decoded.",
    "UNSAFE_SOURCE_DIMENSIONS": "The floor-plan image dimensions are unsafe.",
    "DECODE_FAILED": "The floor-plan image could not be decoded.",
    "ORIENTATION_FAILED": "The floor-plan orientation could not be normalized.",
    "RESIZE_FAILED": "The floor-plan image could not be resized.",
    "INVALID_PROCESSED_DIRECTORY": "The processed-file directory is invalid.",
    "UNSAFE_OUTPUT_PATH": "The normalized image output path is unsafe.",
    "OUTPUT_ALREADY_EXISTS": "The normalized floor-plan image already exists.",
    "ENCODE_FAILED": "The normalized floor-plan image could not be encoded.",
    "OUTPUT_WRITE_FAILED": "The normalized floor-plan image could not be stored.",
    "OUTPUT_CLEANUP_FAILED": (
        "A failed image normalization could not be cleaned up safely."
    ),
    "PROCESSING_JOB_INVALID": "The processing job cannot normalize this image.",
    "PROCESSING_JOB_STATE_PERSISTENCE_FAILED": (
        "The image normalization state could not be saved."
    ),
    "PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED": (
        "The image normalization failure state could not be saved."
    ),
    "ARTIFACT_REGISTRATION_FAILED": "The normalized image could not be registered safely.",
}


@dataclass(frozen=True)
class NormalizedImage:
    absolute_output_path: Path
    output_reference: str
    floor_plan_id: int
    processing_job_id: int
    source_mime_type: str
    encoded_source_width: int
    encoded_source_height: int
    oriented_width: int
    oriented_height: int
    normalized_width: int
    normalized_height: int
    orientation_corrected: bool
    resized: bool
    output_mime_type: str
    output_byte_size: int


class ImageNormalizationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _normalization_error(code: str) -> ImageNormalizationError:
    return ImageNormalizationError(code, ERROR_MESSAGES[code])


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_request(
    *,
    floor_plan_id: int,
    processing_job_id: int,
    maximum_dimension: int,
) -> None:
    if not (
        _is_positive_integer(floor_plan_id)
        and _is_positive_integer(processing_job_id)
    ):
        raise _normalization_error("INVALID_IDENTIFIERS")
    if not _is_positive_integer(maximum_dimension):
        raise _normalization_error("INVALID_MAXIMUM_DIMENSION")


def _expected_extensions(source_mime_type: str) -> frozenset[str]:
    if source_mime_type == "image/jpeg":
        return frozenset({".jpg", ".jpeg"})
    if source_mime_type == "image/png":
        return frozenset({".png"})
    raise _normalization_error("UNSUPPORTED_SOURCE")


def _resolve_low_level_source(
    source_path: Path,
    *,
    source_mime_type: str,
) -> Path:
    expected_extensions = _expected_extensions(source_mime_type)
    try:
        source = Path(source_path).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _normalization_error("SOURCE_UNAVAILABLE") from None
    if not source.is_file():
        raise _normalization_error("SOURCE_UNAVAILABLE")
    if source.suffix.casefold() not in expected_extensions:
        raise _normalization_error("UNSUPPORTED_SOURCE")
    return source


def _prepare_output_destination(
    *,
    processed_directory: Path,
    source_path: Path,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[Path, Path]:
    try:
        configured_root = Path(processed_directory)
        if configured_root == Path("."):
            raise ValueError
        processed_root = configured_root.resolve(strict=False)
        processed_root.mkdir(parents=True, exist_ok=True)
        processed_root = processed_root.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _normalization_error("INVALID_PROCESSED_DIRECTORY") from None

    relative_reference = PurePosixPath(
        "normalized",
        f"floor-plan-{floor_plan_id}",
        f"job-{processing_job_id}",
        "image.png",
    )
    destination = processed_root.joinpath(*relative_reference.parts)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = destination.parent.resolve(strict=True)
        destination = resolved_parent / destination.name
    except (OSError, RuntimeError):
        raise _normalization_error("UNSAFE_OUTPUT_PATH") from None

    if (
        not resolved_parent.is_relative_to(processed_root)
        or destination.is_relative_to(source_path.parent)
        or destination == source_path
    ):
        raise _normalization_error("UNSAFE_OUTPUT_PATH")
    if destination.exists():
        raise _normalization_error("OUTPUT_ALREADY_EXISTS")
    return processed_root, destination


def _load_source_image(
    source_path: Path,
    *,
    source_mime_type: str,
) -> tuple[Image.Image, int, int, bool]:
    expected_format = "JPEG" if source_mime_type == "image/jpeg" else "PNG"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source_image = Image.open(source_path)
            if source_image.format != expected_format:
                source_image.close()
                raise _normalization_error("UNSUPPORTED_SOURCE")
            encoded_width, encoded_height = source_image.size
            if (
                encoded_width <= 0
                or encoded_height <= 0
                or encoded_width * encoded_height > MAX_SOURCE_PIXEL_COUNT
            ):
                source_image.close()
                raise _normalization_error("UNSAFE_SOURCE_DIMENSIONS")
            orientation = source_image.getexif().get(274, 1)
            source_image.load()
    except ImageNormalizationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _normalization_error("UNSAFE_SOURCE_DIMENSIONS") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise _normalization_error("CORRUPT_SOURCE") from None
    except Exception:
        raise _normalization_error("DECODE_FAILED") from None

    return (
        source_image,
        encoded_width,
        encoded_height,
        orientation in {2, 3, 4, 5, 6, 7, 8},
    )


def _apply_orientation(source_image: Image.Image) -> Image.Image:
    try:
        return ImageOps.exif_transpose(source_image)
    except Exception:
        raise _normalization_error("ORIENTATION_FAILED") from None


def _convert_to_clean_rgb(oriented_image: Image.Image) -> Image.Image:
    rgb_image = None
    try:
        has_transparency = (
            "A" in oriented_image.getbands()
            or "transparency" in oriented_image.info
        )
        if has_transparency:
            rgba_image = oriented_image.convert("RGBA")
            try:
                rgb_image = Image.new("RGB", rgba_image.size, "white")
                rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
            finally:
                rgba_image.close()
            return rgb_image

        converted = oriented_image.convert("RGB")
        try:
            clean_image = Image.new("RGB", converted.size)
            clean_image.paste(converted)
        finally:
            converted.close()
        return clean_image
    except ImageNormalizationError:
        raise
    except Exception:
        if rgb_image is not None:
            rgb_image.close()
        raise _normalization_error("DECODE_FAILED") from None


def _resize_if_required(
    rgb_image: Image.Image,
    *,
    maximum_dimension: int,
) -> tuple[Image.Image, bool]:
    width, height = rgb_image.size
    if max(width, height) <= maximum_dimension:
        return rgb_image, False

    scale = maximum_dimension / max(width, height)
    target_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    try:
        resized_image = rgb_image.resize(target_size, Image.Resampling.LANCZOS)
    except Exception:
        raise _normalization_error("RESIZE_FAILED") from None
    rgb_image.close()
    return resized_image, True


def _encode_png(image: Image.Image) -> bytes:
    try:
        output = BytesIO()
        image.save(output, format="PNG")
        encoded = output.getvalue()
    except Exception:
        raise _normalization_error("ENCODE_FAILED") from None
    if not encoded:
        raise _normalization_error("ENCODE_FAILED")
    return encoded


def _remove_partial_output(destination: Path) -> None:
    try:
        destination.unlink(missing_ok=True)
    except OSError:
        raise _normalization_error("OUTPUT_CLEANUP_FAILED") from None


def _write_png_exclusively(destination: Path, content: bytes) -> None:
    try:
        destination_file = destination.open("xb")
    except FileExistsError:
        raise _normalization_error("OUTPUT_ALREADY_EXISTS") from None
    except OSError:
        _remove_partial_output(destination)
        raise _normalization_error("OUTPUT_WRITE_FAILED") from None

    try:
        with destination_file:
            written = destination_file.write(content)
            if written != len(content):
                raise OSError("incomplete write")
    except Exception:
        _remove_partial_output(destination)
        raise _normalization_error("OUTPUT_WRITE_FAILED") from None


def normalize_image(
    *,
    source_path: Path,
    source_mime_type: str,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
    maximum_dimension: int = DEFAULT_MAXIMUM_DIMENSION,
) -> NormalizedImage:
    """Normalize one trusted image path without HTTP or database state."""
    _validate_request(
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        maximum_dimension=maximum_dimension,
    )
    source = _resolve_low_level_source(
        source_path,
        source_mime_type=source_mime_type,
    )
    processed_root, destination = _prepare_output_destination(
        processed_directory=processed_directory,
        source_path=source,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
    )
    source_image, encoded_width, encoded_height, orientation_corrected = (
        _load_source_image(source, source_mime_type=source_mime_type)
    )
    oriented_image = None
    clean_image = None
    normalized_image = None
    try:
        oriented_image = _apply_orientation(source_image)
        oriented_width, oriented_height = oriented_image.size
        clean_image = _convert_to_clean_rgb(oriented_image)
        normalized_image, resized = _resize_if_required(
            clean_image,
            maximum_dimension=maximum_dimension,
        )
        normalized_width, normalized_height = normalized_image.size
        png_bytes = _encode_png(normalized_image)
    finally:
        if normalized_image is not None:
            normalized_image.close()
        elif clean_image is not None:
            clean_image.close()
        if oriented_image is not None and oriented_image is not source_image:
            oriented_image.close()
        source_image.close()

    _write_png_exclusively(destination, png_bytes)
    return NormalizedImage(
        absolute_output_path=destination,
        output_reference=destination.relative_to(processed_root).as_posix(),
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        source_mime_type=source_mime_type,
        encoded_source_width=encoded_width,
        encoded_source_height=encoded_height,
        oriented_width=oriented_width,
        oriented_height=oriented_height,
        normalized_width=normalized_width,
        normalized_height=normalized_height,
        orientation_corrected=orientation_corrected,
        resized=resized,
        output_mime_type=NORMALIZED_MIME_TYPE,
        output_byte_size=len(png_bytes),
    )


def _validate_relative_original_reference(
    storage_path: str,
    *,
    source_mime_type: str,
) -> PurePosixPath:
    if not isinstance(storage_path, str) or not storage_path:
        raise _normalization_error("UNSAFE_SOURCE_PATH")
    portable_path = PurePosixPath(storage_path.replace("\\", "/"))
    windows_path = PureWindowsPath(storage_path)
    if (
        portable_path.is_absolute()
        or windows_path.is_absolute()
        or portable_path.parts[0:1] != ("originals",)
        or any(part in {"", ".", ".."} for part in portable_path.parts)
        or portable_path.suffix.casefold()
        not in _expected_extensions(source_mime_type)
    ):
        raise _normalization_error("UNSAFE_SOURCE_PATH")
    return portable_path


def _resolve_uploaded_raster(
    *,
    upload_directory: Path,
    floor_plan: FloorPlan,
) -> tuple[Path, str]:
    if floor_plan.mime_type not in SUPPORTED_SOURCE_MIME_TYPES:
        raise _normalization_error("UNSUPPORTED_SOURCE")
    portable_path = _validate_relative_original_reference(
        floor_plan.storage_path,
        source_mime_type=floor_plan.mime_type,
    )
    try:
        upload_root = Path(upload_directory).resolve(strict=True)
        originals_root = (upload_root / "originals").resolve(strict=True)
        source = upload_root.joinpath(*portable_path.parts).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _normalization_error("SOURCE_UNAVAILABLE") from None
    if (
        not upload_root.is_dir()
        or not originals_root.is_dir()
        or not originals_root.is_relative_to(upload_root)
        or not source.is_relative_to(originals_root)
    ):
        raise _normalization_error("UNSAFE_SOURCE_PATH")
    if not source.is_file():
        raise _normalization_error("SOURCE_UNAVAILABLE")
    return source, floor_plan.mime_type


def _g1_reference_and_path(
    g1_page: ConvertedPdfPage | str,
    *,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
) -> Path:
    if isinstance(g1_page, ConvertedPdfPage):
        if (
            g1_page.floor_plan_id != floor_plan_id
            or g1_page.processing_job_id != processing_job_id
            or g1_page.mime_type != NORMALIZED_MIME_TYPE
            or not _is_positive_integer(g1_page.page_number)
        ):
            raise _normalization_error("G1_RESULT_MISMATCH")
        reference = g1_page.output_reference
        supplied_absolute_path = g1_page.absolute_output_path
        supplied_page_number = g1_page.page_number
    elif isinstance(g1_page, str):
        reference = g1_page
        supplied_absolute_path = None
        supplied_page_number = None
    else:
        raise _normalization_error("G1_RESULT_MISMATCH")

    match = G1_REFERENCE_PATTERN.fullmatch(reference)
    if (
        match is None
        or int(match.group("floor_plan_id")) != floor_plan_id
        or int(match.group("job_id")) != processing_job_id
        or int(match.group("page")) <= 0
        or (
            supplied_page_number is not None
            and int(match.group("page")) != supplied_page_number
        )
    ):
        raise _normalization_error("G1_RESULT_MISMATCH")

    try:
        processed_root = Path(processed_directory).resolve(strict=True)
        source = processed_root.joinpath(
            *PurePosixPath(reference).parts
        ).resolve(strict=True)
        expected_job_directory = (
            processed_root
            / "pdf-pages"
            / f"floor-plan-{floor_plan_id}"
            / f"job-{processing_job_id}"
        ).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _normalization_error("SOURCE_UNAVAILABLE") from None

    if (
        not processed_root.is_dir()
        or not expected_job_directory.is_relative_to(processed_root)
        or source.parent != expected_job_directory
        or not source.is_file()
    ):
        raise _normalization_error("UNSAFE_SOURCE_PATH")
    if supplied_absolute_path is not None:
        try:
            if Path(supplied_absolute_path).resolve(strict=True) != source:
                raise _normalization_error("G1_RESULT_MISMATCH")
        except (OSError, RuntimeError, TypeError, ValueError):
            raise _normalization_error("G1_RESULT_MISMATCH") from None
    return source


def _rollback_quietly(database_session: Session) -> None:
    try:
        database_session.rollback()
    except Exception:
        pass


def _persist_start_state(
    database_session: Session,
    processing_job: ProcessingJob,
) -> None:
    processing_job.status = "processing"
    processing_job.error_message = None
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _normalization_error(
            "PROCESSING_JOB_STATE_PERSISTENCE_FAILED"
        ) from None


def _persist_failure_state(
    database_session: Session,
    processing_job: ProcessingJob,
) -> None:
    processing_job.status = "failed"
    processing_job.error_message = SAFE_NORMALIZATION_FAILURE_MESSAGE
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _normalization_error(
            "PROCESSING_JOB_FAILURE_PERSISTENCE_FAILED"
        ) from None


def normalize_processing_job_image(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    floor_plan: FloorPlan,
    upload_directory: Path,
    processed_directory: Path,
    g1_page: ConvertedPdfPage | str | None = None,
    maximum_dimension: int = DEFAULT_MAXIMUM_DIMENSION,
) -> NormalizedImage:
    """Normalize an existing job source while owning job-state commits."""
    if not (
        _is_positive_integer(processing_job.id)
        and _is_positive_integer(floor_plan.id)
        and processing_job.job_type == NORMALIZATION_JOB_TYPE
        and processing_job.floor_plan_id == floor_plan.id
        and processing_job.status in ACTIVE_JOB_STATUSES
    ):
        raise _normalization_error("PROCESSING_JOB_INVALID")

    _persist_start_state(database_session, processing_job)
    try:
        if floor_plan.mime_type in SUPPORTED_SOURCE_MIME_TYPES:
            if g1_page is not None:
                raise _normalization_error("G1_RESULT_MISMATCH")
            source_path, source_mime_type = _resolve_uploaded_raster(
                upload_directory=upload_directory,
                floor_plan=floor_plan,
            )
        elif floor_plan.mime_type == "application/pdf":
            if g1_page is None:
                raise _normalization_error("G1_RESULT_MISMATCH")
            source_path = _g1_reference_and_path(
                g1_page,
                processed_directory=processed_directory,
                floor_plan_id=floor_plan.id,
                processing_job_id=processing_job.id,
            )
            source_mime_type = "image/png"
        else:
            raise _normalization_error("UNSUPPORTED_SOURCE")

        normalized = normalize_image(
            source_path=source_path,
            source_mime_type=source_mime_type,
            processed_directory=processed_directory,
            floor_plan_id=floor_plan.id,
            processing_job_id=processing_job.id,
            maximum_dimension=maximum_dimension,
        )
        page_number = g1_page.page_number if isinstance(g1_page, ConvertedPdfPage) else 1
        register_processing_artifact(
            database_session,
            processing_job=processing_job,
            floor_plan_id=floor_plan.id,
            page_number=page_number,
            artifact_kind="normalized_image",
            processed_directory=processed_directory,
            relative_path=normalized.output_reference,
            mime_type=normalized.output_mime_type,
        )
        database_session.commit()
        return normalized
    except ProcessingArtifactError:
        if "normalized" in locals():
            _remove_partial_output(normalized.absolute_output_path)
        _persist_failure_state(database_session, processing_job)
        raise _normalization_error("ARTIFACT_REGISTRATION_FAILED") from None
    except ImageNormalizationError:
        _persist_failure_state(database_session, processing_job)
        raise
