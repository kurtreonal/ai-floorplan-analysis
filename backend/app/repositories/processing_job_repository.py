from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import ProcessingJob


def find_active_processing_job(
    database_session: Session,
    *,
    floor_plan_id: int,
    job_type: str,
    active_statuses: Collection[str],
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .options(
            load_only(ProcessingJob.id),
            raiseload("*"),
        )
        .where(
            ProcessingJob.floor_plan_id == floor_plan_id,
            ProcessingJob.job_type == job_type,
            ProcessingJob.status.in_(tuple(active_statuses)),
        )
        .order_by(
            ProcessingJob.created_at.desc(),
            ProcessingJob.id.desc(),
        )
        .limit(1)
    )


def add_processing_job(
    database_session: Session,
    processing_job: ProcessingJob,
) -> ProcessingJob:
    database_session.add(processing_job)
    database_session.flush()
    return processing_job


def update_processing_job_to_failed(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
    error_message: str,
) -> ProcessingJob:
    processing_job.status = "failed"
    processing_job.error_message = error_message
    database_session.flush()
    return processing_job
