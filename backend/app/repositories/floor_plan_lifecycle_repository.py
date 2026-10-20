from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FloorPlan, FloorPlanLifecycleEvent, ProjectFloor


def active_floor_plan(floor_plan_id=FloorPlan.id):
    """Explicit predicate for active lists/inputs, not a global ORM visibility filter."""
    latest = (select(FloorPlanLifecycleEvent.action)
              .where(FloorPlanLifecycleEvent.floor_plan_id == floor_plan_id)
              .order_by(FloorPlanLifecycleEvent.revision.desc()).limit(1)
              .correlate_except(FloorPlanLifecycleEvent).scalar_subquery())
    return func.coalesce(latest, "restored") == "restored"


def latest_event(session: Session, floor_plan_id: int, *, lock=False):
    query = (select(FloorPlanLifecycleEvent)
             .where(FloorPlanLifecycleEvent.floor_plan_id == floor_plan_id)
             .order_by(FloorPlanLifecycleEvent.revision.desc()).limit(1))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def lock_plan(session: Session, floor_plan_id: int):
    # Same floor -> plan -> job ordering as canonical saves and removal.
    floor_id = session.scalar(select(FloorPlan.project_floor_id).where(FloorPlan.id == floor_plan_id))
    if floor_id is not None:
        session.scalar(select(ProjectFloor).where(ProjectFloor.id == floor_id).with_for_update())
    plan = session.scalar(select(FloorPlan).where(FloorPlan.id == floor_plan_id)
                          .with_for_update().execution_options(populate_existing=True))
    return plan


def lock_active_plan(session: Session, floor_plan_id: int):
    plan = lock_plan(session, floor_plan_id)
    event = latest_event(session, floor_plan_id, lock=True) if plan is not None else None
    return plan if event is None or event.action != "removed" else None
