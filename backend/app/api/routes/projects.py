from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import (
    ProjectNotFoundError,
    create_project,
    get_accessible_project,
    list_accessible_projects,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
)
def list_projects_endpoint(
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> list[ProjectResponse]:
    try:
        projects = list_accessible_projects(
            database_session,
            current_user=current_user,
        )
    except SQLAlchemyError:
        database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "PROJECT_LIST_FAILED",
                    "message": "Projects could not be loaded.",
                    "details": {},
                }
            },
        ) from None

    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
)
def get_project_endpoint(
    project_id: Annotated[int, Path(gt=0)],
    current_user: User = Depends(require_roles("ADMIN", "DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        project = get_accessible_project(
            database_session,
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROJECT_NOT_FOUND",
                    "message": "The requested project was not found.",
                    "details": {},
                }
            },
        ) from None
    except SQLAlchemyError:
        database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "PROJECT_DETAIL_FAILED",
                    "message": "The project could not be loaded.",
                    "details": {},
                }
            },
        ) from None

    return ProjectResponse.model_validate(project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    project_data: ProjectCreate,
    current_user: User = Depends(require_roles("DESIGNER")),
    database_session: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        project = create_project(
            database_session,
            current_user=current_user,
            project_data=project_data,
        )
        database_session.commit()
        database_session.refresh(project)
    except SQLAlchemyError:
        database_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "PROJECT_CREATION_FAILED",
                    "message": "The project could not be created.",
                    "details": {},
                }
            },
        ) from None

    return ProjectResponse.model_validate(project)
