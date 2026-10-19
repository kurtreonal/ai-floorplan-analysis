from sqlalchemy import select
from app.models import Material, Project, ProjectPriceVersion


def materials(session, ids=None, lock=False):
    query = select(Material).order_by(Material.id).execution_options(populate_existing=True)
    if ids is not None:
        query = query.where(Material.id.in_(ids))
    else:
        query = query.limit(5000)
    return list(session.scalars(query.with_for_update() if lock else query))


def lock_project(session, project_id):
    return session.scalar(select(Project).where(Project.id == project_id).with_for_update()
        .execution_options(populate_existing=True))


def versions(session, project_id):
    return list(session.scalars(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id)
        .order_by(ProjectPriceVersion.version_number.desc()).limit(100)))


def latest_version(session, project_id, lock=False):
    query = select(ProjectPriceVersion.version_number).where(ProjectPriceVersion.project_id == project_id).order_by(
        ProjectPriceVersion.version_number.desc()).limit(1)
    return session.scalar(query.with_for_update() if lock else query) or 0


def find(session, project_id, version_id):
    return session.scalar(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id,
        ProjectPriceVersion.id == version_id))


def retry(session, project_id, request_id):
    return session.scalar(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id,
        ProjectPriceVersion.request_id == request_id).with_for_update().execution_options(populate_existing=True))


def append(session, **values):
    record = ProjectPriceVersion(**values)
    session.add(record)
    session.flush()
    return record
