from sqlalchemy.orm import Session

from app.models import Project


def add_project(database_session: Session, project: Project) -> Project:
    database_session.add(project)
    database_session.flush()
    return project
