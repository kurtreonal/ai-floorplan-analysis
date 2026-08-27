from __future__ import annotations

import math
from dataclasses import dataclass, fields


INVALID_CONFIGURATION_MESSAGE = "The wall-detection configuration is invalid."


class WallDetectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class WallDetectionConfigurationError(WallDetectionError):
    code = "INVALID_CONFIGURATION"
    message = INVALID_CONFIGURATION_MESSAGE

    def __init__(self) -> None:
        super().__init__(self.code, self.message)


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


@dataclass(frozen=True, init=False)
class WallDetectionParameters:
    canny_low_threshold: int = 50
    canny_high_threshold: int = 200
    canny_aperture_size: int = 3
    hough_rho: float = 1.0
    hough_theta_degrees: float = 1.0
    hough_vote_threshold: int = 50
    minimum_line_length: float = 50
    maximum_line_gap: float = 10
    maximum_candidates: int = 2000

    def __init__(
        self,
        canny_low_threshold: int = 50,
        canny_high_threshold: int = 200,
        canny_aperture_size: int = 3,
        hough_rho: float = 1.0,
        hough_theta_degrees: float = 1.0,
        hough_vote_threshold: int = 50,
        minimum_line_length: float = 50,
        maximum_line_gap: float = 10,
        maximum_candidates: int = 2000,
        **unknown: object,
    ) -> None:
        if unknown:
            raise WallDetectionConfigurationError()
        values = {
            "canny_low_threshold": canny_low_threshold,
            "canny_high_threshold": canny_high_threshold,
            "canny_aperture_size": canny_aperture_size,
            "hough_rho": hough_rho,
            "hough_theta_degrees": hough_theta_degrees,
            "hough_vote_threshold": hough_vote_threshold,
            "minimum_line_length": minimum_line_length,
            "maximum_line_gap": maximum_line_gap,
            "maximum_candidates": maximum_candidates,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        self._validate()

    @classmethod
    def from_mapping(cls, values: dict[str, object]) -> "WallDetectionParameters":
        if not isinstance(values, dict):
            raise WallDetectionConfigurationError()
        known = {field.name for field in fields(cls)}
        if not set(values).issubset(known):
            raise WallDetectionConfigurationError()
        return cls(**values)

    def _validate(self) -> None:
        if (
            not _is_integer(self.canny_low_threshold)
            or not _is_integer(self.canny_high_threshold)
            or not 0 <= self.canny_low_threshold <= 255
            or not 0 <= self.canny_high_threshold <= 255
            or self.canny_low_threshold >= self.canny_high_threshold
            or not _is_integer(self.canny_aperture_size)
            or self.canny_aperture_size not in {3, 5, 7}
        ):
            raise WallDetectionConfigurationError()
        if (
            not _is_finite_number(self.hough_rho)
            or self.hough_rho <= 0
            or not _is_finite_number(self.hough_theta_degrees)
            or not 0 < self.hough_theta_degrees <= 180
        ):
            raise WallDetectionConfigurationError()
        if (
            not _is_integer(self.hough_vote_threshold)
            or self.hough_vote_threshold <= 0
            or not _is_integer(self.maximum_candidates)
            or self.maximum_candidates <= 0
        ):
            raise WallDetectionConfigurationError()
        if (
            not _is_finite_number(self.minimum_line_length)
            or self.minimum_line_length < 0
            or not _is_finite_number(self.maximum_line_gap)
            or self.maximum_line_gap < 0
        ):
            raise WallDetectionConfigurationError()
