from sqlalchemy import select
from app.models import Estimate, EstimateItem, EstimateSource, Material, ProjectFloor


def find_estimate(session, project_id, estimate_id):
    return session.scalar(select(Estimate).where(Estimate.project_id == project_id, Estimate.id == estimate_id))


def list_estimates(session, project_id):
    return list(session.scalars(select(Estimate).where(Estimate.project_id == project_id)
        .order_by(Estimate.version_number.desc()).limit(100)))


def items(session, estimate_id):
    return list(session.scalars(select(EstimateItem).where(EstimateItem.estimate_id == estimate_id).order_by(EstimateItem.line_number)))


def source(session, estimate_id):
    return session.get(EstimateSource, estimate_id)


def retry(session, project_id, request_id):
    return session.scalar(select(EstimateSource).where(EstimateSource.project_id == project_id,
        EstimateSource.request_id == request_id).with_for_update())


def next_version(session, project_id):
    latest = session.scalar(select(Estimate.version_number).where(Estimate.project_id == project_id)
        .order_by(Estimate.version_number.desc()).limit(1).with_for_update())
    return (latest or 0) + 1


def catalog(session):
    return list(session.scalars(select(Material).where(Material.is_active.is_(True)).order_by(Material.code).limit(2000)))


def floor_ids(session, project_id):
    return list(session.scalars(select(ProjectFloor.id).where(ProjectFloor.project_id == project_id).order_by(ProjectFloor.id)))


def save(session, header, lines, provenance):
    estimate = Estimate(**header)
    session.add(estimate)
    session.flush()
    session.add_all([EstimateItem(estimate_id=estimate.id, line_number=i, **line) for i, line in enumerate(lines, 1)])
    session.add(EstimateSource(estimate_id=estimate.id, project_id=estimate.project_id, **provenance))
    session.flush()
    return estimate
