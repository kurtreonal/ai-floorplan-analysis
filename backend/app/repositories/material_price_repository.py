from sqlalchemy import select

from app.models import Material, MaterialPrice


def lock_material(session, material_id):
    return session.scalar(select(Material).where(Material.id == material_id).with_for_update())


def price_history(session, material_id):
    return list(session.scalars(select(MaterialPrice).where(MaterialPrice.material_id == material_id)
                               .order_by(MaterialPrice.version_number)))


def latest_price(session, material_id, *, at, lock=False):
    query = select(MaterialPrice).where(MaterialPrice.material_id == material_id,
        MaterialPrice.effective_at <= at).order_by(MaterialPrice.effective_at.desc(), MaterialPrice.version_number.desc()).limit(1)
    return session.scalar(query.with_for_update() if lock else query)


def last_revision(session, material_id):
    return session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == material_id)
        .order_by(MaterialPrice.version_number.desc()).limit(1).with_for_update())


def append_price(session, **values):
    record = MaterialPrice(**values)
    session.add(record)
    session.flush()
    return record
