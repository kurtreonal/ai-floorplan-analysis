from sqlalchemy import select
from app.models import Material


def catalog(session):
    return list(session.scalars(select(Material).order_by(Material.code).limit(5000)))


def by_code(session, code, *, lock=False):
    query = select(Material).where(Material.code == code)
    return session.scalar(query.with_for_update() if lock else query)


def create(session, values):
    row = Material(**values)
    session.add(row)
    session.flush()
    return row
