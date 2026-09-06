from sqlalchemy import select
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import DatasetApproverAssignment, Role, User


def find_current_assignment(
    database_session: Session,
    *,
    lock: bool = False,
) -> DatasetApproverAssignment | None:
    query = (
        select(DatasetApproverAssignment)
        .where(DatasetApproverAssignment.active_marker.is_(True))
        .options(raiseload("*"))
    )
    if lock:
        query = query.with_for_update()
    return database_session.scalar(query)


def list_assignments(
    database_session: Session,
) -> tuple[DatasetApproverAssignment, ...]:
    return tuple(database_session.scalars(
        select(DatasetApproverAssignment)
        .options(raiseload("*"))
        .order_by(
            DatasetApproverAssignment.active_from.desc(),
            DatasetApproverAssignment.id.desc(),
        )
        .execution_options(populate_existing=True)
    ).all())


def find_assignment(
    database_session: Session,
    *,
    assignment_id: int,
    lock: bool = False,
) -> DatasetApproverAssignment | None:
    query = (
        select(DatasetApproverAssignment)
        .where(DatasetApproverAssignment.id == assignment_id)
        .options(raiseload("*"))
    )
    if lock:
        query = query.with_for_update()
    return database_session.scalar(query)


def find_eligible_assignee(
    database_session: Session,
    *,
    user_id: int,
) -> User | None:
    return database_session.scalar(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(User.id == user_id, Role.name.in_(("ADMIN", "DESIGNER")))
        .options(load_only(User.id), raiseload("*"))
    )


def add_and_flush(database_session: Session, record):
    database_session.add(record)
    database_session.flush()
    return record
