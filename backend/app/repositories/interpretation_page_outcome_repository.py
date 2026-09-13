from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FloorPlanPage, FloorPlanSource, InterpretationPageOutcome


def list_page_outcomes(session: Session, *, processing_job_id: int) -> list[InterpretationPageOutcome]:
    return list(session.scalars(
        select(InterpretationPageOutcome)
        .where(InterpretationPageOutcome.processing_job_id == processing_job_id)
        .order_by(InterpretationPageOutcome.page_number.asc())
    ).all())


def find_page_outcome(session: Session, *, processing_job_id: int, floor_plan_page_id: int) -> InterpretationPageOutcome | None:
    return session.scalar(select(InterpretationPageOutcome).where(
        InterpretationPageOutcome.processing_job_id == processing_job_id,
        InterpretationPageOutcome.floor_plan_page_id == floor_plan_page_id,
    ).with_for_update())


def list_pages_for_floor_plan(session: Session, *, floor_plan_id: int) -> list[FloorPlanPage]:
    return list(session.scalars(
        select(FloorPlanPage)
        .join(FloorPlanSource, FloorPlanPage.floor_plan_source_id == FloorPlanSource.id)
        .where(FloorPlanSource.floor_plan_id == floor_plan_id)
        .order_by(FloorPlanPage.page_number.asc())
    ).all())
