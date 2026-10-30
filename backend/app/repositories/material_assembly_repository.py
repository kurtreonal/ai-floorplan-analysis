from sqlalchemy import inspect, select
from app.models.material_assembly import MaterialAssembly


def available(session):
    # Per transaction/connection, not a process-global negative schema cache.
    return inspect(session.connection()).has_table(MaterialAssembly.__tablename__)


def records(session, *, lock=False):
    if not available(session):
        return []
    query = select(MaterialAssembly).order_by(MaterialAssembly.material_id)
    return list(session.scalars(query.with_for_update() if lock else query))
