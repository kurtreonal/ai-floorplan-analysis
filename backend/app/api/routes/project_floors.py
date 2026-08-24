from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.project_floor import ProjectFloorCreate, ProjectFloorResponse
from app.services.project_floor_service import (
    create_project_floor,
    list_accessible_project_floors,
)
from app.services.project_service import ProjectNotFoundError


router = APIRouter(prefix="/api/projects", tags=["project floors"])


def _api_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        },
    )


@router.get(
    "/{project_id}/floors",
    response_model=list[ProjectFloorResponse],
    status_code=status.HTTP_200_OK,
)
def list_project_floors_endpoint(
    project_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> list[ProjectFloorResponse]:
    try:
        project_floors = list_accessible_project_floors(
            database_session,
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectNotFoundError:
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROJECT_NOT_FOUND",
            message="The requested project was not found.",
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PROJECT_FLOOR_LIST_FAILED",
            message="Project floors could not be loaded.",
        ) from None

    return [
        ProjectFloorResponse.model_validate(project_floor)
        for project_floor in project_floors
    ]


@router.post(
    "/{project_id}/floors",
    response_model=ProjectFloorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_floor_endpoint(
    project_id: Annotated[int, Path(gt=0)],
    floor_data: ProjectFloorCreate,
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ProjectFloorResponse:
    try:
        project_floor = create_project_floor(
            database_session,
            current_user=current_user,
            project_id=project_id,
            floor_data=floor_data,
        )
        database_session.commit()
        database_session.refresh(project_floor)
    except ProjectNotFoundError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PROJECT_NOT_FOUND",
            message="The requested project was not found.",
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise _api_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="PROJECT_FLOOR_CREATION_FAILED",
            message="The project floor could not be created.",
        ) from None

    return ProjectFloorResponse.model_validate(project_floor)
