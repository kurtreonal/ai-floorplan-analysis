from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.preprocessing.pipeline import MAXIMUM_DIMENSION
from app.ai.symbol_detection.confidence_filter import (
    DETECTED_STATUS,
    NEEDS_REVIEW_STATUS,
    ClassifiedSymbolPrediction,
    SymbolConfidenceFilterResult,
)
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolPrediction,
)
from app.models import DetectedSymbol
from app.repositories.detected_symbol_repository import (
    add_detected_symbols,
    delete_processing_job_detections,
    find_processing_job,
    list_detected_symbols,
    lock_floor_plan,
)
from app.services.processing_job_service import FLOOR_PLAN_ANALYSIS_JOB_TYPE


ERROR_MESSAGES = {
    "INVALID_FLOOR_PLAN_ID": "The floor-plan identifier is invalid.",
    "INVALID_PROCESSING_JOB_ID": "The processing-job identifier is invalid.",
    "INVALID_CLASSIFIED_RESULT": "The classified symbol result is invalid.",
    "FLOOR_PLAN_NOT_FOUND": "The floor plan does not exist.",
    "PROCESSING_JOB_NOT_FOUND": "The processing job does not exist.",
    "PROCESSING_JOB_FLOOR_PLAN_MISMATCH": (
        "The processing job does not belong to the floor plan."
    ),
    "INVALID_PROCESSING_JOB_TYPE": "The processing-job type is invalid.",
    "INVALID_PROCESSING_JOB_STATUS": "The processing job is not processing.",
    "SYMBOL_PERSISTENCE_FAILED": "Detected symbols could not be persisted.",
    "SYMBOL_RETRIEVAL_FAILED": "Detected symbols could not be retrieved.",
}
ALLOWED_STATUSES = frozenset((DETECTED_STATUS, NEEDS_REVIEW_STATUS))
MAXIMUM_BIGINT = 9_223_372_036_854_775_807
MAXIMUM_INTEGER = 2_147_483_647
MAXIMUM_CLASS_NAME_LENGTH = 255


class SymbolPersistenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


def _error(code: str) -> SymbolPersistenceError:
    return SymbolPersistenceError(code)


@dataclass(frozen=True)
class PersistedDetectedSymbolRecord:
    id: int
    floor_plan_id: int
    processing_job_id: int
    prediction_index: int
    status: str
    original_class_id: int
    original_class_name: str
    original_confidence: float
    confidence_threshold: float
    image_width_pixels: int
    image_height_pixels: int
    bounding_box_x_min_pixels: float
    bounding_box_y_min_pixels: float
    bounding_box_x_max_pixels: float
    bounding_box_y_max_pixels: float
    center_x_pixels: float
    center_y_pixels: float
    maximum_detections: int
    detection_limit_reached: bool
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "processing_job_id": self.processing_job_id,
            "prediction_index": self.prediction_index,
            "status": self.status,
            "original_class_id": self.original_class_id,
            "original_class_name": self.original_class_name,
            "original_confidence": self.original_confidence,
            "confidence_threshold": self.confidence_threshold,
            "image_width_pixels": self.image_width_pixels,
            "image_height_pixels": self.image_height_pixels,
            "bounding_box_x_min_pixels": self.bounding_box_x_min_pixels,
            "bounding_box_y_min_pixels": self.bounding_box_y_min_pixels,
            "bounding_box_x_max_pixels": self.bounding_box_x_max_pixels,
            "bounding_box_y_max_pixels": self.bounding_box_y_max_pixels,
            "center_x_pixels": self.center_x_pixels,
            "center_y_pixels": self.center_y_pixels,
            "maximum_detections": self.maximum_detections,
            "detection_limit_reached": self.detection_limit_reached,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class _PreparedDetectedSymbol:
    prediction_index: int
    status: str
    original_class_id: int
    original_class_name: str
    original_confidence: float
    confidence_threshold: float
    image_width_pixels: int
    image_height_pixels: int
    bounding_box_x_min_pixels: float
    bounding_box_y_min_pixels: float
    bounding_box_x_max_pixels: float
    bounding_box_y_max_pixels: float
    center_x_pixels: float
    center_y_pixels: float
    maximum_detections: int
    detection_limit_reached: bool


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0 or value > MAXIMUM_BIGINT:
        raise _error(code)
    return value


def _finite_number(value: object) -> float:
    if type(value) not in (int, float):
        raise _error("INVALID_CLASSIFIED_RESULT")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise _error("INVALID_CLASSIFIED_RESULT")
    return numeric


def _prepare_result(result: object) -> tuple[_PreparedDetectedSymbol, ...]:
    if (
        type(result) is not SymbolConfidenceFilterResult
        or type(result.image_width) is not int
        or type(result.image_height) is not int
        or result.image_width <= 0
        or result.image_height <= 0
        or max(result.image_width, result.image_height) > MAXIMUM_DIMENSION
        or type(result.maximum_detections) is not int
        or result.maximum_detections != MAXIMUM_DETECTIONS
        or type(result.detection_limit_reached) is not bool
        or not isinstance(result.predictions, tuple)
        or len(result.predictions) > result.maximum_detections
        or result.detection_limit_reached
        != (len(result.predictions) == result.maximum_detections)
    ):
        raise _error("INVALID_CLASSIFIED_RESULT")
    threshold = _finite_number(result.threshold)
    if not 0.0 <= threshold <= 1.0:
        raise _error("INVALID_CLASSIFIED_RESULT")

    prepared = []
    for prediction_index, classified in enumerate(result.predictions, start=1):
        if (
            type(classified) is not ClassifiedSymbolPrediction
            or classified.status not in ALLOWED_STATUSES
            or type(classified.prediction) is not SymbolPrediction
        ):
            raise _error("INVALID_CLASSIFIED_RESULT")
        prediction = classified.prediction
        if (
            type(prediction.class_id) is not int
            or prediction.class_id < 0
            or prediction.class_id > MAXIMUM_INTEGER
            or type(prediction.class_name) is not str
            or not prediction.class_name
            or len(prediction.class_name) > MAXIMUM_CLASS_NAME_LENGTH
            or "\x00" in prediction.class_name
            or prediction.class_name != prediction.class_name.strip()
            or type(prediction.bounding_box) is not SymbolBoundingBox
            or type(prediction.center) is not SymbolCenter
        ):
            raise _error("INVALID_CLASSIFIED_RESULT")
        confidence = _finite_number(prediction.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise _error("INVALID_CLASSIFIED_RESULT")
        expected_status = (
            DETECTED_STATUS if confidence >= threshold else NEEDS_REVIEW_STATUS
        )
        if classified.status != expected_status:
            raise _error("INVALID_CLASSIFIED_RESULT")
        box = prediction.bounding_box
        center = prediction.center
        x_min = _finite_number(box.x_min)
        y_min = _finite_number(box.y_min)
        x_max = _finite_number(box.x_max)
        y_max = _finite_number(box.y_max)
        center_x = _finite_number(center.x)
        center_y = _finite_number(center.y)
        if (
            x_min < 0.0
            or y_min < 0.0
            or x_max > result.image_width
            or y_max > result.image_height
            or x_min >= x_max
            or y_min >= y_max
            or center_x != (x_min + x_max) / 2.0
            or center_y != (y_min + y_max) / 2.0
        ):
            raise _error("INVALID_CLASSIFIED_RESULT")
        prepared.append(
            _PreparedDetectedSymbol(
                prediction_index=prediction_index,
                status=classified.status,
                original_class_id=prediction.class_id,
                original_class_name=prediction.class_name,
                original_confidence=confidence,
                confidence_threshold=threshold,
                image_width_pixels=result.image_width,
                image_height_pixels=result.image_height,
                bounding_box_x_min_pixels=x_min,
                bounding_box_y_min_pixels=y_min,
                bounding_box_x_max_pixels=x_max,
                bounding_box_y_max_pixels=y_max,
                center_x_pixels=center_x,
                center_y_pixels=center_y,
                maximum_detections=result.maximum_detections,
                detection_limit_reached=result.detection_limit_reached,
            )
        )
    return tuple(prepared)


def _record(symbol: DetectedSymbol) -> PersistedDetectedSymbolRecord:
    return PersistedDetectedSymbolRecord(
        **{
            field: getattr(symbol, field)
            for field in PersistedDetectedSymbolRecord.__dataclass_fields__
        }
    )


def replace_detected_symbols(
    database_session: Session,
    floor_plan_id: int,
    processing_job_id: int,
    result: SymbolConfidenceFilterResult,
) -> tuple[PersistedDetectedSymbolRecord, ...]:
    floor_plan_id = _positive_identifier(floor_plan_id, "INVALID_FLOOR_PLAN_ID")
    processing_job_id = _positive_identifier(
        processing_job_id,
        "INVALID_PROCESSING_JOB_ID",
    )
    prepared = _prepare_result(result)
    try:
        floor_plan = lock_floor_plan(database_session, floor_plan_id=floor_plan_id)
        if floor_plan is None:
            raise _error("FLOOR_PLAN_NOT_FOUND")
        processing_job = find_processing_job(
            database_session,
            processing_job_id=processing_job_id,
        )
        if processing_job is None:
            raise _error("PROCESSING_JOB_NOT_FOUND")
        if processing_job.floor_plan_id != floor_plan_id:
            raise _error("PROCESSING_JOB_FLOOR_PLAN_MISMATCH")
        if processing_job.job_type != FLOOR_PLAN_ANALYSIS_JOB_TYPE:
            raise _error("INVALID_PROCESSING_JOB_TYPE")
        if processing_job.status != "processing":
            raise _error("INVALID_PROCESSING_JOB_STATUS")
        delete_processing_job_detections(
            database_session,
            processing_job_id=processing_job_id,
        )
        symbols = tuple(
            DetectedSymbol(
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
                **item.__dict__,
            )
            for item in prepared
        )
        add_detected_symbols(database_session, symbols)
        database_session.commit()
        return tuple(_record(symbol) for symbol in symbols)
    except SymbolPersistenceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise _error("SYMBOL_PERSISTENCE_FAILED") from None


def retrieve_detected_symbols(
    database_session: Session,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[PersistedDetectedSymbolRecord, ...]:
    floor_plan_id = _positive_identifier(floor_plan_id, "INVALID_FLOOR_PLAN_ID")
    processing_job_id = _positive_identifier(
        processing_job_id,
        "INVALID_PROCESSING_JOB_ID",
    )
    try:
        return tuple(
            _record(symbol)
            for symbol in list_detected_symbols(
                database_session,
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
            )
        )
    except SQLAlchemyError:
        database_session.rollback()
        raise _error("SYMBOL_RETRIEVAL_FAILED") from None
