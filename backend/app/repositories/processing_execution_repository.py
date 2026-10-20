from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ProcessingJob,
    ProcessingJobAttempt,
    ProcessingJobCancellation,
    InterpretationPageOutcome,
    FloorPlanInterpretationRun,
)
from app.repositories.floor_plan_lifecycle_repository import lock_plan


def lock_processing_job(
    database_session: Session,
    *,
    job_id: int,
) -> ProcessingJob | None:
    plan_id = database_session.scalar(select(ProcessingJob.floor_plan_id).where(ProcessingJob.id == job_id))
    if plan_id is not None:
        lock_plan(database_session, plan_id)
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


def failed_attempt_count(database_session: Session, *, job_id: int) -> int:
    """Successful page leases are not failed retry-budget attempts."""
    return database_session.scalar(select(func.count()).select_from(ProcessingJobAttempt).where(
        ProcessingJobAttempt.processing_job_id == job_id,
        ProcessingJobAttempt.status.in_(("failed", "lease_expired")),
    )) or 0


def has_trusted_page_continuation(database_session: Session, *, job_id: int) -> bool:
    """Called under the job lock: never recover arbitrary legacy processing."""
    latest = database_session.scalar(select(ProcessingJobAttempt).where(
        ProcessingJobAttempt.processing_job_id == job_id,
    ).order_by(ProcessingJobAttempt.attempt_number.desc()).limit(1))
    if latest is None or latest.status != "succeeded" or latest.active_marker is not None:
        return False
    completed = database_session.scalar(select(InterpretationPageOutcome.id).join(
        FloorPlanInterpretationRun,
        FloorPlanInterpretationRun.candidate_run_id == InterpretationPageOutcome.candidate_run_id,
    ).where(InterpretationPageOutcome.processing_job_id == job_id,
        InterpretationPageOutcome.selection_state == "selected",
        InterpretationPageOutcome.status == "completed",
        FloorPlanInterpretationRun.processing_job_id == job_id,
        FloorPlanInterpretationRun.floor_plan_page_id == InterpretationPageOutcome.floor_plan_page_id,
    ).limit(1))
    queued = database_session.scalar(select(InterpretationPageOutcome.id).where(
        InterpretationPageOutcome.processing_job_id == job_id,
        InterpretationPageOutcome.selection_state == "selected",
        InterpretationPageOutcome.status == "queued",
    ).limit(1))
    return completed is not None and queued is not None


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
