import hashlib
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FloorPlanPage, FloorPlanSource, ProcessingArtifact, ProcessingJob
from app.services.processing_artifact_service import register_processing_artifact


def attach_source_identity(
    session: Session, floor_plan, content: bytes, *, page_count: int = 1
) -> FloorPlanSource:
    source = FloorPlanSource(
        floor_plan=floor_plan,
        original_sha256=hashlib.sha256(content).hexdigest(),
        pages=[FloorPlanPage(page_number=number) for number in range(1, page_count + 1)],
    )
    session.add(source)
    session.flush()
    return source


def register_normalized_fixture(
    session: Session,
    *,
    floor_plan,
    processing_job,
    processed_root: Path,
    image_path: Path,
) -> ProcessingArtifact:
    return register_processing_artifact(
        session,
        processing_job=processing_job,
        floor_plan_id=floor_plan.id,
        page_number=1,
        artifact_kind="normalized_image",
        processed_directory=processed_root,
        relative_path=image_path.relative_to(processed_root).as_posix(),
        mime_type="image/png",
    )


def delete_artifact_identity_fixtures(
    session: Session, *, floor_plan_ids: tuple[int, ...]
) -> None:
    delete_processing_artifacts(session, floor_plan_ids=floor_plan_ids)
    source_ids = tuple(
        session.scalars(
            select(FloorPlanSource.id).where(FloorPlanSource.floor_plan_id.in_(floor_plan_ids))
        )
    )
    if source_ids:
        session.execute(
            delete(FloorPlanPage).where(FloorPlanPage.floor_plan_source_id.in_(source_ids))
        )
        session.execute(delete(FloorPlanSource).where(FloorPlanSource.id.in_(source_ids)))


def delete_processing_artifacts(
    session: Session, *, floor_plan_ids: tuple[int, ...]
) -> None:
    job_ids = tuple(
        session.scalars(
            select(ProcessingJob.id).where(ProcessingJob.floor_plan_id.in_(floor_plan_ids))
        )
    )
    if job_ids:
        session.execute(
            delete(ProcessingArtifact).where(ProcessingArtifact.processing_job_id.in_(job_ids))
        )
