from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import FloorPlan, LayoutSaveRequest, LayoutVersion, ProjectFloor


LAYOUT_VERSION_COLUMNS = tuple(
    getattr(LayoutVersion, column.name)
    for column in LayoutVersion.__table__.columns
)


def lock_project_floor(
    database_session: Session,
    *,
    project_floor_id: int,
) -> ProjectFloor | None:
    return database_session.scalar(
        select(ProjectFloor)
        .options(
            load_only(
                ProjectFloor.id,
                ProjectFloor.project_id,
                ProjectFloor.name,
                ProjectFloor.sort_order,
            ),
            raiseload("*"),
        )
        .where(ProjectFloor.id == project_floor_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def find_floor_plan_for_floor(
    database_session: Session,
    *,
    floor_plan_id: int,
    project_floor_id: int,
) -> FloorPlan | None:
    return database_session.scalar(
        select(FloorPlan)
        .options(
            load_only(FloorPlan.id, FloorPlan.project_floor_id),
            raiseload("*"),
        )
        .where(
            FloorPlan.id == floor_plan_id,
            FloorPlan.project_floor_id == project_floor_id,
        )
        .execution_options(populate_existing=True)
    )


def maximum_version_number(
    database_session: Session,
    *,
    project_floor_id: int,
) -> int | None:
    return database_session.scalar(
        select(func.max(LayoutVersion.version_number)).where(
            LayoutVersion.project_floor_id == project_floor_id
        )
    )


def list_current_versions(
    database_session: Session,
    *,
    project_floor_id: int,
) -> tuple[LayoutVersion, ...]:
    return tuple(
        database_session.scalars(
            select(LayoutVersion)
            .options(load_only(*LAYOUT_VERSION_COLUMNS), raiseload("*"))
            .where(
                LayoutVersion.project_floor_id == project_floor_id,
                LayoutVersion.is_current.is_(True),
            )
            .order_by(LayoutVersion.version_number.asc(), LayoutVersion.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def clear_current_marker(
    database_session: Session,
    *,
    project_floor_id: int,
) -> None:
    database_session.execute(
        update(LayoutVersion)
        .where(
            LayoutVersion.project_floor_id == project_floor_id,
            LayoutVersion.is_current.is_(True),
        )
        .values(is_current=None)
        .execution_options(synchronize_session=False)
    )


def add_layout_version(
    database_session: Session,
    layout_version: LayoutVersion,
) -> None:
    database_session.add(layout_version)
    database_session.flush()


def find_layout_save_request(
    database_session: Session,
    *,
    project_floor_id: int,
    idempotency_key: str,
) -> LayoutSaveRequest | None:
    return database_session.scalar(
        select(LayoutSaveRequest)
        .where(
            LayoutSaveRequest.project_floor_id == project_floor_id,
            LayoutSaveRequest.idempotency_key == idempotency_key,
        )
        .with_for_update()
    )


def add_layout_save_request(
    database_session: Session,
    request: LayoutSaveRequest,
) -> None:
    database_session.add(request)
    database_session.flush()


def find_layout_version_by_id(
    database_session: Session,
    *,
    layout_version_id: int,
) -> LayoutVersion | None:
    return database_session.scalar(
        select(LayoutVersion)
        .options(load_only(*LAYOUT_VERSION_COLUMNS), raiseload("*"))
        .where(LayoutVersion.id == layout_version_id)
        .execution_options(populate_existing=True)
    )


def find_layout_version(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
    version_number: int,
) -> LayoutVersion | None:
    return database_session.scalar(
        select(LayoutVersion)
        .options(load_only(*LAYOUT_VERSION_COLUMNS), raiseload("*"))
        .where(
            LayoutVersion.project_id == project_id,
            LayoutVersion.project_floor_id == project_floor_id,
            LayoutVersion.version_number == version_number,
        )
        .execution_options(populate_existing=True)
    )


def find_current_layout_version(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
) -> tuple[LayoutVersion, ...]:
    return tuple(
        database_session.scalars(
            select(LayoutVersion)
            .options(load_only(*LAYOUT_VERSION_COLUMNS), raiseload("*"))
            .where(
                LayoutVersion.project_id == project_id,
                LayoutVersion.project_floor_id == project_floor_id,
                LayoutVersion.is_current.is_(True),
            )
            .order_by(LayoutVersion.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def list_layout_versions(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
) -> tuple[LayoutVersion, ...]:
    return tuple(
        database_session.scalars(
            select(LayoutVersion)
            .options(load_only(*LAYOUT_VERSION_COLUMNS), raiseload("*"))
            .where(
                LayoutVersion.project_id == project_id,
                LayoutVersion.project_floor_id == project_floor_id,
            )
            .order_by(LayoutVersion.version_number.asc(), LayoutVersion.id.asc())
            .execution_options(populate_existing=True)
        ).all()
    )


def set_current_marker(
    database_session: Session,
    *,
    layout_version_id: int,
) -> None:
    database_session.execute(
        update(LayoutVersion)
        .where(LayoutVersion.id == layout_version_id)
        .values(is_current=True)
        .execution_options(synchronize_session=False)
    )
    database_session.flush()
