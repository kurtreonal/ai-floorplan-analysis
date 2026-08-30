from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ManualSymbol, User
from app.repositories.detection_result_repository import find_owned_detection_context
from app.repositories.manual_symbol_repository import (
    add_manual_symbol,
    find_manual_symbol_by_request,
    lock_manual_symbol_legend,
    lock_owned_manual_symbol_context,
)
from app.services.review_image_service import (
    ReviewImageServiceError,
    validate_review_image,
)


ERROR_MESSAGES = {
    "AUTHORIZATION_DENIED": "The authenticated user is not authorized for this action.",
    "MANUAL_SYMBOL_CONTEXT_NOT_FOUND": "The requested floor-plan review context was not found.",
    "SYMBOL_LEGEND_UNAVAILABLE": "The selected symbol legend is unavailable.",
    "MANUAL_SYMBOL_PLACEMENT_UNAVAILABLE": "Manual symbol placement is unavailable for this review context.",
    "INVALID_MANUAL_SYMBOL_POSITION": "The manual symbol position is invalid.",
    "PLACEMENT_REQUEST_CONFLICT": "The placement request identifier is already used for different content.",
    "MANUAL_SYMBOL_PERSISTENCE_FAILED": "The manual symbol could not be saved.",
}
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


class ManualSymbolServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class ManualSymbolRecord:
    id: int
    floor_plan_id: int
    processing_job_id: int
    created_by_user_id: int
    symbol_legend_id: int
    placement_request_id: str
    status: str
    class_id: int
    class_name: str
    center_x_pixels: float
    center_y_pixels: float
    image_width_pixels: int
    image_height_pixels: int
    created_at: datetime


@dataclass(frozen=True)
class ManualSymbolCreationResult:
    record: ManualSymbolRecord
    created: bool


def manual_symbol_record(symbol: ManualSymbol) -> ManualSymbolRecord:
    return ManualSymbolRecord(
        **{
            field: getattr(symbol, field)
            for field in ManualSymbolRecord.__dataclass_fields__
        }
    )


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise ManualSymbolServiceError(code)
    return value


def _request_uuid(value: object) -> str:
    try:
        if isinstance(value, bool):
            raise ValueError
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        raise ManualSymbolServiceError("MANUAL_SYMBOL_PERSISTENCE_FAILED") from None


def _coordinate(value: object) -> float:
    if type(value) not in (int, float):
        raise ManualSymbolServiceError("INVALID_MANUAL_SYMBOL_POSITION")
    number = float(value)
    if not math.isfinite(number):
        raise ManualSymbolServiceError("INVALID_MANUAL_SYMBOL_POSITION")
    return number


def _matches(
    symbol: ManualSymbol,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    symbol_legend_id: int,
    class_id: int,
    class_name: str,
    center_x: float,
    center_y: float,
    image_width: int,
    image_height: int,
) -> bool:
    return (
        symbol.floor_plan_id == floor_plan_id
        and symbol.processing_job_id == processing_job_id
        and symbol.symbol_legend_id == symbol_legend_id
        and symbol.class_id == class_id
        and symbol.class_name == class_name
        and symbol.center_x_pixels == center_x
        and symbol.center_y_pixels == center_y
        and symbol.image_width_pixels == image_width
        and symbol.image_height_pixels == image_height
        and symbol.status == "manually_added"
    )


def create_manual_symbol(
    database_session: Session,
    *,
    current_user: User,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
    placement_request_id: object,
    symbol_legend_id: int,
    center_x: object,
    center_y: object,
) -> ManualSymbolCreationResult:
    floor_plan_id = _positive_identifier(
        floor_plan_id,
        "MANUAL_SYMBOL_CONTEXT_NOT_FOUND",
    )
    processing_job_id = _positive_identifier(
        processing_job_id,
        "MANUAL_SYMBOL_CONTEXT_NOT_FOUND",
    )
    symbol_legend_id = _positive_identifier(
        symbol_legend_id,
        "SYMBOL_LEGEND_UNAVAILABLE",
    )
    request_id = _request_uuid(placement_request_id)
    x = _coordinate(center_x)
    y = _coordinate(center_y)
    if getattr(getattr(current_user, "role", None), "name", None) != "DESIGNER":
        raise ManualSymbolServiceError("AUTHORIZATION_DENIED")
    owner_id = _positive_identifier(
        getattr(current_user, "id", None),
        "MANUAL_SYMBOL_CONTEXT_NOT_FOUND",
    )

    match_values: dict[str, object] | None = None
    try:
        context = find_owned_detection_context(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            owner_id=owner_id,
        )
        if context is None:
            raise ManualSymbolServiceError("MANUAL_SYMBOL_CONTEXT_NOT_FOUND")
    except ManualSymbolServiceError:
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise ManualSymbolServiceError("MANUAL_SYMBOL_PERSISTENCE_FAILED") from None

    try:
        review_image = validate_review_image(
            processed_directory,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    except ReviewImageServiceError:
        raise ManualSymbolServiceError(
            "MANUAL_SYMBOL_PLACEMENT_UNAVAILABLE"
        ) from None
    try:
        locked_context = lock_owned_manual_symbol_context(
            database_session,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            owner_id=owner_id,
        )
        if locked_context is None:
            raise ManualSymbolServiceError("MANUAL_SYMBOL_CONTEXT_NOT_FOUND")
        legend = lock_manual_symbol_legend(
            database_session,
            symbol_legend_id=symbol_legend_id,
        )
        if legend is None or not legend.is_active:
            raise ManualSymbolServiceError("SYMBOL_LEGEND_UNAVAILABLE")
        if x < 0 or y < 0 or x > review_image.width or y > review_image.height:
            raise ManualSymbolServiceError("INVALID_MANUAL_SYMBOL_POSITION")
        existing = find_manual_symbol_by_request(
            database_session,
            created_by_user_id=owner_id,
            placement_request_id=request_id,
            lock=True,
        )
        match_values = {
            "floor_plan_id": floor_plan_id,
            "processing_job_id": processing_job_id,
            "symbol_legend_id": symbol_legend_id,
            "class_id": legend.class_id,
            "class_name": legend.name,
            "center_x": x,
            "center_y": y,
            "image_width": review_image.width,
            "image_height": review_image.height,
        }
        if existing is not None:
            if not _matches(existing, **match_values):
                raise ManualSymbolServiceError("PLACEMENT_REQUEST_CONFLICT")
            database_session.commit()
            return ManualSymbolCreationResult(
                record=manual_symbol_record(existing),
                created=False,
            )

        symbol = ManualSymbol(
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
            created_by_user_id=owner_id,
            symbol_legend_id=symbol_legend_id,
            placement_request_id=request_id,
            status="manually_added",
            class_id=legend.class_id,
            class_name=legend.name,
            center_x_pixels=x,
            center_y_pixels=y,
            image_width_pixels=review_image.width,
            image_height_pixels=review_image.height,
        )
        add_manual_symbol(database_session, symbol)
        database_session.commit()
        return ManualSymbolCreationResult(
            record=manual_symbol_record(symbol),
            created=True,
        )
    except ManualSymbolServiceError:
        database_session.rollback()
        raise
    except IntegrityError:
        database_session.rollback()
        try:
            existing = find_manual_symbol_by_request(
                database_session,
                created_by_user_id=owner_id,
                placement_request_id=request_id,
            )
            if (
                existing is not None
                and match_values is not None
                and _matches(existing, **match_values)
            ):
                return ManualSymbolCreationResult(
                    record=manual_symbol_record(existing),
                    created=False,
                )
        except SQLAlchemyError:
            database_session.rollback()
            raise ManualSymbolServiceError("MANUAL_SYMBOL_PERSISTENCE_FAILED") from None
        if existing is not None:
            raise ManualSymbolServiceError("PLACEMENT_REQUEST_CONFLICT")
        raise ManualSymbolServiceError("MANUAL_SYMBOL_PERSISTENCE_FAILED") from None
    except SQLAlchemyError:
        database_session.rollback()
        raise ManualSymbolServiceError("MANUAL_SYMBOL_PERSISTENCE_FAILED") from None
