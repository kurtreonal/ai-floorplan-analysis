from sqlalchemy import select
from sqlalchemy.orm import Session, raiseload

from app.models import ProjectFloor


def add_project_floor(
    database_session: Session,
    project_floor: ProjectFloor,
) -> ProjectFloor:
    database_session.add(project_floor)
    database_session.flush()
    return project_floor


def list_project_floors(
    database_session: Session,
    *,
    project_id: int,
) -> list[ProjectFloor]:
    return list(
        database_session.scalars(
            select(ProjectFloor)
            .options(raiseload("*"))
            .where(ProjectFloor.project_id == project_id)
            .order_by(ProjectFloor.sort_order.asc(), ProjectFloor.id.asc())
        ).all()
    )


def find_project_floor_by_id_and_project(
    database_session: Session,
    *,
    project_floor_id: int,
    project_id: int,
) -> ProjectFloor | None:
    return database_session.scalar(
        select(ProjectFloor)
        .options(raiseload("*"))
        .where(
            ProjectFloor.id == project_floor_id,
            ProjectFloor.project_id == project_id,
        )
        .execution_options(populate_existing=True)
    )
