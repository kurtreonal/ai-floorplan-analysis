from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.processing_job import ProcessingJobStartResponse
from app.services.processing_job_service import (
    ActiveProcessingJobError,
    FloorPlanNotFoundError,
    start_floor_plan_processing,
)


router = APIRouter(prefix="/api/floor-plans", tags=["processing jobs"])


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


@router.post(
    "/{floor_plan_id}/process",
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
