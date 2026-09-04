from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from app.models import FloorPlan, FloorPlanSource
from app.repositories.floor_plan_source_repository import add_floor_plan_source
from app.services.upload_validation import ValidatedFloorPlan, validate_floor_plan_upload


class SourceIdentityError(RuntimeError):
    """Raised when existing original bytes cannot prove source identity safely."""


@dataclass(frozen=True)
class VerifiedSourceIdentity:
    original_sha256: str
    page_count: int


def verified_source_identity(
    *,
    content: bytes,
    validated: ValidatedFloorPlan,
) -> VerifiedSourceIdentity:
    page_count = validated.page_count if validated.page_count is not None else 1
    if page_count <= 0:
        raise SourceIdentityError("The validated source has no pages.")
    return VerifiedSourceIdentity(
        original_sha256=sha256(content).hexdigest(),
        page_count=page_count,
    )


def persist_source_identity(
    database_session: Session,
    *,
    floor_plan: FloorPlan,
    identity: VerifiedSourceIdentity,
) -> FloorPlanSource:
    return add_floor_plan_source(
        database_session,
        floor_plan=floor_plan,
        original_sha256=identity.original_sha256,
        page_count=identity.page_count,
    )


def resolve_stored_original(upload_directory: Path, storage_path: str) -> Path:
    reference = PurePosixPath(storage_path)
    if (
        reference.is_absolute()
        or len(reference.parts) != 2
        or reference.parts[0] != "originals"
        or reference.parts[1] in {"", ".", ".."}
    ):
        raise SourceIdentityError("A floor-plan storage reference is unsafe.")
    root = upload_directory.resolve(strict=True)
    candidate = (root / Path(*reference.parts)).resolve(strict=True)
    if candidate.parent != root / "originals" or not candidate.is_file():
        raise SourceIdentityError("An original floor-plan file is unavailable.")
    return candidate


def verify_existing_floor_plan_source(
    *,
    floor_plan: FloorPlan,
    upload_directory: Path,
    max_file_size_bytes: int,
) -> VerifiedSourceIdentity:
    original = resolve_stored_original(upload_directory, floor_plan.storage_path)
    content = original.read_bytes()
    if len(content) != floor_plan.file_size:
        raise SourceIdentityError("Stored original size does not match its database record.")
    try:
        validated = validate_floor_plan_upload(
            filename=floor_plan.original_filename,
            declared_mime_type=floor_plan.mime_type,
            content=content,
            max_file_size_bytes=max_file_size_bytes,
        )
    except Exception as error:
        raise SourceIdentityError("Stored original validation failed.") from error
    return verified_source_identity(content=content, validated=validated)
