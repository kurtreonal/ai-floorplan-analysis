from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.detection_result_repository import (
    find_detection_context,
    find_owned_detection_context,
)
from app.services.image_normalization import (
    DEFAULT_MAXIMUM_DIMENSION,
    MAX_SOURCE_PIXEL_COUNT,
)


MAXIMUM_BIGINT = 9_223_372_036_854_775_807
MAXIMUM_REVIEW_IMAGE_BYTES = 64 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ERROR_MESSAGES = {
    "INVALID_FLOOR_PLAN_ID": "The floor-plan identifier is invalid.",
    "INVALID_PROCESSING_JOB_ID": "The processing-job identifier is invalid.",
    "REVIEW_IMAGE_NOT_FOUND": "The requested review image was not found.",
    "REVIEW_IMAGE_UNAVAILABLE": "The review image could not be retrieved.",
}


class ReviewImageServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class ReviewImage:
    content: bytes
    width: int
    height: int
    media_type: str = "image/png"


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise ReviewImageServiceError(code)
    return value


def _resolve_review_image_path(
    processed_directory: Path,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> Path:
    try:
        configured_root = Path(processed_directory)
        if configured_root == Path("."):
            raise ValueError
        processed_root = configured_root.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None

    if not processed_root.is_dir():
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")

    expected = (
        processed_root
        / "normalized"
        / f"floor-plan-{floor_plan_id}"
        / f"job-{processing_job_id}"
        / "image.png"
    )
    try:
        resolved = expected.resolve(strict=True)
    except FileNotFoundError:
        raise ReviewImageServiceError("REVIEW_IMAGE_NOT_FOUND") from None
    except (OSError, RuntimeError, ValueError):
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None

    if (
        not resolved.is_relative_to(processed_root)
        or resolved != expected
        or resolved.suffix.casefold() != ".png"
        or not resolved.is_file()
    ):
        raise ReviewImageServiceError("REVIEW_IMAGE_NOT_FOUND")
    return resolved


def _read_and_validate_png(image_path: Path) -> ReviewImage:
    try:
        file_size = image_path.stat().st_size
        if file_size <= 0:
            raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")
        if file_size > MAXIMUM_REVIEW_IMAGE_BYTES:
            raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")
        content = image_path.read_bytes()
    except ReviewImageServiceError:
        raise
    except OSError:
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None

    if len(content) != file_size or not content.startswith(PNG_SIGNATURE):
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG" or image.mode != "RGB":
                raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or max(width, height) > DEFAULT_MAXIMUM_DIMENSION
                or width * height > MAX_SOURCE_PIXEL_COUNT
            ):
                raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE")
            image.load()
    except ReviewImageServiceError:
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None
    except Exception:
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None

    return ReviewImage(content=content, width=width, height=height)


def retrieve_review_image(
    database_session: Session,
    *,
    current_user: User,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
) -> ReviewImage:
    floor_plan_id = _positive_identifier(floor_plan_id, "INVALID_FLOOR_PLAN_ID")
    processing_job_id = _positive_identifier(
        processing_job_id,
        "INVALID_PROCESSING_JOB_ID",
    )
    role_name = getattr(getattr(current_user, "role", None), "name", None)

    try:
        if role_name == "ADMIN":
            context = find_detection_context(
                database_session,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
            )
        elif role_name == "DESIGNER":
            owner_id = _positive_identifier(
                getattr(current_user, "id", None),
                "REVIEW_IMAGE_NOT_FOUND",
            )
            context = find_owned_detection_context(
                database_session,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
                owner_id=owner_id,
            )
        else:
            context = None
    except ReviewImageServiceError:
        raise
    except SQLAlchemyError:
        raise ReviewImageServiceError("REVIEW_IMAGE_UNAVAILABLE") from None

    if context is None:
        raise ReviewImageServiceError("REVIEW_IMAGE_NOT_FOUND")

    image_path = _resolve_review_image_path(
        processed_directory,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
    )
    return _read_and_validate_png(image_path)
