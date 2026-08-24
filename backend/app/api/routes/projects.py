from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import create_project


router = APIRouter(prefix="/api/projects", tags=["projects"])


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
