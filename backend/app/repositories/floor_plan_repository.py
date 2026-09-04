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


def list_floor_plans_by_project(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int | None = None,
) -> list[FloorPlan]:
    statement = (
        select(FloorPlan)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .options(
            load_only(
                FloorPlan.id,
                FloorPlan.project_floor_id,
                FloorPlan.original_filename,
                FloorPlan.mime_type,
                FloorPlan.file_size,
                FloorPlan.processing_status,
            ),
            raiseload("*"),
        )
        .where(ProjectFloor.project_id == project_id)
        .order_by(
            ProjectFloor.sort_order.asc(),
            ProjectFloor.id.asc(),
            FloorPlan.id.asc(),
        )
    )
    if project_floor_id is not None:
        statement = statement.where(FloorPlan.project_floor_id == project_floor_id)
    return list(database_session.scalars(statement).all())


def find_floor_plan_by_id(
    database_session: Session,
    *,
    floor_plan_id: int,
) -> FloorPlan | None:
    return database_session.scalar(
        select(FloorPlan)
        .options(load_only(FloorPlan.id), raiseload("*"))
        .where(FloorPlan.id == floor_plan_id)
        .execution_options(populate_existing=True)
    )


def find_floor_plan_by_id_and_owner(
    database_session: Session,
    *,
    floor_plan_id: int,
    owner_id: int,
) -> FloorPlan | None:
    return database_session.scalar(
        select(FloorPlan)
        .join(ProjectFloor, FloorPlan.project_floor_id == ProjectFloor.id)
        .join(Project, ProjectFloor.project_id == Project.id)
        .options(load_only(FloorPlan.id), raiseload("*"))
        .where(
            FloorPlan.id == floor_plan_id,
            Project.owner_id == owner_id,
        )
        .execution_options(populate_existing=True)
    )


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
