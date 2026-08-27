from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.geometry.coordinates import (
    CanonicalCoordinateSystem,
    CanonicalPoint,
    WallCoordinateError,
    coordinate_error,
    rounded_metric,
    validate_pixels_per_meter,
)

if TYPE_CHECKING:
    from app.ai.wall_detection.detector import WallDetectionResult


_MISSING_SCALE = object()
H1_MODULE = "app.ai.wall_detection.detector"
MAXIMUM_IMAGE_EDGE = 4096


@dataclass(frozen=True)
class RawPixelPoint:
    x: int
    y: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class RawPixelWall:
    start: RawPixelPoint
    end: RawPixelPoint
    length_pixels: int | float
    angle_degrees: int | float

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "length_pixels": self.length_pixels,
            "angle_degrees": self.angle_degrees,
        }


@dataclass(frozen=True)
class CanonicalWall:
    start: CanonicalPoint
    end: CanonicalPoint
    length_meters: float
    angle_degrees: int | float

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "length_meters": rounded_metric(self.length_meters),
            "angle_degrees": self.angle_degrees,
        }


@dataclass(frozen=True)
class CanonicalWallCandidate:
    candidate_id: int
    raw_pixels: RawPixelWall
    canonical: CanonicalWall

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "raw_pixels": self.raw_pixels.to_dict(),
            "canonical": self.canonical.to_dict(),
        }


@dataclass(frozen=True)
class NormalizedWallGeometry:
    coordinate_system: CanonicalCoordinateSystem
    source_truncated: bool
    walls: tuple[CanonicalWallCandidate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "coordinate_system": self.coordinate_system.to_dict(),
            "source_truncated": self.source_truncated,
            "walls": [wall.to_dict() for wall in self.walls],
        }


def _is_exact_h1_type(value: object, class_name: str) -> bool:
    value_type = type(value)
    return value_type.__module__ == H1_MODULE and value_type.__name__ == class_name


def _validate_coordinate_space(coordinate_space: object) -> tuple[int, int]:
    if not _is_exact_h1_type(coordinate_space, "CoordinateSpace"):
        raise coordinate_error("INVALID_DETECTION_RESULT")
    try:
        unit = coordinate_space.unit
        origin = coordinate_space.origin
        x_direction = coordinate_space.x_direction
        y_direction = coordinate_space.y_direction
        width = coordinate_space.width
        height = coordinate_space.height
    except Exception:
        raise coordinate_error("INVALID_DETECTION_RESULT") from None
    if (
        unit != "pixel"
        or origin != "top_left"
        or x_direction != "right"
        or y_direction != "down"
    ):
        raise coordinate_error("UNSUPPORTED_COORDINATE_SYSTEM")
    if (
        type(width) is not int
        or type(height) is not int
        or width <= 0
        or height <= 0
        or max(width, height) > MAXIMUM_IMAGE_EDGE
    ):
        raise coordinate_error("INVALID_IMAGE_DIMENSIONS")
    return width, height


def _validate_point(point: object, *, width: int, height: int) -> tuple[int, int]:
    if not _is_exact_h1_type(point, "PixelPoint"):
        raise coordinate_error("INVALID_DETECTION_RESULT")
    try:
        x = point.x
        y = point.y
    except Exception:
        raise coordinate_error("INVALID_DETECTION_RESULT") from None
    if type(x) is not int or type(y) is not int:
        raise coordinate_error("OUT_OF_BOUNDS_ENDPOINT")
    if not 0 <= x < width or not 0 <= y < height:
        raise coordinate_error("OUT_OF_BOUNDS_ENDPOINT")
    return x, y


def _validate_measurement(value: object, *, angle: bool) -> int | float:
    if type(value) not in (int, float):
        raise coordinate_error("INVALID_LENGTH_OR_ANGLE")
    try:
        measurement = float(value)
    except (OverflowError, TypeError, ValueError):
        raise coordinate_error("INVALID_LENGTH_OR_ANGLE") from None
    if not math.isfinite(measurement):
        raise coordinate_error("INVALID_LENGTH_OR_ANGLE")
    if (angle and not 0 <= measurement < 180) or (
        not angle and measurement < 0
    ):
        raise coordinate_error("INVALID_LENGTH_OR_ANGLE")
    return value


def _validate_candidates(
    candidates: object,
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, int, int, int, int, float, float], ...]:
    if not isinstance(candidates, tuple):
        raise coordinate_error("INVALID_DETECTION_RESULT")
    validated = []
    previous_sort_key = None
    seen_segments = set()
    for expected_id, candidate in enumerate(candidates, start=1):
        if not _is_exact_h1_type(candidate, "WallLineCandidate"):
            raise coordinate_error("INVALID_DETECTION_RESULT")
        try:
            candidate_id = candidate.candidate_id
            start = candidate.start
            end = candidate.end
            length_pixels = candidate.length_pixels
            angle_degrees = candidate.angle_degrees
        except Exception:
            raise coordinate_error("INVALID_DETECTION_RESULT") from None
        if type(candidate_id) is not int or candidate_id != expected_id:
            raise coordinate_error("INVALID_CANDIDATE_ID")
        start_x, start_y = _validate_point(start, width=width, height=height)
        end_x, end_y = _validate_point(end, width=width, height=height)
        if (end_y, end_x) < (start_y, start_x):
            raise coordinate_error("INVALID_DETECTION_RESULT")
        length = _validate_measurement(length_pixels, angle=False)
        angle = _validate_measurement(angle_degrees, angle=True)
        sort_key = (start_y, start_x, end_y, end_x)
        segment = (start_x, start_y, end_x, end_y)
        if (
            (previous_sort_key is not None and sort_key < previous_sort_key)
            or segment in seen_segments
        ):
            raise coordinate_error("INVALID_DETECTION_RESULT")
        previous_sort_key = sort_key
        seen_segments.add(segment)
        validated.append(
            (
                candidate_id,
                start_x,
                start_y,
                end_x,
                end_y,
                length,
                angle,
            )
        )
    return tuple(validated)


def _validated_detection_result(
    detection_result: object,
) -> tuple[int, int, bool, tuple[tuple[int, int, int, int, int, float, float], ...]]:
    if not _is_exact_h1_type(detection_result, "WallDetectionResult"):
        raise coordinate_error("INVALID_DETECTION_RESULT")
    try:
        coordinate_space = detection_result.coordinate_space
        algorithm = detection_result.algorithm
        truncated = detection_result.truncated
        candidates = detection_result.candidates
    except Exception:
        raise coordinate_error("INVALID_DETECTION_RESULT") from None
    if algorithm != "probabilistic_hough" or type(truncated) is not bool:
        raise coordinate_error("INVALID_DETECTION_RESULT")
    width, height = _validate_coordinate_space(coordinate_space)
    validated_candidates = _validate_candidates(
        candidates,
        width=width,
        height=height,
    )
    return width, height, truncated, validated_candidates


def _metric_value(pixel_value: int, scale: float) -> float:
    value = pixel_value / scale
    if not math.isfinite(value):
        raise coordinate_error("NONFINITE_CONVERSION_RESULT")
    return value


def normalize_wall_coordinates(
    detection_result: "WallDetectionResult",
    pixels_per_meter: object = _MISSING_SCALE,
) -> NormalizedWallGeometry:
    """Convert validated H1 candidates into shared metric image-plane geometry."""
    scale = validate_pixels_per_meter(pixels_per_meter)
    width, height, truncated, candidates = _validated_detection_result(
        detection_result
    )
    width_meters = _metric_value(width, scale)
    height_meters = _metric_value(height, scale)
    walls = []
    for (
        candidate_id,
        start_x,
        start_y,
        end_x,
        end_y,
        raw_length,
        angle,
    ) in candidates:
        canonical_start = CanonicalPoint(
            x=_metric_value(start_x, scale),
            y=_metric_value(start_y, scale),
        )
        canonical_end = CanonicalPoint(
            x=_metric_value(end_x, scale),
            y=_metric_value(end_y, scale),
        )
        metric_length = math.hypot(
            canonical_end.x - canonical_start.x,
            canonical_end.y - canonical_start.y,
        )
        if not math.isfinite(metric_length):
            raise coordinate_error("NONFINITE_CONVERSION_RESULT")
        walls.append(
            CanonicalWallCandidate(
                candidate_id=candidate_id,
                raw_pixels=RawPixelWall(
                    start=RawPixelPoint(x=start_x, y=start_y),
                    end=RawPixelPoint(x=end_x, y=end_y),
                    length_pixels=raw_length,
                    angle_degrees=angle,
                ),
                canonical=CanonicalWall(
                    start=canonical_start,
                    end=canonical_end,
                    length_meters=metric_length,
                    angle_degrees=angle,
                ),
            )
        )
    return NormalizedWallGeometry(
        coordinate_system=CanonicalCoordinateSystem(
            pixels_per_meter=scale,
            image_width_pixels=width,
            image_height_pixels=height,
            width_meters=width_meters,
            height_meters=height_meters,
        ),
        source_truncated=truncated,
        walls=tuple(walls),
    )
