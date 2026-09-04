from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.models import ProcessingArtifact, ProcessingJob
from app.models.processing_artifact import ARTIFACT_KINDS
from app.repositories.processing_artifact_repository import (
    add_processing_artifact,
    find_artifact_by_relative_path,
    find_artifact_for_job,
    find_source_page,
)


MAXIMUM_ARTIFACT_BYTES = 256 * 1024 * 1024
SUPPORTED_ARTIFACT_MIME_TYPES = frozenset({"image/png"})


class ProcessingArtifactError(RuntimeError):
    """Raised when derived artifact provenance cannot be trusted."""


@dataclass(frozen=True)
class TrustedArtifact:
    record: ProcessingArtifact
    absolute_path: Path
    content: bytes


def _validated_file(
    processed_directory: Path,
    *,
    relative_path: str,
    mime_type: str,
) -> tuple[Path, bytes, int, int]:
    portable = PurePosixPath(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or portable.is_absolute()
        or PureWindowsPath(relative_path).is_absolute()
        or any(part in {"", ".", ".."} for part in portable.parts)
        or mime_type not in SUPPORTED_ARTIFACT_MIME_TYPES
        or portable.suffix.casefold() != ".png"
    ):
        raise ProcessingArtifactError("Artifact metadata is unsafe.")
    try:
        root = Path(processed_directory).resolve(strict=True)
        lexical = root.joinpath(*portable.parts)
        resolved = lexical.resolve(strict=True)
        if (
            not root.is_dir()
            or resolved != lexical
            or not resolved.is_relative_to(root)
            or not resolved.is_file()
        ):
            raise ProcessingArtifactError("Artifact path is unsafe.")
        size = resolved.stat().st_size
        if size <= 0 or size > MAXIMUM_ARTIFACT_BYTES:
            raise ProcessingArtifactError("Artifact size is invalid.")
        content = resolved.read_bytes()
        if len(content) != size:
            raise ProcessingArtifactError("Artifact size changed while reading.")
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG":
                raise ProcessingArtifactError("Artifact content does not match its MIME type.")
            width, height = image.size
            image.verify()
        if width <= 0 or height <= 0:
            raise ProcessingArtifactError("Artifact dimensions are invalid.")
    except ProcessingArtifactError:
        raise
    except FileNotFoundError:
        raise ProcessingArtifactError("Artifact file was not found.") from None
    except (OSError, RuntimeError, ValueError, SyntaxError, UnidentifiedImageError):
        raise ProcessingArtifactError("Artifact file is unavailable or invalid.") from None
    return resolved, content, width, height


def register_processing_artifact(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    floor_plan_id: int,
    page_number: int,
    artifact_kind: str,
    processed_directory: Path,
    relative_path: str,
    mime_type: str,
) -> ProcessingArtifact:
    if (
        artifact_kind not in ARTIFACT_KINDS
        or processing_job.id is None
        or processing_job.floor_plan_id != floor_plan_id
        or page_number <= 0
    ):
        raise ProcessingArtifactError("Artifact provenance is invalid.")
    page = find_source_page(
        database_session, floor_plan_id=floor_plan_id, page_number=page_number
    )
    if page is None:
        raise ProcessingArtifactError("Artifact source page was not found.")
    _, content, width, height = _validated_file(
        processed_directory, relative_path=relative_path, mime_type=mime_type
    )
    digest = sha256(content).hexdigest()
    existing = find_artifact_by_relative_path(
        database_session, relative_path=relative_path
    )
    values = (
        processing_job.id,
        page.id,
        artifact_kind,
        mime_type,
        len(content),
        digest,
        width,
        height,
    )
    if existing is not None:
        current = (
            existing.processing_job_id,
            existing.floor_plan_page_id,
            existing.artifact_kind,
            existing.mime_type,
            existing.byte_size,
            existing.sha256,
            existing.pixel_width,
            existing.pixel_height,
        )
        if current == values:
            return existing
        raise ProcessingArtifactError("Artifact path conflicts with existing provenance.")
    return add_processing_artifact(
        database_session,
        ProcessingArtifact(
            processing_job_id=processing_job.id,
            floor_plan_page_id=page.id,
            artifact_kind=artifact_kind,
            relative_path=relative_path,
            mime_type=mime_type,
            byte_size=len(content),
            sha256=digest,
            pixel_width=width,
            pixel_height=height,
        ),
    )


def resolve_trusted_processing_artifact(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    artifact_kind: str,
    processed_directory: Path,
) -> TrustedArtifact:
    artifact = find_artifact_for_job(
        database_session,
        floor_plan_id=floor_plan_id,
        processing_job_id=processing_job_id,
        artifact_kind=artifact_kind,
    )
    if artifact is None:
        raise ProcessingArtifactError("Registered artifact was not found.")
    path, content, width, height = _validated_file(
        processed_directory,
        relative_path=artifact.relative_path,
        mime_type=artifact.mime_type,
    )
    if (
        len(content) != artifact.byte_size
        or sha256(content).hexdigest() != artifact.sha256
        or width != artifact.pixel_width
        or height != artifact.pixel_height
    ):
        raise ProcessingArtifactError("Registered artifact integrity validation failed.")
    return TrustedArtifact(record=artifact, absolute_path=path, content=content)
