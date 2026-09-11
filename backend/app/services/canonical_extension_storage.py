from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from app.core.config import get_settings
from app.geometry.canonical_extension import (
    CanonicalExtensionV2,
    canonical_extension_from_dict,
)
from app.geometry.canonical import CanonicalGeometryDocument


def get_canonical_extension_directory() -> Path:
    settings = get_settings()
    if settings.processed_dir:
        base_dir = settings.processed_dir.parent / "canonical_extensions"
    else:
        base_dir = Path("storage") / "canonical_extensions"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _extension_file_path(layout_version_id: int) -> Path:
    return get_canonical_extension_directory() / f"layout_{layout_version_id}_extension_v2.json"


def save_canonical_extension(
    layout_version_id: int,
    extension: CanonicalExtensionV2,
) -> tuple[Path, str]:
    target_path = _extension_file_path(layout_version_id)
    serialized = json.dumps(
        extension.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    content_hash = sha256(serialized).hexdigest()
    target_path.write_bytes(serialized)
    return target_path, content_hash


def retrieve_canonical_extension(
    layout_version_id: int,
    base_document: CanonicalGeometryDocument | None = None,
) -> CanonicalExtensionV2 | None:
    target_path = _extension_file_path(layout_version_id)
    if not target_path.is_file():
        return None
    try:
        raw = json.loads(target_path.read_text(encoding="utf-8"))
        return canonical_extension_from_dict(raw, base_document)
    except Exception:
        return None


def delete_canonical_extension(layout_version_id: int) -> bool:
    target_path = _extension_file_path(layout_version_id)
    if target_path.is_file():
        try:
            target_path.unlink()
            return True
        except OSError:
            return False
    return False
