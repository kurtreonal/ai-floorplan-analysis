from sqlalchemy.orm import Session

from app.models import Project, User
from app.repositories.project_repository import (
    add_project,
    list_all_projects,
    list_projects_by_owner,
)
from app.schemas.project import ProjectCreate


def create_project(
    database_session: Session,
    *,
    current_user: User,
    project_data: ProjectCreate,
) -> Project:
    project = Project(
        owner_id=current_user.id,
        name=project_data.name,
        client_name=project_data.client_name,
        location=project_data.location,
    )
    return add_project(database_session, project)


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
