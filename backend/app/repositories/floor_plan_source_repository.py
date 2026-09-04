from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import FloorPlan, FloorPlanPage, FloorPlanSource


def add_floor_plan_source(
    database_session: Session,
    *,
    floor_plan: FloorPlan,
    original_sha256: str,
    page_count: int,
) -> FloorPlanSource:
    source = FloorPlanSource(
        floor_plan=floor_plan,
        original_sha256=original_sha256,
        pages=[FloorPlanPage(page_number=number) for number in range(1, page_count + 1)],
    )
    database_session.add(source)
    database_session.flush()
    return source


def list_floor_plans_with_source_identity(
    database_session: Session,
) -> list[FloorPlan]:
    return list(
        database_session.scalars(
            select(FloorPlan)
            .options(
                selectinload(FloorPlan.source_manifest).selectinload(
                    FloorPlanSource.pages
                )
            )
            .order_by(FloorPlan.id.asc())
        ).all()
    )
