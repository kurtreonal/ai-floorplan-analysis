from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.models.client_workflow import ProjectAssignment
from app.services.local_accounts import require_same_origin
from fastapi import Request
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import (
    ProjectNotFoundError,
    create_project,
    get_accessible_project,
    list_accessible_projects,
    update_project_details,
    ProjectDetailsConflictError,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)


def project_response(db, project):
    result = ProjectResponse.model_validate(project)
    assignment = db.get(ProjectAssignment, project.id)
    result.client_id = assignment.client_id if assignment else None
    from app.services.intake_schema import details
    intake = details(db,assignment,'intake_details')
    result.layout_type = intake.get('layout_type')
    from app.services.project_budget import allocated
    result.allocated_budget=allocated(db,project.id)
    result.service_types = intake.get('service_types') or ([project.service_type] if project.service_type else [])
    result.intake_status = intake.get('status','assigned')
    result.preferred_designer_id = intake.get('preferred_designer_id')
    preferred = db.get(User,result.preferred_designer_id) if result.preferred_designer_id else None
    result.preferred_designer_name = preferred.display_name if preferred else None
    designer = db.get(User, project.owner_id)
    result.designer_name = designer.display_name if designer else None
    return result


@router.patch('/{project_id}', response_model=ProjectResponse)
def update_project_endpoint(project_id: Annotated[int, Path(gt=0)], project_data: ProjectUpdate,
        current_user: User = Depends(require_roles('ADMIN')), database_session: Session = Depends(get_db)):
    from pydantic import ValidationError
    try:
        project = update_project_details(database_session, current_user=current_user,
            project_id=project_id, project_data=project_data)
        result = project_response(database_session, project)
        database_session.commit()
        logger.info('PROJECT_DETAILS_SAVED project_id=%s user_id=%s', project_id, current_user.id)
        return result
    except (ProjectNotFoundError, ProjectDetailsConflictError, SQLAlchemyError, ValidationError) as error:
        database_session.rollback()
        code, response_status = ('PROJECT_NOT_FOUND', 404) if isinstance(error, ProjectNotFoundError) else (
            ('PROJECT_DETAILS_CONFLICT', 409) if isinstance(error, ProjectDetailsConflictError) else (
            ('PROJECT_DETAILS_INVALID', 422) if isinstance(error, ValidationError) else ('PROJECT_UPDATE_FAILED', 503)))
        raise HTTPException(response_status, detail={'error': {'code': code,
            'message': 'Project details could not be saved. Reload before retrying a conflicting edit.', 'details': {}}}) from None


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

    return [project_response(database_session, project) for project in projects]


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

    return project_response(database_session, project)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    project_data: ProjectCreate,
    current_user: User = Depends(require_roles("ADMIN")),
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
    except ValueError:
        database_session.rollback()
        raise HTTPException(422, 'Choose a valid client and designer.') from None
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

    return project_response(database_session, project)


@router.delete('/{project_id}', status_code=204)
def delete_project(project_id: Annotated[int, Path(gt=0)], request: Request,
                   user: User = Depends(require_roles('ADMIN')), db: Session = Depends(get_db)):
    require_same_origin(request)
    try:
        project = get_accessible_project(db, current_user=user, project_id=project_id)
        project.status = 'archived'
        from app.services.activity_log import record
        record(db, user, 'PROJECT_ARCHIVED', 'project', project.id, 'Removed project from active projects. Original uploads and saved estimates retained.')
        db.commit()
        logger.info('PROJECT_DELETED project_id=%s user_id=%s retained_history=true', project_id, user.id)
    except ProjectNotFoundError:
        raise HTTPException(404, 'Project not found.') from None
