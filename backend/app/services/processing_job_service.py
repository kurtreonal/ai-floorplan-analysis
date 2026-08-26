from sqlalchemy.orm import Session

from app.models import ProcessingJob, User
from app.repositories.floor_plan_repository import find_owned_floor_plan_for_update
from app.repositories.processing_job_repository import (
    add_processing_job,
    find_active_processing_job,
    update_processing_job_to_failed,
)


FLOOR_PLAN_ANALYSIS_JOB_TYPE = "floor_plan_analysis"
ACTIVE_PROCESSING_JOB_STATUSES = ("queued", "processing")
SAFE_PROCESSING_FAILURE_MESSAGE = "Floor-plan processing could not be started."


class FloorPlanNotFoundError(RuntimeError):
    """Raised when an owned floor plan is absent or inaccessible."""


class ActiveProcessingJobError(RuntimeError):
    """Raised when an authorized floor plan already has an active job."""

    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        super().__init__("An active processing job already exists.")


def start_floor_plan_processing(
    database_session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
) -> ProcessingJob:
    floor_plan = find_owned_floor_plan_for_update(
        database_session,
        floor_plan_id=floor_plan_id,
        owner_id=current_user.id,
    )
    if floor_plan is None:
        raise FloorPlanNotFoundError

    active_job = find_active_processing_job(
        database_session,
        floor_plan_id=floor_plan.id,
        job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
        active_statuses=ACTIVE_PROCESSING_JOB_STATUSES,
    )
    if active_job is not None:
        raise ActiveProcessingJobError(active_job.id)

    processing_job = ProcessingJob(
        floor_plan_id=floor_plan.id,
        job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
    )
    return add_processing_job(database_session, processing_job)


def mark_processing_job_failed(
    database_session: Session,
    *,
    processing_job: ProcessingJob,
) -> ProcessingJob:
    return update_processing_job_to_failed(
        database_session,
        processing_job=processing_job,
        error_message=SAFE_PROCESSING_FAILURE_MESSAGE,
    )
