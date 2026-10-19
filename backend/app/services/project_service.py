from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Project, User
from app.repositories.project_repository import (
    add_project,
    find_project_by_id,
    find_project_by_id_and_owner,
    list_all_projects,
    list_projects_by_owner,
)
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, PROJECT_DETAIL_FIELDS


class ProjectNotFoundError(RuntimeError):
    """Raised when a project is absent or inaccessible to the current user."""


class ProjectDetailsConflictError(RuntimeError):
    """The submitted edit was based on obsolete project metadata."""


def create_project(
    database_session: Session,
    *,
    current_user: User,
    project_data: ProjectCreate,
) -> Project:
    project = Project(
        owner_id=current_user.id,
        **project_data.model_dump(),
    )
    return add_project(database_session, project)


def update_project_details(database_session: Session, *, current_user: User,
                           project_id: int, project_data: ProjectUpdate) -> Project:
    if current_user.role.name != 'DESIGNER':
        raise PermissionError('Only a Designer can edit project intake details.')
    get_accessible_project(database_session, current_user=current_user, project_id=project_id)
    project = database_session.scalar(select(Project).where(Project.id == project_id)
        .with_for_update().execution_options(populate_existing=True))
    if project is None:
        raise ProjectNotFoundError
    changes = project_data.model_dump(exclude_unset=True, exclude={'expected_details_revision'})
    merged = {key: getattr(project, key) for key in PROJECT_DETAIL_FIELDS} | changes
    # Changing away from Other deliberately clears its no-longer-applicable description.
    if 'service_type' in changes and changes['service_type'] != 'other' and 'service_type_other' not in changes:
        merged['service_type_other'] = None
        changes['service_type_other'] = None
    ProjectCreate.model_validate(merged)
    if ProjectResponse.model_validate(project).details_revision != project_data.expected_details_revision:
        # A lost successful response can be retried, but never overwrite a newer edit.
        if all(getattr(project, key) == value for key, value in changes.items()):
            return project
        raise ProjectDetailsConflictError
    for key, value in changes.items():
        setattr(project, key, value)
    database_session.flush()
    return project


def list_accessible_projects(
    database_session: Session,
    *,
    current_user: User,
) -> list[Project]:
    if current_user.role.name == "DESIGNER":
        return list_projects_by_owner(
            database_session,
            owner_id=current_user.id,
        )
    if current_user.role.name == "ADMIN":
        return list_all_projects(database_session)

    raise ValueError("The current role cannot access projects.")


def get_accessible_project(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
) -> Project:
    if current_user.role.name == "DESIGNER":
        project = find_project_by_id_and_owner(
            database_session,
            project_id=project_id,
            owner_id=current_user.id,
        )
    elif current_user.role.name == "ADMIN":
        project = find_project_by_id(
            database_session,
            project_id=project_id,
        )
    else:
        raise ValueError("The current role cannot access projects.")

    if project is None:
        raise ProjectNotFoundError
    return project
