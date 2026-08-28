from __future__ import annotations

import os
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock

from app.core.config import REPOSITORY_ROOT, Settings, get_settings


SAFE_ERROR_MESSAGE = "The configured symbol-detection model could not be loaded."
ERROR_CODES = frozenset(
    {
        "model_path_not_configured",
        "model_path_invalid",
        "model_file_missing",
        "model_file_unsupported",
        "model_load_failed",
        "model_metadata_invalid",
        "model_task_unsupported",
    }
)
SUPPORTED_MODEL_TASK = "detect"
MAXIMUM_CACHED_MODELS = 4
URL_LIKE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")

ModelFactory = Callable[[str], object]


class YOLOModelLoaderError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in ERROR_CODES:
            raise ValueError("Unknown YOLO model-loader error code.")
        self.code = code
        self.message = SAFE_ERROR_MESSAGE
        super().__init__(self.message)


@dataclass(frozen=True)
class SymbolClassMetadata:
    class_id: int
    name: str


@dataclass(frozen=True)
class LoadedSymbolDetectionModel:
    model: object = field(repr=False, compare=False)
    classes: tuple[SymbolClassMetadata, ...]
    task: str | None
    _resolved_path: Path = field(repr=False)


_model_cache: OrderedDict[Path, LoadedSymbolDetectionModel] = OrderedDict()
_model_cache_lock = RLock()


def _error(code: str) -> YOLOModelLoaderError:
    return YOLOModelLoaderError(code)


def _configured_model_path(settings: Settings) -> Path:
    configured = settings.yolo_model_path
    if configured is None or configured == Path("."):
        raise _error("model_path_not_configured")

    configured_text = str(configured).strip()
    if not configured_text:
        raise _error("model_path_not_configured")
    if URL_LIKE_PATTERN.match(configured_text) and not WINDOWS_DRIVE_PATTERN.match(
        configured_text
    ):
        raise _error("model_path_invalid")
    if "\x00" in configured_text:
        raise _error("model_path_invalid")

    try:
        candidate = Path(configured_text)
        candidate = candidate if candidate.is_absolute() else REPOSITORY_ROOT / candidate
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _error("model_path_invalid") from None

    if resolved.suffix.casefold() != ".pt":
        raise _error("model_file_unsupported")
    try:
        if not resolved.exists():
            raise _error("model_file_missing")
        if not resolved.is_file():
            raise _error("model_path_invalid")
        if not os.access(resolved, os.R_OK):
            raise _error("model_path_invalid")
        with resolved.open("rb") as model_file:
            model_file.read(1)
        return resolved.resolve(strict=True)
    except YOLOModelLoaderError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _error("model_path_invalid") from None


def _default_model_factory(model_path: str) -> object:
    from ultralytics import YOLO

    return YOLO(model_path)


def _normalized_classes(model: object) -> tuple[SymbolClassMetadata, ...]:
    try:
        names = model.names
    except Exception:
        raise _error("model_metadata_invalid") from None

    if isinstance(names, list):
        items = tuple(enumerate(names))
    elif isinstance(names, dict):
        if any(type(class_id) is not int or class_id < 0 for class_id in names):
            raise _error("model_metadata_invalid")
        ordered_ids = tuple(sorted(names))
        if ordered_ids != tuple(range(len(ordered_ids))):
            raise _error("model_metadata_invalid")
        items = tuple((class_id, names[class_id]) for class_id in ordered_ids)
    else:
        raise _error("model_metadata_invalid")

    if not items:
        raise _error("model_metadata_invalid")
    normalized = []
    seen_names = set()
    for class_id, name in items:
        if type(name) is not str or not name.strip():
            raise _error("model_metadata_invalid")
        normalized_name = name.strip()
        if normalized_name in seen_names:
            raise _error("model_metadata_invalid")
        seen_names.add(normalized_name)
        normalized.append(
            SymbolClassMetadata(class_id=class_id, name=normalized_name)
        )
    return tuple(normalized)


def _model_task(model: object) -> str | None:
    try:
        task = getattr(model, "task", None)
    except Exception:
        raise _error("model_task_unsupported") from None
    if task is None:
        return None
    if type(task) is not str or task.casefold() != SUPPORTED_MODEL_TASK:
        raise _error("model_task_unsupported")
    return SUPPORTED_MODEL_TASK


def load_symbol_detection_model(
    *,
    settings: Settings | None = None,
    model_factory: ModelFactory | None = None,
) -> LoadedSymbolDetectionModel:
    """Load one validated local detection model through a bounded process cache."""
    resolved_path = _configured_model_path(settings or get_settings())
    factory = model_factory or _default_model_factory

    with _model_cache_lock:
        cached = _model_cache.get(resolved_path)
        if cached is not None:
            _model_cache.move_to_end(resolved_path)
            return cached
        try:
            model = factory(str(resolved_path))
        except Exception:
            raise _error("model_load_failed") from None

        classes = _normalized_classes(model)
        task = _model_task(model)
        loaded = LoadedSymbolDetectionModel(
            model=model,
            classes=classes,
            task=task,
            _resolved_path=resolved_path,
        )
        _model_cache[resolved_path] = loaded
        _model_cache.move_to_end(resolved_path)
        while len(_model_cache) > MAXIMUM_CACHED_MODELS:
            _model_cache.popitem(last=False)
        return loaded


def reset_symbol_detection_model_cache() -> None:
    """Clear only the process-local model cache; intended for isolated tests."""
    with _model_cache_lock:
        _model_cache.clear()
