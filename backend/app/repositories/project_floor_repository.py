from sqlalchemy import select
from sqlalchemy.orm import Session, raiseload

from app.models import ProjectFloor


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
