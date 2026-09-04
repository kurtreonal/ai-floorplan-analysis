from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import FloorPlan
from app.repositories.floor_plan_repository import add_floor_plan
from app.services.upload_validation import validate_floor_plan_upload
from app.services.source_identity import persist_source_identity, verified_source_identity


ORIGINALS_DIRECTORY_NAME = "originals"
MAX_STORAGE_NAME_ATTEMPTS = 5

ERROR_MESSAGES = {
    "UPLOAD_DIRECTORY_UNAVAILABLE": "The upload directory is unavailable.",
    "ORIGINAL_FILENAME_INVALID": "The original floor-plan filename is invalid.",
    "ORIGINAL_FILENAME_TOO_LONG": "The original floor-plan filename is too long.",
    "STORAGE_PATH_INVALID": "The floor-plan storage path is invalid.",
    "STORAGE_NAME_ALLOCATION_FAILED": (
        "A unique floor-plan storage name could not be allocated."
    ),
    "ORIGINAL_FILE_WRITE_FAILED": "The original floor-plan file could not be stored.",
    "FLOOR_PLAN_RECORD_FAILED": "The floor-plan record could not be saved.",
    "STORED_FILE_CLEANUP_FAILED": (
        "A failed floor-plan operation could not be cleaned up safely."
    ),
}


@dataclass(frozen=True)
class StoredOriginalFloorPlan:
    absolute_path: Path
    storage_reference: str
    stored_filename: str
    file_size: int


class FloorPlanStorageError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


def _storage_error(
    code: str,
    *,
    details: dict[str, object] | None = None,
) -> FloorPlanStorageError:
    return FloorPlanStorageError(code, ERROR_MESSAGES[code], details)


def _safe_original_basename(filename: str) -> str:
    if "\x00" in filename:
        raise _storage_error("ORIGINAL_FILENAME_INVALID")

    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or basename in {".", ".."}:
        raise _storage_error("ORIGINAL_FILENAME_INVALID")
    if len(basename) > 255:
        raise _storage_error("ORIGINAL_FILENAME_TOO_LONG")
    return basename


def _prepare_originals_directory(upload_directory: Path) -> Path:
    try:
        upload_root = Path(upload_directory).resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _storage_error("STORAGE_PATH_INVALID") from None

    originals_candidate = upload_root / ORIGINALS_DIRECTORY_NAME
    try:
        upload_root.mkdir(parents=True, exist_ok=True)
        originals_candidate.mkdir(exist_ok=True)
        originals_directory = originals_candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _storage_error("UPLOAD_DIRECTORY_UNAVAILABLE") from None

    if (
        not originals_directory.is_dir()
        or originals_directory.parent != upload_root
    ):
        raise _storage_error("STORAGE_PATH_INVALID")
    return originals_directory


def _remove_stored_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        raise _storage_error("STORED_FILE_CLEANUP_FAILED") from None


def _write_original(
    originals_directory: Path,
    *,
    extension: str,
    content: bytes,
) -> StoredOriginalFloorPlan:
    for _ in range(MAX_STORAGE_NAME_ATTEMPTS):
        stored_filename = f"{uuid4().hex}{extension}"
        destination = originals_directory / stored_filename

        if destination.parent != originals_directory:
            raise _storage_error("STORAGE_PATH_INVALID")

        try:
            destination_file = destination.open("xb")
        except FileExistsError:
            continue
        except OSError:
            _remove_stored_file(destination)
            raise _storage_error("ORIGINAL_FILE_WRITE_FAILED") from None

        try:
            with destination_file:
                bytes_written = destination_file.write(content)
                if bytes_written != len(content):
                    raise OSError("incomplete write")
        except Exception:
            _remove_stored_file(destination)
            raise _storage_error("ORIGINAL_FILE_WRITE_FAILED") from None

        return StoredOriginalFloorPlan(
            absolute_path=destination,
            storage_reference=PurePosixPath(
                ORIGINALS_DIRECTORY_NAME,
                stored_filename,
            ).as_posix(),
            stored_filename=stored_filename,
            file_size=len(content),
        )

    raise _storage_error("STORAGE_NAME_ALLOCATION_FAILED")


def store_floor_plan_upload(
    database_session: Session,
    *,
    project_floor_id: int,
    filename: str,
    declared_mime_type: str,
    content: bytes,
    upload_directory: Path,
    max_file_size_bytes: int,
) -> FloorPlan:
    """Store an original and own its database commit/rollback boundary."""
    validated = validate_floor_plan_upload(
        filename=filename,
        declared_mime_type=declared_mime_type,
        content=content,
        max_file_size_bytes=max_file_size_bytes,
    )
    safe_original_filename = _safe_original_basename(filename)
    originals_directory = _prepare_originals_directory(upload_directory)
    stored = _write_original(
        originals_directory,
        extension=validated.extension,
        content=content,
    )

    floor_plan = FloorPlan(
        project_floor_id=project_floor_id,
        original_filename=safe_original_filename,
        storage_path=stored.storage_reference,
        mime_type=validated.mime_type,
        file_size=validated.file_size,
        processing_status="uploaded",
    )
    identity = verified_source_identity(content=content, validated=validated)

    try:
        persisted_floor_plan = add_floor_plan(database_session, floor_plan)
        persist_source_identity(
            database_session,
            floor_plan=persisted_floor_plan,
            identity=identity,
        )
        database_session.commit()
    except Exception:
        try:
            database_session.rollback()
        except Exception:
            pass
        _remove_stored_file(stored.absolute_path)
        raise _storage_error("FLOOR_PLAN_RECORD_FAILED") from None

    return persisted_floor_plan
