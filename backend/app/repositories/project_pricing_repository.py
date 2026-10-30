from sqlalchemy import select
from sqlalchemy.orm import defer
from app.models import Material, Project, ProjectPriceVersion
from app.models.account_security import AdminActivity


def active_import():
    return ~select(AdminActivity.id).where(AdminActivity.target_type == 'price_import',
        AdminActivity.target_id == ProjectPriceVersion.id,
        AdminActivity.action == 'CLIENT_PRICING_REMOVED').exists()


def removed_ids(session, project_id):
    return set(session.scalars(select(ProjectPriceVersion.id).where(ProjectPriceVersion.project_id == project_id, ~active_import())))


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
    return list(session.scalars(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id, active_import())
        .order_by(ProjectPriceVersion.version_number.desc()).limit(100)))


def latest_version(session, project_id, lock=False):
    query = select(ProjectPriceVersion.version_number).where(ProjectPriceVersion.project_id == project_id).order_by(
        ProjectPriceVersion.version_number.desc()).limit(1)
    return session.scalar(query.with_for_update() if lock else query) or 0


def current(session, project_id):
    return session.scalar(select(ProjectPriceVersion).options(defer(ProjectPriceVersion.source_bytes))
        .where(ProjectPriceVersion.project_id == project_id, active_import(),
            (ProjectPriceVersion.document['usage'].as_string().is_(None)) |
            (ProjectPriceVersion.document['usage'].as_string() != 'item_selection'))
        .order_by(ProjectPriceVersion.version_number.desc()).limit(1))


def find(session, project_id, version_id):
    return session.scalar(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id,
        ProjectPriceVersion.id == version_id))


def latest_automatic(session,project_id,*,for_floor=False,floor_id=None):
    query=(select(ProjectPriceVersion).options(defer(ProjectPriceVersion.source_bytes))
        .where(ProjectPriceVersion.project_id==project_id, active_import(),
            ProjectPriceVersion.document['matching_method'].as_string()=='automatic_client_specification')
        .order_by(ProjectPriceVersion.version_number.desc()).limit(1))
    if for_floor:
        scope=ProjectPriceVersion.document['application']
        query=query.where((scope['scope'].as_string()=='project') | (scope['floor_id'].as_integer()==floor_id))
    return session.scalar(query)


def retry(session, project_id, request_id):
    return session.scalar(select(ProjectPriceVersion).where(ProjectPriceVersion.project_id == project_id,
        ProjectPriceVersion.request_id == request_id).with_for_update().execution_options(populate_existing=True))


def append(session, **values):
    record = ProjectPriceVersion(**values)
    session.add(record)
    session.flush()
    return record
