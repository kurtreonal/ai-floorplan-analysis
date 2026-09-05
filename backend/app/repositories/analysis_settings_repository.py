from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FloorElevationSetting, FloorPlan, FloorPlanPage, FloorPlanSource, PageScaleSetting, ProjectFloor


def find_floor(session: Session, *, project_id: int, floor_id: int, lock: bool = False):
    query = select(ProjectFloor).where(ProjectFloor.id == floor_id, ProjectFloor.project_id == project_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def list_pages(session: Session, floor_id: int):
    return session.execute(
        select(FloorPlanPage, FloorPlan.id)
        .join(FloorPlanSource, FloorPlanSource.id == FloorPlanPage.floor_plan_source_id)
        .join(FloorPlan, FloorPlan.id == FloorPlanSource.floor_plan_id)
        .where(FloorPlan.project_floor_id == floor_id)
        .order_by(FloorPlan.id, FloorPlanPage.page_number)
    ).all()


def latest_elevation(session: Session, floor_id: int):
    return session.scalar(select(FloorElevationSetting).where(
        FloorElevationSetting.project_floor_id == floor_id
    ).order_by(FloorElevationSetting.id.desc()).limit(1))


def latest_scales(session: Session, page_ids: list[int]):
    if not page_ids:
        return {}
    latest = select(func.max(PageScaleSetting.id)).where(
        PageScaleSetting.floor_plan_page_id.in_(page_ids)
    ).group_by(PageScaleSetting.floor_plan_page_id)
    return {row.floor_plan_page_id: row for row in session.scalars(
        select(PageScaleSetting).where(PageScaleSetting.id.in_(latest))
    )}


def add_approval(session: Session, record):
    session.add(record)
    session.flush()
    session.refresh(record)
    return record
