from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.dataset_approver_assignment import (
    CurrentDatasetApproverAssignment,
    CurrentDatasetApproverResponse,
    DatasetApproverAssignmentAdminResponse,
    DatasetApproverAssignmentWrite,
)
from app.services.dataset_approver_assignment_service import (
    DatasetApproverAssignmentServiceError,
    create_dataset_approver_assignment,
    deactivate_dataset_approver_assignment,
    retrieve_current_dataset_approver,
    retrieve_dataset_approver_history,
)


router = APIRouter(tags=["dataset approver authority"])
admin_router = APIRouter(
    prefix="/api/admin/dataset-approver-assignments",
    tags=["dataset approver administration"],
)
AssignmentId = Annotated[int, Path(gt=0, le=9_223_372_036_854_775_807)]


def _error(error: DatasetApproverAssignmentServiceError) -> HTTPException:
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if error.code in {
        "DATASET_APPROVER_ASSIGNEE_NOT_FOUND",
        "DATASET_APPROVER_ASSIGNMENT_NOT_FOUND",
    }:
        status_code = status.HTTP_404_NOT_FOUND
    elif error.code in {
        "DATASET_APPROVER_ASSIGNMENT_CONFLICT",
        "DATASET_APPROVER_SELF_ASSIGNMENT_DENIED",
    }:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": {},
            }
        },
    )


def _current_response(item) -> CurrentDatasetApproverAssignment:
    return CurrentDatasetApproverAssignment(**item.__dict__)


def _admin_response(item) -> DatasetApproverAssignmentAdminResponse:
    return DatasetApproverAssignmentAdminResponse(**item.__dict__)


@router.get(
    "/api/dataset-approver-assignment",
    response_model=CurrentDatasetApproverResponse,
)
def get_current_dataset_approver_assignment(
    _current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> CurrentDatasetApproverResponse:
    try:
        item = retrieve_current_dataset_approver(database_session)
    except DatasetApproverAssignmentServiceError as error:
        raise _error(error) from None
    return CurrentDatasetApproverResponse(
        assignment=_current_response(item) if item is not None else None
    )


@admin_router.get("", response_model=list[DatasetApproverAssignmentAdminResponse])
def get_dataset_approver_assignment_history(
    _current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> list[DatasetApproverAssignmentAdminResponse]:
    try:
        return [
            _admin_response(item)
            for item in retrieve_dataset_approver_history(database_session)
        ]
    except DatasetApproverAssignmentServiceError as error:
        raise _error(error) from None


@admin_router.post(
    "",
    response_model=DatasetApproverAssignmentAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_dataset_approver_assignment(
    data: DatasetApproverAssignmentWrite,
    current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> DatasetApproverAssignmentAdminResponse:
    try:
        return _admin_response(create_dataset_approver_assignment(
            database_session,
            current_user=current_user,
            data=data,
        ))
    except DatasetApproverAssignmentServiceError as error:
        raise _error(error) from None


@admin_router.post(
    "/{assignment_id}/deactivate",
    response_model=DatasetApproverAssignmentAdminResponse,
)
def post_dataset_approver_assignment_deactivation(
    assignment_id: AssignmentId,
    current_user: User = Depends(require_roles("ADMIN")),
    database_session: Session = Depends(get_db),
) -> DatasetApproverAssignmentAdminResponse:
    try:
        return _admin_response(deactivate_dataset_approver_assignment(
            database_session,
            current_user=current_user,
            assignment_id=assignment_id,
        ))
    except DatasetApproverAssignmentServiceError as error:
        raise _error(error) from None
