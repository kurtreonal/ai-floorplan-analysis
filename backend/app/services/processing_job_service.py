from sqlalchemy.orm import Session

from app.models import ProcessingJob, User
from app.repositories.floor_plan_repository import (
    find_floor_plan_by_id,
    find_floor_plan_by_id_and_owner,
    find_owned_floor_plan_for_update,
)
from app.repositories.processing_job_repository import (
    add_processing_job,
    find_active_processing_job,
    find_processing_job_by_id,
    find_processing_job_by_id_and_owner,
    list_processing_jobs_for_floor_plan,
    update_processing_job_to_failed,
)


FLOOR_PLAN_ANALYSIS_JOB_TYPE = "floor_plan_analysis"
ACTIVE_PROCESSING_JOB_STATUSES = ("queued", "processing")
SAFE_PROCESSING_FAILURE_MESSAGE = "Floor-plan processing could not be started."
SAFE_PROCESSING_STATUS_ERROR_MESSAGE = "Floor-plan processing failed."
DEFAULT_PROCESSING_JOB_HISTORY_LIMIT = 50
MAXIMUM_PROCESSING_JOB_HISTORY_LIMIT = 100


class FloorPlanNotFoundError(RuntimeError):
    """Raised when an owned floor plan is absent or inaccessible."""


class ActiveProcessingJobError(RuntimeError):
    """Raised when an authorized floor plan already has an active job."""

    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        super().__init__("An active processing job already exists.")


class ProcessingJobNotFoundError(RuntimeError):
    """Raised when a processing job is absent or inaccessible."""


def list_accessible_processing_jobs(
    database_session: Session,
    *,
    current_user: User,
    floor_plan_id: int,
    limit: int = DEFAULT_PROCESSING_JOB_HISTORY_LIMIT,
) -> list[ProcessingJob]:
    role_name = current_user.role.name
    if role_name == "DESIGNER":
        floor_plan = find_floor_plan_by_id_and_owner(
            database_session,
            floor_plan_id=floor_plan_id,
            owner_id=current_user.id,
        )
    elif role_name == "ADMIN":
        floor_plan = find_floor_plan_by_id(
            database_session,
            floor_plan_id=floor_plan_id,
        )
    else:
        raise ValueError("The current role cannot access processing jobs.")

    if floor_plan is None:
        raise FloorPlanNotFoundError
    return list_processing_jobs_for_floor_plan(
        database_session,
        floor_plan_id=floor_plan.id,
        job_type=FLOOR_PLAN_ANALYSIS_JOB_TYPE,
        limit=limit,
    )


def get_accessible_processing_job(
    database_session: Session,
    *,
    current_user: User,
    job_id: int,
) -> ProcessingJob:
    role_name = current_user.role.name
    if role_name == "DESIGNER":
        processing_job = find_processing_job_by_id_and_owner(
            database_session,
            job_id=job_id,
            owner_id=current_user.id,
        )
    elif role_name == "ADMIN":
        processing_job = find_processing_job_by_id(
            database_session,
            job_id=job_id,
        )
    else:
        raise ValueError("The current role cannot access processing jobs.")

    if processing_job is None:
        raise ProcessingJobNotFoundError
    return processing_job


def get_safe_processing_error_message(
    processing_job: ProcessingJob,
) -> str | None:
    if processing_job.status == "failed":
        return SAFE_PROCESSING_STATUS_ERROR_MESSAGE
    return None


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
