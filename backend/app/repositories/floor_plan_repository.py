from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import FloorPlan, Project, ProjectFloor


def add_floor_plan(
    database_session: Session,
    floor_plan: FloorPlan,
) -> FloorPlan:
    database_session.add(floor_plan)
    database_session.flush()
    return floor_plan


def find_owned_floor_plan_for_update(
    database_session: Session,
    *,
    floor_plan_id: int,
    owner_id: int,
) -> FloorPlan | None:
    return database_session.scalar(
        select(FloorPlan)
        .join(
            ProjectFloor,
            FloorPlan.project_floor_id == ProjectFloor.id,
        )
        .join(Project, ProjectFloor.project_id == Project.id)
        .options(load_only(FloorPlan.id), raiseload("*"))
        .where(
            FloorPlan.id == floor_plan_id,
            Project.owner_id == owner_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
