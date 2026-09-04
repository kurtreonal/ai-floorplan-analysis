from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.processing_job import (
    ProcessingJobStartResponse,
    ProcessingJobStatusResponse,
    ProcessingJobHistoryItemResponse,
)
from app.services.processing_job_service import (
    ActiveProcessingJobError,
    DEFAULT_PROCESSING_JOB_HISTORY_LIMIT,
    FloorPlanNotFoundError,
    MAXIMUM_PROCESSING_JOB_HISTORY_LIMIT,
    ProcessingJobNotFoundError,
    get_accessible_processing_job,
    get_safe_processing_error_message,
    list_accessible_processing_jobs,
    start_floor_plan_processing,
)


router = APIRouter(tags=["processing jobs"])


def _api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": dict(details or {}),
            }
        },
    )


@router.get(
    "/api/floor-plans/{floor_plan_id}/processing-jobs",
    response_model=list[ProcessingJobHistoryItemResponse],
    status_code=status.HTTP_200_OK,
)
def list_processing_job_history_endpoint(
    floor_plan_id: Annotated[int, Path(gt=0)],
    limit: Annotated[
        int,
        Query(ge=1, le=MAXIMUM_PROCESSING_JOB_HISTORY_LIMIT),
    ] = DEFAULT_PROCESSING_JOB_HISTORY_LIMIT,
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> list[ProcessingJobHistoryItemResponse]:
    try:
        processing_jobs = list_accessible_processing_jobs(
            database_session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
            limit=limit,
        )
    except FloorPlanNotFoundError:
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FLOOR_PLAN_NOT_FOUND",
            message="The requested floor plan was not found.",
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PROCESSING_JOB_HISTORY_FAILED",
            message="Processing-job history could not be loaded.",
        ) from None

    return [
        ProcessingJobHistoryItemResponse(
            job_id=processing_job.id,
            type=processing_job.job_type,
            status=processing_job.status,
            progress=processing_job.progress,
            error_message=get_safe_processing_error_message(processing_job),
            created_at=processing_job.created_at,
            updated_at=processing_job.updated_at,
        )
        for processing_job in processing_jobs
    ]


@router.post(
    "/api/floor-plans/{floor_plan_id}/process",
    response_model=ProcessingJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_floor_plan_processing_endpoint(
    floor_plan_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ProcessingJobStartResponse:
    try:
        processing_job = start_floor_plan_processing(
            database_session,
            current_user=current_user,
            floor_plan_id=floor_plan_id,
        )
        database_session.commit()
    except FloorPlanNotFoundError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FLOOR_PLAN_NOT_FOUND",
            message="The requested floor plan was not found.",
        ) from None
    except ActiveProcessingJobError as error:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_409_CONFLICT,
            code="PROCESSING_JOB_ALREADY_ACTIVE",
            message="A processing job is already active for this floor plan.",
            details={"job_id": error.job_id},
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PROCESSING_JOB_CREATION_FAILED",
            message="The processing job could not be created.",
        ) from None

    return ProcessingJobStartResponse(
        job_id=processing_job.id,
        status=processing_job.status,
    )


@router.get(
    "/api/processing-jobs/{job_id}",
    response_model=ProcessingJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
def get_processing_job_status_endpoint(
    job_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ProcessingJobStatusResponse:
    try:
        processing_job = get_accessible_processing_job(
            database_session,
            current_user=current_user,
            job_id=job_id,
        )
    except ProcessingJobNotFoundError:
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROCESSING_JOB_NOT_FOUND",
            message="The requested processing job was not found.",
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PROCESSING_JOB_STATUS_FAILED",
            message="The processing job status could not be loaded.",
        ) from None

    return ProcessingJobStatusResponse(
        job_id=processing_job.id,
        type=processing_job.job_type,
        status=processing_job.status,
        progress=processing_job.progress,
        error_message=get_safe_processing_error_message(processing_job),
    )
