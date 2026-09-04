from pathlib import Path

from sqlalchemy.orm import Session

from app.models import FloorPlan, User
from app.repositories.floor_plan_repository import list_floor_plans_by_project
from app.repositories.project_floor_repository import (
    find_project_floor_by_id_and_project,
)
from app.services.floor_plan_storage import store_floor_plan_upload
from app.services.project_service import get_accessible_project


class ProjectFloorNotFoundError(RuntimeError):
    """Raised when a project floor is absent or does not belong to a project."""


def list_accessible_floor_plans(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int | None = None,
) -> list[FloorPlan]:
    get_accessible_project(
        database_session,
        current_user=current_user,
        project_id=project_id,
    )
    if project_floor_id is not None:
        project_floor = find_project_floor_by_id_and_project(
            database_session,
            project_floor_id=project_floor_id,
            project_id=project_id,
        )
        if project_floor is None:
            raise ProjectFloorNotFoundError
    return list_floor_plans_by_project(
        database_session,
        project_id=project_id,
        project_floor_id=project_floor_id,
    )


def upload_floor_plan(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int,
    filename: str,
    declared_mime_type: str,
    content: bytes,
    upload_directory: Path,
    max_file_size_bytes: int,
) -> FloorPlan:
    get_accessible_project(
        database_session,
        current_user=current_user,
        project_id=project_id,
    )
    project_floor = find_project_floor_by_id_and_project(
        database_session,
        project_floor_id=project_floor_id,
        project_id=project_id,
    )
    if project_floor is None:
        raise ProjectFloorNotFoundError

    return store_floor_plan_upload(
        database_session,
        project_floor_id=project_floor.id,
        filename=filename,
        declared_mime_type=declared_mime_type,
        content=content,
        upload_directory=upload_directory,
        max_file_size_bytes=max_file_size_bytes,
    )
