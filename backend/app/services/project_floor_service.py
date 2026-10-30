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
    floors=list_project_floors(
        database_session,
        project_id=project_id,
    )
    from app.services.plan_material_setup import floor_settings
    for floor in floors:floor.layout_type=floor_settings(database_session,project_id,floor.id).get('layoutType')
    return floors


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
    from app.repositories.routing_repository import lock_context
    lock_context(database_session,project_id,[])
    project_floor = ProjectFloor(
        project_id=project.id,
        name=floor_data.name,
        sort_order=max((floor.sort_order for floor in list_project_floors(database_session,project_id=project_id)),default=-1)+1,
    )
    floor=add_project_floor(database_session, project_floor)
    if floor_data.layout_type:
        from app.services.plan_material_setup import append
        append(database_session,current_user,project_id,floor_id=floor.id,layout=floor_data.layout_type)
    floor.layout_type=floor_data.layout_type
    return floor
