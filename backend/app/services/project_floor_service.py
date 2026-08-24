from sqlalchemy.orm import Session

from app.models import ProjectFloor, User
from app.repositories.project_floor_repository import (
    add_project_floor,
    list_project_floors,
)
from app.schemas.project_floor import ProjectFloorCreate
from app.services.project_service import get_accessible_project


def list_accessible_project_floors(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
) -> list[ProjectFloor]:
    get_accessible_project(
        database_session,
        current_user=current_user,
        project_id=project_id,
    )
    return list_project_floors(
        database_session,
        project_id=project_id,
    )


def create_project_floor(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    floor_data: ProjectFloorCreate,
) -> ProjectFloor:
    project = get_accessible_project(
        database_session,
        current_user=current_user,
        project_id=project_id,
    )
    project_floor = ProjectFloor(
        project_id=project.id,
        name=floor_data.name,
    )
    return add_project_floor(database_session, project_floor)
