from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.layout import (
    MAXIMUM_DATABASE_ID,
    LayoutResponse,
    LayoutSaveRequest,
)
from app.services.layout_service import (
    LayoutServiceError,
    retrieve_accessible_current_layout,
    save_owned_layout,
)
from app.services.layout_version_service import LayoutVersionRecord


router = APIRouter(prefix="/api/projects", tags=["layouts"])


def _api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


def _response(record: LayoutVersionRecord) -> LayoutResponse:
    return LayoutResponse(
        id=record.id,
        project_id=record.project_id,
        project_floor_id=record.project_floor_id,
        floor_plan_id=record.floor_plan_id,
        version_number=record.version_number,
        schema_version=record.schema_version,
        is_current=True,
        created_at=record.created_at,
        geometry=record.geometry.to_dict(),
        extension=record.extension.to_dict() if record.extension else None,
    )


def _raise_service_error(error: LayoutServiceError, *, saving: bool) -> None:
    if error.code == "AUTHORIZATION_DENIED":
        raise _api_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="AUTHORIZATION_DENIED",
            message="The authenticated user is not authorized for this action.",
        ) from None
    if error.code == "LAYOUT_NOT_FOUND":
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="LAYOUT_NOT_FOUND",
            message="The requested layout was not found.",
        ) from None
    if error.code == "INVALID_LAYOUT_GEOMETRY":
        raise _api_error(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_LAYOUT_GEOMETRY",
            message="The layout geometry is invalid.",
        ) from None
    if error.code in {"STALE_LAYOUT_VERSION", "IDEMPOTENCY_KEY_CONFLICT"}:
        raise _api_error(
            status_code=status.HTTP_409_CONFLICT,
            code=error.code,
            message=(
                "The layout changed after this edit began. Reload before saving."
                if error.code == "STALE_LAYOUT_VERSION"
                else "The save request identity was already used for different content."
            ),
        ) from None
    raise _api_error(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="LAYOUT_SAVE_FAILED" if saving else "LAYOUT_RETRIEVAL_FAILED",
        message=(
            "The layout could not be saved."
            if saving
            else "The layout could not be loaded."
        ),
    ) from None


@router.get(
    "/{project_id}/floors/{project_floor_id}/layouts",
    response_model=LayoutResponse,
    status_code=status.HTTP_200_OK,
)
def get_current_layout(
    project_id: Annotated[int, Path(gt=0, le=MAXIMUM_DATABASE_ID)],
    project_floor_id: Annotated[int, Path(gt=0, le=MAXIMUM_DATABASE_ID)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> LayoutResponse:
    try:
        record = retrieve_accessible_current_layout(
            database_session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
        )
    except LayoutServiceError as error:
        _raise_service_error(error, saving=False)
    return _response(record)


@router.post(
    "/{project_id}/floors/{project_floor_id}/layouts",
    response_model=LayoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_layout(
    payload: LayoutSaveRequest,
    project_id: Annotated[int, Path(gt=0, le=MAXIMUM_DATABASE_ID)],
    project_floor_id: Annotated[int, Path(gt=0, le=MAXIMUM_DATABASE_ID)],
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> LayoutResponse:
    try:
        record = save_owned_layout(
            database_session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            geometry_payload=payload.geometry.model_dump(mode="json", by_alias=True),
            expected_version_number=payload.expected_version_number,
            idempotency_key=str(payload.idempotency_key),
        )
    except LayoutServiceError as error:
        _raise_service_error(error, saving=True)
    return _response(record)
