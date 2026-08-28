from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.ai.preprocessing import PreprocessedImage
from app.ai.preprocessing.pipeline import MAXIMUM_DIMENSION
from app.ai.symbol_detection.model_loader import (
    LoadedSymbolDetectionModel,
    SymbolClassMetadata,
    YOLOModelLoaderError,
    load_symbol_detection_model,
)
from app.models import FloorPlan, ProcessingJob


MAXIMUM_DETECTIONS = 300
PROCESSING_JOB_TYPE = "floor_plan_analysis"
SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE = "Floor-plan symbol inference failed."
ERROR_CODES = frozenset(
    {
        "INVALID_PROCESSED_IMAGE",
        "INVALID_LOADED_MODEL",
        "INFERENCE_FAILED",
        "INVALID_RESULT_COUNT",
        "INVALID_BOX_OUTPUT",
        "INVALID_CLASS_OUTPUT",
        "UNKNOWN_MODEL_CLASS",
        "INVALID_CONFIDENCE",
        "INVALID_COORDINATES",
        "PROCESSING_JOB_INVALID",
        "JOB_FAILURE_PERSISTENCE_FAILED",
    }
)

ModelLoader = Callable[[], LoadedSymbolDetectionModel]


class SymbolInferenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError("Unknown symbol-inference error code.")
        self.code = code
        self.message = SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE
        super().__init__(self.message)


@dataclass(frozen=True)
class SymbolBoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True)
class SymbolCenter:
    x: float
    y: float


@dataclass(frozen=True)
class SymbolPrediction:
    class_id: int
    class_name: str
    confidence: float
    bounding_box: SymbolBoundingBox
    center: SymbolCenter


@dataclass(frozen=True)
class SymbolInferenceResult:
    image_width: int
    image_height: int
    predictions: tuple[SymbolPrediction, ...]
    maximum_detections: int
    detection_limit_reached: bool


def _error(code: str) -> SymbolInferenceError:
    return SymbolInferenceError(code)


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _inference_image(processed_image: PreprocessedImage) -> np.ndarray:
    if not isinstance(processed_image, PreprocessedImage):
        raise _error("INVALID_PROCESSED_IMAGE")
    thresholded = processed_image.thresholded
    if (
        not _is_positive_integer(processed_image.width)
        or not _is_positive_integer(processed_image.height)
        or max(processed_image.width, processed_image.height) > MAXIMUM_DIMENSION
        or not isinstance(thresholded, np.ndarray)
        or thresholded.dtype != np.uint8
        or thresholded.ndim != 2
        or thresholded.shape != (processed_image.height, processed_image.width)
        or thresholded.size == 0
        or not np.isin(thresholded, (0, 255)).all()
    ):
        raise _error("INVALID_PROCESSED_IMAGE")

    try:
        inference_image = np.repeat(thresholded[:, :, np.newaxis], 3, axis=2)
        inference_image = np.ascontiguousarray(inference_image, dtype=np.uint8)
    except Exception:
        raise _error("INVALID_PROCESSED_IMAGE") from None
    if (
        inference_image.shape
        != (processed_image.height, processed_image.width, 3)
        or not inference_image.flags.c_contiguous
        or np.shares_memory(inference_image, thresholded)
    ):
        raise _error("INVALID_PROCESSED_IMAGE")
    return inference_image


def _class_names(
    loaded_model: LoadedSymbolDetectionModel,
) -> dict[int, str]:
    try:
        model = loaded_model.model
        predict = getattr(model, "predict", None)
    except Exception:
        raise _error("INVALID_LOADED_MODEL") from None
    if (
        not isinstance(loaded_model, LoadedSymbolDetectionModel)
        or model is None
        or not callable(predict)
        or loaded_model.task not in {None, "detect"}
        or not isinstance(loaded_model.classes, tuple)
        or not loaded_model.classes
    ):
        raise _error("INVALID_LOADED_MODEL")

    class_names: dict[int, str] = {}
    for metadata in loaded_model.classes:
        if (
            not isinstance(metadata, SymbolClassMetadata)
            or not isinstance(metadata.class_id, int)
            or isinstance(metadata.class_id, bool)
            or metadata.class_id < 0
            or not isinstance(metadata.name, str)
            or not metadata.name
            or metadata.class_id in class_names
        ):
            raise _error("INVALID_LOADED_MODEL")
        class_names[metadata.class_id] = metadata.name
    return class_names


def _numeric_array(value: object, *, code: str) -> np.ndarray:
    try:
        candidate = value
        detach = getattr(candidate, "detach", None)
        if callable(detach):
            candidate = detach()
        cpu = getattr(candidate, "cpu", None)
        if callable(cpu):
            candidate = cpu()
        numpy_method = getattr(candidate, "numpy", None)
        if callable(numpy_method):
            candidate = numpy_method()
        array = np.asarray(candidate)
    except Exception:
        raise _error(code) from None
    if array.dtype.kind not in "iuf":
        raise _error(code)
    return array


def _single_result(raw_results: object) -> object:
    try:
        results = tuple(raw_results)
    except Exception:
        raise _error("INVALID_RESULT_COUNT") from None
    if len(results) != 1:
        raise _error("INVALID_RESULT_COUNT")
    return results[0]


def _validate_result_type(result: object) -> None:
    try:
        unexpected = (
            getattr(result, "masks", None),
            getattr(result, "obb", None),
            getattr(result, "probs", None),
        )
    except Exception:
        raise _error("INVALID_BOX_OUTPUT") from None
    if any(output is not None for output in unexpected):
        raise _error("INVALID_BOX_OUTPUT")


def _empty_result(
    processed_image: PreprocessedImage,
) -> SymbolInferenceResult:
    return SymbolInferenceResult(
        image_width=processed_image.width,
        image_height=processed_image.height,
        predictions=(),
        maximum_detections=MAXIMUM_DETECTIONS,
        detection_limit_reached=False,
    )


def _convert_result(
    result: object,
    *,
    processed_image: PreprocessedImage,
    class_names: dict[int, str],
) -> SymbolInferenceResult:
    _validate_result_type(result)
    try:
        boxes = result.boxes
    except Exception:
        raise _error("INVALID_BOX_OUTPUT") from None
    if boxes is None:
        return _empty_result(processed_image)
    if isinstance(boxes, (list, tuple)) and not boxes:
        return _empty_result(processed_image)

    try:
        xyxy_raw = boxes.xyxy
        confidence_raw = boxes.conf
        class_raw = boxes.cls
    except Exception:
        raise _error("INVALID_BOX_OUTPUT") from None

    coordinates = _numeric_array(xyxy_raw, code="INVALID_BOX_OUTPUT")
    confidences = _numeric_array(confidence_raw, code="INVALID_CONFIDENCE")
    classes = _numeric_array(class_raw, code="INVALID_CLASS_OUTPUT")
    if coordinates.ndim != 2 or coordinates.shape[1:] != (4,):
        raise _error("INVALID_BOX_OUTPUT")
    if confidences.ndim != 1:
        raise _error("INVALID_CONFIDENCE")
    if classes.ndim != 1:
        raise _error("INVALID_CLASS_OUTPUT")
    count = coordinates.shape[0]
    if count != confidences.shape[0] or count != classes.shape[0]:
        raise _error("INVALID_BOX_OUTPUT")
    if count > MAXIMUM_DETECTIONS:
        raise _error("INVALID_BOX_OUTPUT")
    if count == 0:
        return _empty_result(processed_image)

    try:
        finite_coordinates = np.isfinite(coordinates).all()
        finite_confidences = np.isfinite(confidences).all()
        finite_classes = np.isfinite(classes).all()
    except Exception:
        raise _error("INVALID_BOX_OUTPUT") from None
    if not finite_coordinates:
        raise _error("INVALID_COORDINATES")
    if not finite_confidences or np.any((confidences < 0.0) | (confidences > 1.0)):
        raise _error("INVALID_CONFIDENCE")
    if not finite_classes or np.any(classes < 0) or np.any(classes != np.floor(classes)):
        raise _error("INVALID_CLASS_OUTPUT")

    predictions = []
    for raw_box, raw_confidence, raw_class_id in zip(
        coordinates,
        confidences,
        classes,
        strict=True,
    ):
        x_min, y_min, x_max, y_max = (float(value) for value in raw_box)
        if (
            x_min < 0.0
            or y_min < 0.0
            or x_max > processed_image.width
            or y_max > processed_image.height
            or x_min >= x_max
            or y_min >= y_max
        ):
            raise _error("INVALID_COORDINATES")
        class_id = int(raw_class_id)
        class_name = class_names.get(class_id)
        if class_name is None:
            raise _error("UNKNOWN_MODEL_CLASS")
        bounding_box = SymbolBoundingBox(
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
        )
        predictions.append(
            SymbolPrediction(
                class_id=class_id,
                class_name=class_name,
                confidence=float(raw_confidence),
                bounding_box=bounding_box,
                center=SymbolCenter(
                    x=(x_min + x_max) / 2.0,
                    y=(y_min + y_max) / 2.0,
                ),
            )
        )
    return SymbolInferenceResult(
        image_width=processed_image.width,
        image_height=processed_image.height,
        predictions=tuple(predictions),
        maximum_detections=MAXIMUM_DETECTIONS,
        detection_limit_reached=count == MAXIMUM_DETECTIONS,
    )


def run_symbol_inference(
    processed_image: PreprocessedImage,
    loaded_model: LoadedSymbolDetectionModel,
) -> SymbolInferenceResult:
    """Run one in-memory prediction and return validated pixel detections."""
    inference_image = _inference_image(processed_image)
    class_names = _class_names(loaded_model)
    try:
        raw_results = loaded_model.model.predict(
            source=inference_image,
            conf=0.0,
            max_det=MAXIMUM_DETECTIONS,
            verbose=False,
            save=False,
            stream=False,
        )
    except Exception:
        raise _error("INFERENCE_FAILED") from None
    result = _single_result(raw_results)
    return _convert_result(
        result,
        processed_image=processed_image,
        class_names=class_names,
    )


def _rollback_quietly(database_session: Session) -> None:
    try:
        database_session.rollback()
    except Exception:
        pass


def _persist_failure(
    database_session: Session,
    processing_job: ProcessingJob,
) -> None:
    processing_job.status = "failed"
    processing_job.error_message = SAFE_SYMBOL_INFERENCE_FAILURE_MESSAGE
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _error("JOB_FAILURE_PERSISTENCE_FAILED") from None


def run_processing_job_symbol_inference(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    floor_plan: FloorPlan,
    processed_image: PreprocessedImage,
    loaded_model: LoadedSymbolDetectionModel | None = None,
    model_loader: ModelLoader = load_symbol_detection_model,
) -> SymbolInferenceResult:
    """Run I2 for a valid processing job without advancing successful state."""
    if not (
        isinstance(processing_job, ProcessingJob)
        and isinstance(floor_plan, FloorPlan)
        and _is_positive_integer(processing_job.id)
        and _is_positive_integer(floor_plan.id)
        and processing_job.floor_plan_id == floor_plan.id
        and processing_job.job_type == PROCESSING_JOB_TYPE
        and processing_job.status == "processing"
    ):
        raise _error("PROCESSING_JOB_INVALID")

    try:
        selected_model = loaded_model if loaded_model is not None else model_loader()
        return run_symbol_inference(processed_image, selected_model)
    except YOLOModelLoaderError:
        _persist_failure(database_session, processing_job)
        raise _error("INVALID_LOADED_MODEL") from None
    except SymbolInferenceError:
        _persist_failure(database_session, processing_job)
        raise
    except Exception:
        _persist_failure(database_session, processing_job)
        raise _error("INVALID_LOADED_MODEL") from None
