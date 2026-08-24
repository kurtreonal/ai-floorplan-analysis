from sqlalchemy.orm import Session

from app.models import Project, User
from app.repositories.project_repository import add_project
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
