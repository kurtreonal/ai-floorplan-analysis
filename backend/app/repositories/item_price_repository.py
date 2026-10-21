from sqlalchemy import select
from app.models import ItemPriceAssignment


def current(session, project_id, *, lock=False):
    query=(select(ItemPriceAssignment).where(ItemPriceAssignment.project_id == project_id)
        .order_by(ItemPriceAssignment.version_number.desc()).limit(1).execution_options(populate_existing=True))
    return session.scalar(query.with_for_update() if lock else query)


def retry(session, project_id, request_id):
    return session.scalar(select(ItemPriceAssignment).where(ItemPriceAssignment.project_id == project_id,
        ItemPriceAssignment.request_id == request_id).with_for_update())


def append(session, **values):
    value = ItemPriceAssignment(**values)
    session.add(value)
    session.flush()
    return value
