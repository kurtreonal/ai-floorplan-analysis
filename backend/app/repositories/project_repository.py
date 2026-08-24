from sqlalchemy import select
from sqlalchemy.orm import Session, raiseload

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


def find_project_by_id(
    database_session: Session,
    *,
    project_id: int,
) -> Project | None:
    return database_session.scalar(
        select(Project)
        .options(raiseload("*"))
        .where(Project.id == project_id)
        .execution_options(populate_existing=True)
    )


def find_project_by_id_and_owner(
    database_session: Session,
    *,
    project_id: int,
    owner_id: int,
) -> Project | None:
    return database_session.scalar(
        select(Project)
        .options(raiseload("*"))
        .where(
            Project.id == project_id,
            Project.owner_id == owner_id,
        )
        .execution_options(populate_existing=True)
    )
