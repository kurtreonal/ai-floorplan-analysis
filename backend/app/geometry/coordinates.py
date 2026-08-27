from __future__ import annotations

import math
from dataclasses import dataclass


ERROR_MESSAGES = {
    "INVALID_SCALE": "The wall-coordinate scale is invalid.",
    "INVALID_DETECTION_RESULT": "The wall-detection result is invalid.",
    "UNSUPPORTED_COORDINATE_SYSTEM": "The source coordinate system is unsupported.",
    "INVALID_IMAGE_DIMENSIONS": "The source image dimensions are invalid.",
    "INVALID_CANDIDATE_ID": "A wall candidate identifier is invalid.",
    "OUT_OF_BOUNDS_ENDPOINT": "A wall candidate endpoint is outside the source image.",
    "INVALID_LENGTH_OR_ANGLE": "A wall candidate length or angle is invalid.",
    "NONFINITE_CONVERSION_RESULT": "The metric wall conversion is not finite.",
}


class WallCoordinateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


def coordinate_error(code: str) -> WallCoordinateError:
    return WallCoordinateError(code)


def validate_pixels_per_meter(value: object) -> float:
    if type(value) not in (int, float):
        raise coordinate_error("INVALID_SCALE")
    try:
        scale = float(value)
    except (OverflowError, TypeError, ValueError):
        raise coordinate_error("INVALID_SCALE") from None
    if not math.isfinite(scale) or scale <= 0:
        raise coordinate_error("INVALID_SCALE")
    return scale


def rounded_metric(value: float) -> float:
    rounded = round(value, 9)
    return 0.0 if rounded == 0 else rounded


@dataclass(frozen=True)
class CanonicalPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x": rounded_metric(self.x),
            "y": rounded_metric(self.y),
        }


@dataclass(frozen=True)
class CanonicalCoordinateSystem:
    pixels_per_meter: float
    image_width_pixels: int
    image_height_pixels: int
    width_meters: float
    height_meters: float
    unit: str = "meter"
    origin: str = "image_top_left"
    x_direction: str = "right"
    y_direction: str = "down"

    def to_dict(self) -> dict[str, object]:
        return {
            "unit": self.unit,
            "origin": self.origin,
            "x_direction": self.x_direction,
            "y_direction": self.y_direction,
            "pixels_per_meter": self.pixels_per_meter,
            "image_width_pixels": self.image_width_pixels,
            "image_height_pixels": self.image_height_pixels,
            "width_meters": rounded_metric(self.width_meters),
            "height_meters": rounded_metric(self.height_meters),
        }
