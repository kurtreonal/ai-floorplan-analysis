from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ProcessingJob,
    ProcessingJobAttempt,
    ProcessingJobCancellation,
)


def lock_processing_job(
    database_session: Session,
    *,
    job_id: int,
) -> ProcessingJob | None:
    return database_session.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def active_attempt(
    database_session: Session,
    *,
    job_id: int,
) -> ProcessingJobAttempt | None:
    return database_session.scalar(
        select(ProcessingJobAttempt)
        .where(
            ProcessingJobAttempt.processing_job_id == job_id,
            ProcessingJobAttempt.active_marker.is_(True),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def lock_attempt(
    database_session: Session,
    *,
    attempt_id: int,
) -> ProcessingJobAttempt | None:
    return database_session.scalar(
        select(ProcessingJobAttempt)
        .where(ProcessingJobAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def find_attempt(
    database_session: Session,
    *,
    attempt_id: int,
) -> ProcessingJobAttempt | None:
    return database_session.get(ProcessingJobAttempt, attempt_id)


def maximum_attempt_number(database_session: Session, *, job_id: int) -> int:
    return database_session.scalar(
        select(func.max(ProcessingJobAttempt.attempt_number)).where(
            ProcessingJobAttempt.processing_job_id == job_id
        )
    ) or 0


def find_cancellation(
    database_session: Session,
    *,
    job_id: int,
) -> ProcessingJobCancellation | None:
    return database_session.scalar(
        select(ProcessingJobCancellation)
        .where(ProcessingJobCancellation.processing_job_id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def add_record(database_session: Session, record):
    database_session.add(record)
    database_session.flush()
    return record
