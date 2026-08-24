from sqlalchemy.orm import Session

from app.models import FloorPlan


def add_floor_plan(
    database_session: Session,
    floor_plan: FloorPlan,
) -> FloorPlan:
    database_session.add(floor_plan)
    database_session.flush()
    return floor_plan
