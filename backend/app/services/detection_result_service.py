from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DetectedSymbol, User, Wall
from app.repositories.detection_result_repository import (
    find_detection_context,
    find_owned_detection_context,
    list_current_walls,
    list_versioned_symbols,
)
from app.repositories.detection_review_repository import list_latest_reviews
from app.services.symbol_persistence import PersistedDetectedSymbolRecord
from app.services.wall_persistence import PersistedWallRecord


ERROR_MESSAGES = {
    "INVALID_FLOOR_PLAN_ID": "The floor-plan identifier is invalid.",
    "INVALID_PROCESSING_JOB_ID": "The processing-job identifier is invalid.",
    "DETECTION_RESULTS_NOT_FOUND": "The requested detection results were not found.",
    "DETECTION_RESULTS_RETRIEVAL_FAILED": (
        "The detection results could not be retrieved."
    ),
}
MAXIMUM_BIGINT = 9_223_372_036_854_775_807


class DetectionResultServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class DetectionResults:
    floor_plan_id: int
    symbol_processing_job_id: int
    walls: tuple[PersistedWallRecord, ...]
    symbols: tuple[PersistedDetectedSymbolRecord, ...]
    latest_reviews: Mapping[int, "LatestDetectionReview"]


@dataclass(frozen=True)
class LatestDetectionReview:
    decision: str
    sequence_number: int
    reviewed_at: datetime


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise DetectionResultServiceError(code)
    return value


def _wall_record(wall: Wall) -> PersistedWallRecord:
    return PersistedWallRecord(
        **{
            field: getattr(wall, field)
            for field in PersistedWallRecord.__dataclass_fields__
        }
    )


def _symbol_record(symbol: DetectedSymbol) -> PersistedDetectedSymbolRecord:
    return PersistedDetectedSymbolRecord(
        **{
            field: getattr(symbol, field)
            for field in PersistedDetectedSymbolRecord.__dataclass_fields__
        }
    )


def retrieve_detection_results(
    database_session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    processing_job_id: int,
) -> DetectionResults:
    floor_plan_id = _positive_identifier(
        floor_plan_id,
        "INVALID_FLOOR_PLAN_ID",
    )
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
                "DETECTION_RESULTS_NOT_FOUND",
            )
            context = find_owned_detection_context(
                database_session,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
                owner_id=owner_id,
            )
        else:
            context = None

        if context is None:
            raise DetectionResultServiceError("DETECTION_RESULTS_NOT_FOUND")

        walls = tuple(
            _wall_record(wall)
            for wall in list_current_walls(
                database_session,
                floor_plan_id=floor_plan_id,
            )
        )
        symbols = tuple(
            _symbol_record(symbol)
            for symbol in list_versioned_symbols(
                database_session,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
            )
        )
        latest_reviews = MappingProxyType(
            {
                review.detected_symbol_id: LatestDetectionReview(
                    decision=review.decision,
                    sequence_number=review.sequence_number,
                    reviewed_at=review.created_at,
                )
                for review in list_latest_reviews(
                    database_session,
                    detected_symbol_ids=tuple(symbol.id for symbol in symbols),
                )
            }
        )
    except DetectionResultServiceError:
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise DetectionResultServiceError(
            "DETECTION_RESULTS_RETRIEVAL_FAILED"
        ) from None

    return DetectionResults(
        floor_plan_id=floor_plan_id,
        symbol_processing_job_id=processing_job_id,
        walls=walls,
        symbols=symbols,
        latest_reviews=latest_reviews,
    )
