from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

from app.ai.wall_detection.config import (
    INVALID_CONFIGURATION_MESSAGE,
    WallDetectionConfigurationError,
    WallDetectionError,
    WallDetectionParameters,
)

if TYPE_CHECKING:
    from app.ai.preprocessing.pipeline import PreprocessedImage


MAXIMUM_IMAGE_EDGE = 4096
ALGORITHM = "probabilistic_hough"
ERROR_MESSAGES = {
    "INVALID_CONFIGURATION": INVALID_CONFIGURATION_MESSAGE,
    "INVALID_PROCESSED_IMAGE_RESULT": "The G3 processed-image result is invalid.",
    "INVALID_DTYPE_OR_SHAPE": "The wall-detection image type or shape is invalid.",
    "NONBINARY_IMAGE": "The wall-detection image must contain only binary pixels.",
    "UNSAFE_DIMENSIONS": "The wall-detection image dimensions are unsafe.",
    "EDGE_DETECTION_FAILED": "Candidate wall edges could not be detected.",
    "HOUGH_DETECTION_FAILED": "Candidate wall lines could not be detected.",
    "MALFORMED_OPENCV_RESULT": "The wall detector returned an invalid result.",
    "INVALID_COORDINATES": "A candidate wall segment has invalid coordinates.",
}


def _error(code: str) -> WallDetectionError:
    return WallDetectionError(code, ERROR_MESSAGES[code])


@dataclass(frozen=True)
class PixelPoint:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class WallLineCandidate:
    candidate_id: int
    start: PixelPoint
    end: PixelPoint
    length_pixels: float
    angle_degrees: float

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "length_pixels": self.length_pixels,
            "angle_degrees": self.angle_degrees,
        }


@dataclass(frozen=True)
class CoordinateSpace:
    width: int
    height: int
    unit: str = "pixel"
    origin: str = "top_left"
    x_direction: str = "right"
    y_direction: str = "down"

    def to_dict(self) -> dict[str, object]:
        return {
            "unit": self.unit,
            "origin": self.origin,
            "x_direction": self.x_direction,
            "y_direction": self.y_direction,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class WallDetectionResult:
    coordinate_space: CoordinateSpace
    algorithm: str
    truncated: bool
    candidates: tuple[WallLineCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "coordinate_space": self.coordinate_space.to_dict(),
            "algorithm": self.algorithm,
            "truncated": self.truncated,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def _is_g3_result(value: object) -> bool:
    value_type = type(value)
    return (
        value_type.__name__ == "PreprocessedImage"
        and value_type.__module__ == "app.ai.preprocessing.pipeline"
    )


def _extract_binary_image(
    source: "PreprocessedImage | np.ndarray",
) -> np.ndarray:
    if isinstance(source, np.ndarray):
        image = source
    elif _is_g3_result(source):
        try:
            image = source.thresholded
            expected_width = source.width
            expected_height = source.height
        except Exception:
            raise _error("INVALID_PROCESSED_IMAGE_RESULT") from None
        if (
            not isinstance(expected_width, int)
            or isinstance(expected_width, bool)
            or not isinstance(expected_height, int)
            or isinstance(expected_height, bool)
            or not isinstance(image, np.ndarray)
            or image.ndim != 2
            or image.shape != (expected_height, expected_width)
        ):
            raise _error("INVALID_PROCESSED_IMAGE_RESULT")
    else:
        raise _error("INVALID_PROCESSED_IMAGE_RESULT")

    if image.dtype != np.uint8 or image.ndim != 2:
        raise _error("INVALID_DTYPE_OR_SHAPE")
    height, width = image.shape
    if width <= 0 or height <= 0:
        raise _error("INVALID_DTYPE_OR_SHAPE")
    if max(width, height) > MAXIMUM_IMAGE_EDGE:
        raise _error("UNSAFE_DIMENSIONS")
    if not np.isin(image, (0, 255)).all():
        raise _error("NONBINARY_IMAGE")
    return image


def _empty_result(width: int, height: int) -> WallDetectionResult:
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm=ALGORITHM,
        truncated=False,
        candidates=(),
    )


def _canonical_segment(
    coordinates: object,
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    try:
        values = tuple(coordinates)
    except (TypeError, ValueError):
        raise _error("MALFORMED_OPENCV_RESULT") from None
    if len(values) != 4:
        raise _error("MALFORMED_OPENCV_RESULT")
    if any(
        not isinstance(value, (int, np.integer)) or isinstance(value, (bool, np.bool_))
        for value in values
    ):
        raise _error("MALFORMED_OPENCV_RESULT")
    x1, y1, x2, y2 = (int(value) for value in values)
    if not (
        0 <= x1 < width
        and 0 <= x2 < width
        and 0 <= y1 < height
        and 0 <= y2 < height
    ):
        raise _error("INVALID_COORDINATES")
    if (y2, x2) < (y1, x1):
        x1, y1, x2, y2 = x2, y2, x1, y1
    return x1, y1, x2, y2


def _canonical_segments(
    hough_lines: object,
    *,
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    if hough_lines is None:
        return []
    if not isinstance(hough_lines, np.ndarray):
        raise _error("MALFORMED_OPENCV_RESULT")
    if hough_lines.size == 0:
        return []
    if hough_lines.ndim == 3 and hough_lines.shape[1:] == (1, 4):
        rows = hough_lines[:, 0, :]
    elif hough_lines.ndim == 2 and hough_lines.shape[1] == 4:
        rows = hough_lines
    else:
        raise _error("MALFORMED_OPENCV_RESULT")
    unique = {
        _canonical_segment(row, width=width, height=height)
        for row in rows
    }
    return sorted(unique, key=lambda value: (value[1], value[0], value[3], value[2]))


def _candidate(
    candidate_id: int,
    segment: tuple[int, int, int, int],
) -> WallLineCandidate:
    x1, y1, x2, y2 = segment
    delta_x = x2 - x1
    delta_y = y2 - y1
    angle = math.degrees(math.atan2(delta_y, delta_x)) % 180.0
    if math.isclose(angle, 0.0, abs_tol=0.5e-6) or math.isclose(
        angle,
        180.0,
        abs_tol=0.5e-6,
    ):
        angle = 0.0
    return WallLineCandidate(
        candidate_id=candidate_id,
        start=PixelPoint(x=x1, y=y1),
        end=PixelPoint(x=x2, y=y2),
        length_pixels=round(math.hypot(delta_x, delta_y), 6),
        angle_degrees=round(angle, 6),
    )


def detect_wall_lines(
    source: "PreprocessedImage | np.ndarray",
    *,
    parameters: WallDetectionParameters | None = None,
) -> WallDetectionResult:
    """Return deterministic candidate segments in raw top-left pixel space."""
    try:
        selected = (
            WallDetectionParameters()
            if parameters is None
            else parameters
        )
    except WallDetectionConfigurationError:
        raise _error("INVALID_CONFIGURATION") from None
    if not isinstance(selected, WallDetectionParameters):
        raise _error("INVALID_CONFIGURATION")
    image = _extract_binary_image(source)
    height, width = image.shape
    if np.all(image == image.flat[0]):
        return _empty_result(width, height)

    try:
        edges = cv2.Canny(
            image.copy(),
            selected.canny_low_threshold,
            selected.canny_high_threshold,
            apertureSize=selected.canny_aperture_size,
        )
    except Exception:
        raise _error("EDGE_DETECTION_FAILED") from None
    if (
        not isinstance(edges, np.ndarray)
        or edges.dtype != np.uint8
        or edges.shape != image.shape
    ):
        raise _error("EDGE_DETECTION_FAILED")
    try:
        lines = cv2.HoughLinesP(
            edges,
            selected.hough_rho,
            math.radians(selected.hough_theta_degrees),
            selected.hough_vote_threshold,
            minLineLength=selected.minimum_line_length,
            maxLineGap=selected.maximum_line_gap,
        )
    except Exception:
        raise _error("HOUGH_DETECTION_FAILED") from None

    segments = _canonical_segments(lines, width=width, height=height)
    truncated = len(segments) > selected.maximum_candidates
    limited = segments[: selected.maximum_candidates]
    candidates = tuple(
        _candidate(candidate_id, segment)
        for candidate_id, segment in enumerate(limited, start=1)
    )
    return WallDetectionResult(
        coordinate_space=CoordinateSpace(width=width, height=height),
        algorithm=ALGORITHM,
        truncated=truncated,
        candidates=candidates,
    )
