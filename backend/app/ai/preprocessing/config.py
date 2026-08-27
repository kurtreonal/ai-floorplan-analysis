from __future__ import annotations

import math
from dataclasses import dataclass, fields


class PreprocessingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PreprocessingConfigurationError(PreprocessingError):
    """Raised without leaking the rejected configuration value."""

    code = "INVALID_CONFIGURATION"
    message = "The preprocessing configuration is invalid."

    def __init__(self) -> None:
        super().__init__(self.code, self.message)


@dataclass(frozen=True, init=False)
class PreprocessingParameters:
    median_kernel_size: int = 3
    gaussian_blur_enabled: bool = True
    gaussian_kernel_size: int = 3
    gaussian_sigma: float = 0.0
    threshold_mode: str = "otsu"
    fixed_threshold: int = 127
    invert_binary: bool = False
    save_debug_outputs: bool = False

    def __init__(
        self,
        median_kernel_size: int = 3,
        gaussian_blur_enabled: bool = True,
        gaussian_kernel_size: int = 3,
        gaussian_sigma: float = 0.0,
        threshold_mode: str = "otsu",
        fixed_threshold: int = 127,
        invert_binary: bool = False,
        save_debug_outputs: bool = False,
        **unknown: object,
    ) -> None:
        if unknown:
            raise PreprocessingConfigurationError()
        values = {
            "median_kernel_size": median_kernel_size,
            "gaussian_blur_enabled": gaussian_blur_enabled,
            "gaussian_kernel_size": gaussian_kernel_size,
            "gaussian_sigma": gaussian_sigma,
            "threshold_mode": threshold_mode,
            "fixed_threshold": fixed_threshold,
            "invert_binary": invert_binary,
            "save_debug_outputs": save_debug_outputs,
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)
        self._validate()

    @classmethod
    def from_mapping(cls, values: dict[str, object]) -> "PreprocessingParameters":
        if not isinstance(values, dict):
            raise PreprocessingConfigurationError()
        known = {field.name for field in fields(cls)}
        if not set(values).issubset(known):
            raise PreprocessingConfigurationError()
        return cls(**values)

    def _validate(self) -> None:
        kernels = (self.median_kernel_size, self.gaussian_kernel_size)
        if any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 3
            or value > 31
            or value % 2 == 0
            for value in kernels
        ):
            raise PreprocessingConfigurationError()
        if any(
            not isinstance(value, bool)
            for value in (
                self.gaussian_blur_enabled,
                self.invert_binary,
                self.save_debug_outputs,
            )
        ):
            raise PreprocessingConfigurationError()
        if (
            not isinstance(self.gaussian_sigma, (int, float))
            or isinstance(self.gaussian_sigma, bool)
            or not math.isfinite(self.gaussian_sigma)
            or self.gaussian_sigma < 0
        ):
            raise PreprocessingConfigurationError()
        if (
            not isinstance(self.threshold_mode, str)
            or self.threshold_mode not in {"otsu", "fixed"}
        ):
            raise PreprocessingConfigurationError()
        if (
            not isinstance(self.fixed_threshold, int)
            or isinstance(self.fixed_threshold, bool)
            or not 0 <= self.fixed_threshold <= 255
        ):
            raise PreprocessingConfigurationError()
