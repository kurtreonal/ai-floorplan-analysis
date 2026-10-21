from sqlalchemy import select
from app.models import PlanMeasurementSetting,ProjectFloor


def lock_floor(session,floor_id):
    return session.scalar(select(ProjectFloor).where(ProjectFloor.id==floor_id).with_for_update())


def current(session,plan_id,*,lock=False):
    query=(select(PlanMeasurementSetting).where(PlanMeasurementSetting.floor_plan_id==plan_id)
        .order_by(PlanMeasurementSetting.revision.desc()).limit(1))
    # A locking read sees the latest committed revision even when authorization
    # has already established an older MySQL REPEATABLE READ snapshot.
    return session.scalar(query.with_for_update() if lock else query)


def retry(session,plan_id,request_id):
    return session.scalar(select(PlanMeasurementSetting).where(PlanMeasurementSetting.floor_plan_id==plan_id,PlanMeasurementSetting.request_id==str(request_id)).with_for_update())


def append(session,**values):
    row=PlanMeasurementSetting(**values);session.add(row);session.flush();return row
