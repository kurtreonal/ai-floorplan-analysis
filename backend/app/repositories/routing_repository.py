from sqlalchemy import select
from app.models import Project, ProjectFloor, LayoutVersion
from app.models.generated_route import GeneratedRouteVersion


def latest_route(session, project_id, lock=False):
    query = select(GeneratedRouteVersion).where(GeneratedRouteVersion.project_id == project_id).order_by(GeneratedRouteVersion.version_number.desc()).limit(1)
    return session.scalar(query.with_for_update() if lock else query)


def current_layout_ids(session, project_id, floor_ids, lock=False):
    query = select(LayoutVersion).where(
        LayoutVersion.project_id == project_id, LayoutVersion.project_floor_id.in_(floor_ids),
        LayoutVersion.is_current.is_(True))
    return {str(row.project_floor_id): row.id for row in session.scalars(query.with_for_update() if lock else query)}


def lock_context(session, project_id, floor_ids):
    session.execute(select(Project).where(Project.id == project_id).with_for_update()).scalar_one()
    list(session.scalars(select(ProjectFloor).where(ProjectFloor.project_id == project_id,
        ProjectFloor.id.in_(floor_ids)).order_by(ProjectFloor.id).with_for_update()))


def append_route(session, **values):
    record = GeneratedRouteVersion(**values)
    session.add(record)
    session.flush()
    return record
