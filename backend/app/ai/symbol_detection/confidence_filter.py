from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from app.ai.preprocessing.pipeline import MAXIMUM_DIMENSION
from app.ai.symbol_detection.inference import (
    MAXIMUM_DETECTIONS,
    SymbolBoundingBox,
    SymbolCenter,
    SymbolInferenceResult,
    SymbolPrediction,
)
from app.core.config import Settings, get_settings


DETECTED_STATUS = "detected"
NEEDS_REVIEW_STATUS = "needs_review"
SAFE_CONFIDENCE_FILTER_ERROR_MESSAGE = (
    "Symbol confidence classification could not be completed."
)
ERROR_CODES = frozenset(
    {
        "INVALID_INFERENCE_RESULT",
        "INVALID_CONFIDENCE_THRESHOLD",
    }
)


class SymbolConfidenceFilterError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError("Unknown symbol-confidence filter error code.")
        self.code = code
        self.message = SAFE_CONFIDENCE_FILTER_ERROR_MESSAGE
        super().__init__(self.message)


@dataclass(frozen=True)
class ClassifiedSymbolPrediction:
    prediction: SymbolPrediction
    status: str


@dataclass(frozen=True)
class SymbolConfidenceFilterResult:
    threshold: float
    predictions: tuple[ClassifiedSymbolPrediction, ...]
    image_width: int
    image_height: int
    maximum_detections: int
    detection_limit_reached: bool


def _error(code: str) -> SymbolConfidenceFilterError:
    return SymbolConfidenceFilterError(code)


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validated_threshold(threshold: object) -> float:
    if (
        not isinstance(threshold, Real)
        or isinstance(threshold, bool)
        or not math.isfinite(threshold)
        or threshold < 0.0
        or threshold > 1.0
    ):
        raise _error("INVALID_CONFIDENCE_THRESHOLD")
    return float(threshold)


def _valid_finite_number(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _validate_geometry(
    prediction: SymbolPrediction,
    *,
    image_width: int,
    image_height: int,
) -> None:
    bounding_box = prediction.bounding_box
    center = prediction.center
    if not isinstance(bounding_box, SymbolBoundingBox) or not isinstance(
        center, SymbolCenter
    ):
        raise _error("INVALID_INFERENCE_RESULT")
    coordinates = (
        bounding_box.x_min,
        bounding_box.y_min,
        bounding_box.x_max,
        bounding_box.y_max,
        center.x,
        center.y,
    )
    if not all(_valid_finite_number(value) for value in coordinates):
        raise _error("INVALID_INFERENCE_RESULT")
    if (
        bounding_box.x_min < 0.0
        or bounding_box.y_min < 0.0
        or bounding_box.x_max > image_width
        or bounding_box.y_max > image_height
        or bounding_box.x_min >= bounding_box.x_max
        or bounding_box.y_min >= bounding_box.y_max
        or center.x != (bounding_box.x_min + bounding_box.x_max) / 2.0
        or center.y != (bounding_box.y_min + bounding_box.y_max) / 2.0
    ):
        raise _error("INVALID_INFERENCE_RESULT")


def _validated_predictions(
    inference_result: SymbolInferenceResult,
) -> tuple[SymbolPrediction, ...]:
    if (
        not isinstance(inference_result, SymbolInferenceResult)
        or not _is_positive_integer(inference_result.image_width)
        or not _is_positive_integer(inference_result.image_height)
        or max(inference_result.image_width, inference_result.image_height)
        > MAXIMUM_DIMENSION
        or not isinstance(inference_result.predictions, tuple)
        or inference_result.maximum_detections != MAXIMUM_DETECTIONS
        or not isinstance(inference_result.detection_limit_reached, bool)
        or len(inference_result.predictions) > inference_result.maximum_detections
        or inference_result.detection_limit_reached
        != (len(inference_result.predictions) == inference_result.maximum_detections)
    ):
        raise _error("INVALID_INFERENCE_RESULT")

    for prediction in inference_result.predictions:
        if (
            not isinstance(prediction, SymbolPrediction)
            or not isinstance(prediction.class_id, int)
            or isinstance(prediction.class_id, bool)
            or prediction.class_id < 0
            or not isinstance(prediction.class_name, str)
            or not prediction.class_name
            or not _valid_finite_number(prediction.confidence)
            or prediction.confidence < 0.0
            or prediction.confidence > 1.0
        ):
            raise _error("INVALID_INFERENCE_RESULT")
        _validate_geometry(
            prediction,
            image_width=inference_result.image_width,
            image_height=inference_result.image_height,
        )
    return inference_result.predictions


def classify_symbol_predictions(
    inference_result: SymbolInferenceResult,
    *,
    threshold: float,
) -> SymbolConfidenceFilterResult:
    """Classify every validated I2 prediction without discarding or mutating it."""
    selected_threshold = _validated_threshold(threshold)
    predictions = _validated_predictions(inference_result)
    classified = tuple(
        ClassifiedSymbolPrediction(
            prediction=prediction,
            status=(
                DETECTED_STATUS
                if prediction.confidence >= selected_threshold
                else NEEDS_REVIEW_STATUS
            ),
        )
        for prediction in predictions
    )
    return SymbolConfidenceFilterResult(
        threshold=selected_threshold,
        predictions=classified,
        image_width=inference_result.image_width,
        image_height=inference_result.image_height,
        maximum_detections=inference_result.maximum_detections,
        detection_limit_reached=inference_result.detection_limit_reached,
    )


def classify_symbol_predictions_from_settings(
    inference_result: SymbolInferenceResult,
    *,
    settings: Settings | None = None,
) -> SymbolConfidenceFilterResult:
    """Classify I2 predictions with the configured application threshold."""
    try:
        source = settings if settings is not None else get_settings()
        threshold = source.yolo_confidence_threshold
    except Exception:
        raise _error("INVALID_CONFIDENCE_THRESHOLD") from None
    return classify_symbol_predictions(
        inference_result,
        threshold=threshold,
    )
