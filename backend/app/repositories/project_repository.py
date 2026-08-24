from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project


def add_project(database_session: Session, project: Project) -> Project:
    database_session.add(project)
    database_session.flush()
    return project


def list_projects_by_owner(
    database_session: Session,
    *,
    owner_id: int,
) -> list[Project]:
    return list(
        database_session.scalars(
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
        ).all()
    )


def list_all_projects(database_session: Session) -> list[Project]:
    return list(
        database_session.scalars(
            select(Project).order_by(Project.updated_at.desc(), Project.id.desc())
        ).all()
    )
