from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.ai.preprocessing.config import (
    PreprocessingConfigurationError,
    PreprocessingError,
    PreprocessingParameters,
)
from app.models import FloorPlan, ProcessingJob
from app.services.image_normalization import NormalizedImage


MAXIMUM_DIMENSION = 4096
MAXIMUM_SOURCE_BYTES = 100_000_000
NORMALIZED_MIME_TYPE = "image/png"
PROCESSING_JOB_TYPE = "floor_plan_analysis"
SAFE_PREPROCESSING_FAILURE_MESSAGE = "Floor-plan preprocessing failed."
NORMALIZED_REFERENCE_PATTERN = re.compile(
    r"^normalized/floor-plan-(?P<floor_plan_id>[1-9][0-9]*)/"
    r"job-(?P<job_id>[1-9][0-9]*)/image\.png$"
)

ERROR_MESSAGES = {
    "INVALID_CONFIGURATION": "The preprocessing configuration is invalid.",
    "INVALID_IDENTIFIERS": "The preprocessing identifiers are invalid.",
    "G2_RESULT_MISMATCH": "The normalized image does not match this job.",
    "UNSAFE_SOURCE": "The normalized image source is unsafe.",
    "SOURCE_UNAVAILABLE": "The normalized image is unavailable.",
    "INVALID_PNG_CONTENT": "The normalized image is not a valid RGB PNG.",
    "UNSAFE_DIMENSIONS": "The normalized image dimensions are unsafe.",
    "DECODE_FAILED": "The normalized image could not be decoded.",
    "GRAYSCALE_FAILED": "The floor-plan grayscale stage failed.",
    "DENOISING_FAILED": "The floor-plan denoising stage failed.",
    "GAUSSIAN_FAILED": "The floor-plan Gaussian stage failed.",
    "THRESHOLD_FAILED": "The floor-plan threshold stage failed.",
    "INVALID_PROCESSED_DIRECTORY": "The processed-file directory is invalid.",
    "OUTPUT_COLLISION": "A preprocessing output already exists.",
    "OUTPUT_ENCODING_FAILED": "A preprocessing output could not be encoded.",
    "OUTPUT_WRITE_FAILED": "A preprocessing output could not be stored.",
    "OUTPUT_CLEANUP_FAILED": "Failed preprocessing outputs could not be cleaned up safely.",
    "PROCESSING_JOB_INVALID": "The processing job cannot preprocess this image.",
    "JOB_FAILURE_PERSISTENCE_FAILED": "The preprocessing failure state could not be saved.",
}


def _error(code: str) -> PreprocessingError:
    return PreprocessingError(code, ERROR_MESSAGES[code])


@dataclass(frozen=True)
class PreprocessedImage:
    width: int
    height: int
    grayscale: np.ndarray
    denoised: np.ndarray
    blurred: np.ndarray | None
    thresholded: np.ndarray
    gaussian_applied: bool
    threshold_mode: str
    actual_threshold: float
    inverted: bool
    parameters: PreprocessingParameters
    source_reference: str | None = None
    grayscale_reference: str | None = None
    denoised_reference: str | None = None
    blurred_reference: str | None = None
    thresholded_reference: str | None = None


def _validated_parameters(
    parameters: PreprocessingParameters | None,
) -> PreprocessingParameters:
    if parameters is None:
        return PreprocessingParameters()
    if not isinstance(parameters, PreprocessingParameters):
        raise _error("INVALID_CONFIGURATION")
    return parameters


def preprocess_image(
    normalized_rgb: np.ndarray,
    *,
    parameters: PreprocessingParameters | None = None,
) -> PreprocessedImage:
    """Run deterministic preprocessing on a decoded RGB uint8 image."""
    try:
        selected = _validated_parameters(parameters)
    except PreprocessingConfigurationError:
        raise _error("INVALID_CONFIGURATION") from None
    if (
        not isinstance(normalized_rgb, np.ndarray)
        or normalized_rgb.dtype != np.uint8
        or normalized_rgb.ndim != 3
        or normalized_rgb.shape[2] != 3
        or normalized_rgb.shape[0] <= 0
        or normalized_rgb.shape[1] <= 0
    ):
        raise _error("INVALID_PNG_CONTENT")
    height, width = normalized_rgb.shape[:2]
    if max(width, height) > MAXIMUM_DIMENSION:
        raise _error("UNSAFE_DIMENSIONS")

    try:
        grayscale = cv2.cvtColor(normalized_rgb, cv2.COLOR_RGB2GRAY)
    except Exception:
        raise _error("GRAYSCALE_FAILED") from None
    if grayscale.dtype != np.uint8 or grayscale.shape != (height, width):
        raise _error("GRAYSCALE_FAILED")

    try:
        denoised = cv2.medianBlur(grayscale, selected.median_kernel_size)
    except Exception:
        raise _error("DENOISING_FAILED") from None
    if denoised.dtype != np.uint8 or denoised.shape != grayscale.shape:
        raise _error("DENOISING_FAILED")

    blurred = None
    threshold_input = denoised
    if selected.gaussian_blur_enabled:
        try:
            blurred = cv2.GaussianBlur(
                denoised,
                (selected.gaussian_kernel_size, selected.gaussian_kernel_size),
                selected.gaussian_sigma,
            )
        except Exception:
            raise _error("GAUSSIAN_FAILED") from None
        if blurred.dtype != np.uint8 or blurred.shape != grayscale.shape:
            raise _error("GAUSSIAN_FAILED")
        threshold_input = blurred

    threshold_type = cv2.THRESH_BINARY
    threshold_value = float(selected.fixed_threshold)
    if selected.threshold_mode == "otsu":
        threshold_type |= cv2.THRESH_OTSU
        threshold_value = 0.0
    if selected.invert_binary:
        threshold_type = (
            cv2.THRESH_BINARY_INV
            | (cv2.THRESH_OTSU if selected.threshold_mode == "otsu" else 0)
        )
    try:
        actual_threshold, thresholded = cv2.threshold(
            threshold_input,
            threshold_value,
            255,
            threshold_type,
        )
    except Exception:
        raise _error("THRESHOLD_FAILED") from None
    if (
        thresholded.dtype != np.uint8
        or thresholded.shape != grayscale.shape
        or not np.isin(thresholded, (0, 255)).all()
    ):
        raise _error("THRESHOLD_FAILED")

    return PreprocessedImage(
        width=width,
        height=height,
        grayscale=grayscale,
        denoised=denoised,
        blurred=blurred,
        thresholded=thresholded,
        gaussian_applied=selected.gaussian_blur_enabled,
        threshold_mode=selected.threshold_mode,
        actual_threshold=float(actual_threshold),
        inverted=selected.invert_binary,
        parameters=selected,
    )


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_reference(
    reference: str,
    *,
    floor_plan_id: int,
    processing_job_id: int,
) -> PurePosixPath:
    if not isinstance(reference, str) or not reference:
        raise _error("G2_RESULT_MISMATCH")
    portable = PurePosixPath(reference)
    windows = PureWindowsPath(reference)
    match = NORMALIZED_REFERENCE_PATTERN.fullmatch(reference)
    if (
        portable.is_absolute()
        or windows.is_absolute()
        or any(part in {"", ".", ".."} for part in portable.parts)
        or match is None
        or int(match.group("floor_plan_id")) != floor_plan_id
        or int(match.group("job_id")) != processing_job_id
    ):
        raise _error("G2_RESULT_MISMATCH")
    return portable


def _resolve_source(
    normalized_source: NormalizedImage | str,
    *,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
) -> tuple[Path, Path, str, int | None, int | None]:
    if not (
        _is_positive_integer(floor_plan_id)
        and _is_positive_integer(processing_job_id)
    ):
        raise _error("INVALID_IDENTIFIERS")
    supplied_path = None
    expected_width = expected_height = None
    if isinstance(normalized_source, NormalizedImage):
        if (
            normalized_source.floor_plan_id != floor_plan_id
            or normalized_source.processing_job_id != processing_job_id
            or normalized_source.output_mime_type != NORMALIZED_MIME_TYPE
            or not _is_positive_integer(normalized_source.normalized_width)
            or not _is_positive_integer(normalized_source.normalized_height)
            or max(
                normalized_source.normalized_width,
                normalized_source.normalized_height,
            )
            > MAXIMUM_DIMENSION
        ):
            raise _error("G2_RESULT_MISMATCH")
        reference = normalized_source.output_reference
        supplied_path = normalized_source.absolute_output_path
        expected_width = normalized_source.normalized_width
        expected_height = normalized_source.normalized_height
    elif isinstance(normalized_source, str):
        reference = normalized_source
    else:
        raise _error("G2_RESULT_MISMATCH")
    portable = _validate_reference(
        reference,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
    )
    try:
        configured_root = Path(processed_directory)
        if configured_root == Path("."):
            raise ValueError
        root = configured_root.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _error("INVALID_PROCESSED_DIRECTORY") from None
    if not root.is_dir():
        raise _error("INVALID_PROCESSED_DIRECTORY")
    try:
        source = root.joinpath(*portable.parts).resolve(strict=True)
    except (OSError, RuntimeError):
        raise _error("SOURCE_UNAVAILABLE") from None
    if not source.is_relative_to(root) or not source.is_file():
        raise _error("UNSAFE_SOURCE")
    if supplied_path is not None:
        try:
            if Path(supplied_path).resolve(strict=True) != source:
                raise _error("G2_RESULT_MISMATCH")
        except (OSError, RuntimeError, TypeError, ValueError):
            raise _error("G2_RESULT_MISMATCH") from None
    return root, source, portable.as_posix(), expected_width, expected_height


def _read_and_decode_png(source: Path) -> np.ndarray:
    try:
        size = source.stat().st_size
        if size <= 0 or size > MAXIMUM_SOURCE_BYTES:
            raise _error("SOURCE_UNAVAILABLE")
        with source.open("rb") as input_file:
            content = input_file.read(MAXIMUM_SOURCE_BYTES + 1)
    except PreprocessingError:
        raise
    except OSError:
        raise _error("SOURCE_UNAVAILABLE") from None
    if len(content) != size:
        raise _error("SOURCE_UNAVAILABLE")
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _error("INVALID_PNG_CONTENT")
    try:
        decoded = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    except Exception:
        raise _error("DECODE_FAILED") from None
    if decoded is None:
        raise _error("DECODE_FAILED")
    if decoded.dtype != np.uint8 or decoded.ndim != 3 or decoded.shape[2] != 3:
        raise _error("INVALID_PNG_CONTENT")
    height, width = decoded.shape[:2]
    if width <= 0 or height <= 0 or max(width, height) > MAXIMUM_DIMENSION:
        raise _error("UNSAFE_DIMENSIONS")
    try:
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    except Exception:
        raise _error("DECODE_FAILED") from None


def _debug_destinations(
    root: Path,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    include_blurred: bool,
) -> list[tuple[str, Path]]:
    relative_directory = PurePosixPath(
        "preprocessed",
        f"floor-plan-{floor_plan_id}",
        f"job-{processing_job_id}",
    )
    try:
        directory = root.joinpath(*relative_directory.parts)
        directory.mkdir(parents=True, exist_ok=True)
        directory = directory.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _error("INVALID_PROCESSED_DIRECTORY") from None
    if not directory.is_relative_to(root):
        raise _error("INVALID_PROCESSED_DIRECTORY")
    names = ["grayscale", "denoised"]
    if include_blurred:
        names.append("blurred")
    names.append("thresholded")
    destinations = [(name, directory / f"{name}.png") for name in names]
    if any(path.exists() for _, path in destinations):
        raise _error("OUTPUT_COLLISION")
    return destinations


def _cleanup_outputs(paths: list[Path]) -> None:
    cleanup_failed = False
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            cleanup_failed = True
    if cleanup_failed:
        raise _error("OUTPUT_CLEANUP_FAILED")


def _save_debug_outputs(
    result: PreprocessedImage,
    *,
    root: Path,
    floor_plan_id: int,
    processing_job_id: int,
) -> dict[str, str | None]:
    destinations = _debug_destinations(
        root,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        include_blurred=result.blurred is not None,
    )
    arrays = {
        "grayscale": result.grayscale,
        "denoised": result.denoised,
        "blurred": result.blurred,
        "thresholded": result.thresholded,
    }
    created: list[Path] = []
    references: dict[str, str | None] = {"blurred": None}
    try:
        for name, destination in destinations:
            try:
                encoded_ok, encoded = cv2.imencode(".png", arrays[name])
            except Exception:
                raise _error("OUTPUT_ENCODING_FAILED") from None
            if not encoded_ok or encoded.size == 0:
                raise _error("OUTPUT_ENCODING_FAILED")
            try:
                with destination.open("xb") as output:
                    written = output.write(encoded.tobytes())
                    if written != encoded.nbytes:
                        raise OSError("incomplete write")
            except FileExistsError:
                raise _error("OUTPUT_COLLISION") from None
            except OSError:
                created.append(destination)
                raise _error("OUTPUT_WRITE_FAILED") from None
            created.append(destination)
            references[name] = destination.relative_to(root).as_posix()
    except PreprocessingError as original_error:
        try:
            _cleanup_outputs(created)
        except PreprocessingError:
            raise
        raise original_error
    return references


def preprocess_normalized_image(
    normalized_source: NormalizedImage | str,
    *,
    processed_directory: Path,
    floor_plan_id: int,
    processing_job_id: int,
    parameters: PreprocessingParameters | None = None,
) -> PreprocessedImage:
    """Validate and preprocess only a G2 normalized PNG reference."""
    try:
        selected = _validated_parameters(parameters)
    except PreprocessingConfigurationError:
        raise _error("INVALID_CONFIGURATION") from None
    root, source, reference, expected_width, expected_height = _resolve_source(
        normalized_source,
        processed_directory=processed_directory,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
    )
    rgb = _read_and_decode_png(source)
    height, width = rgb.shape[:2]
    if (
        expected_width is not None
        and (expected_width != width or expected_height != height)
    ):
        raise _error("G2_RESULT_MISMATCH")
    result = preprocess_image(rgb, parameters=selected)
    references = {
        "grayscale": None,
        "denoised": None,
        "blurred": None,
        "thresholded": None,
    }
    if selected.save_debug_outputs:
        references = _save_debug_outputs(
            result,
            root=root,
            floor_plan_id=floor_plan_id,
            processing_job_id=processing_job_id,
        )
    return PreprocessedImage(
        **{
            **result.__dict__,
            "source_reference": reference,
            "grayscale_reference": references["grayscale"],
            "denoised_reference": references["denoised"],
            "blurred_reference": references["blurred"],
            "thresholded_reference": references["thresholded"],
        }
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
    processing_job.error_message = SAFE_PREPROCESSING_FAILURE_MESSAGE
    try:
        database_session.add(processing_job)
        database_session.commit()
    except Exception:
        _rollback_quietly(database_session)
        raise _error("JOB_FAILURE_PERSISTENCE_FAILED") from None


def preprocess_processing_job_image(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    floor_plan: FloorPlan,
    normalized_source: NormalizedImage | str,
    processed_directory: Path,
    parameters: PreprocessingParameters | None = None,
) -> PreprocessedImage:
    """Preprocess a processing job without advancing its successful state."""
    if not (
        _is_positive_integer(processing_job.id)
        and _is_positive_integer(floor_plan.id)
        and processing_job.floor_plan_id == floor_plan.id
        and processing_job.job_type == PROCESSING_JOB_TYPE
        and processing_job.status == "processing"
    ):
        raise _error("PROCESSING_JOB_INVALID")
    try:
        return preprocess_normalized_image(
            normalized_source,
            processed_directory=processed_directory,
            floor_plan_id=floor_plan.id,
            processing_job_id=processing_job.id,
            parameters=parameters,
        )
    except PreprocessingError:
        _persist_failure(database_session, processing_job)
        raise
    except PreprocessingConfigurationError:
        _persist_failure(database_session, processing_job)
        raise _error("INVALID_CONFIGURATION") from None
