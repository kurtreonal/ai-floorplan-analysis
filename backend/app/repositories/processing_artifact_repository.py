from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FloorPlanPage, FloorPlanSource, ProcessingArtifact, ProcessingJob


def find_source_page(
    database_session: Session, *, floor_plan_id: int, page_number: int
) -> FloorPlanPage | None:
    return database_session.scalar(
        select(FloorPlanPage)
        .join(FloorPlanSource, FloorPlanPage.floor_plan_source_id == FloorPlanSource.id)
        .where(
            FloorPlanSource.floor_plan_id == floor_plan_id,
            FloorPlanPage.page_number == page_number,
        )
    )


def find_artifact_by_relative_path(
    database_session: Session, *, relative_path: str
) -> ProcessingArtifact | None:
    return database_session.scalar(
        select(ProcessingArtifact).where(ProcessingArtifact.relative_path == relative_path)
    )


def find_artifact_for_job(
    database_session: Session,
    *,
    floor_plan_id: int,
    processing_job_id: int,
    artifact_kind: str,
) -> ProcessingArtifact | None:
    return database_session.scalar(
        select(ProcessingArtifact)
        .join(ProcessingJob, ProcessingArtifact.processing_job_id == ProcessingJob.id)
        .where(
            ProcessingJob.id == processing_job_id,
            ProcessingJob.floor_plan_id == floor_plan_id,
            ProcessingArtifact.artifact_kind == artifact_kind,
        )
        .order_by(ProcessingArtifact.id.desc())
        .limit(1)
    )


def add_processing_artifact(
    database_session: Session, artifact: ProcessingArtifact
) -> ProcessingArtifact:
    database_session.add(artifact)
    database_session.flush()
    return artifact
