from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.geometry import (
    CanonicalExtensionV2,
    CanonicalGeometryError,
    canonical_extension_from_dict,
    canonical_geometry_from_dict,
)
from app.models import ProjectFloor, User
from app.repositories.project_floor_repository import (
    find_project_floor_by_id_and_project,
)
from app.services.layout_version_service import (
    LayoutVersionRecord,
    LayoutVersionServiceError,
    retrieve_current_layout_version,
    save_layout_snapshot_conditionally,
)
from app.services.project_service import ProjectNotFoundError, get_accessible_project


MAXIMUM_DATABASE_ID = 9_223_372_036_854_775_807
ERROR_MESSAGE = "The layout operation could not be completed."


class LayoutServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGE)


def _fail(code: str) -> None:
    raise LayoutServiceError(code)


def _identifier(value: object) -> int:
    if type(value) is not int or not 0 < value <= MAXIMUM_DATABASE_ID:
        _fail("LAYOUT_NOT_FOUND")
    return value


def _role_name(current_user: User) -> str | None:
    role = getattr(current_user, "role", None)
    name = getattr(role, "name", None)
    return name if type(name) is str else None


def _accessible_floor(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int,
    save: bool,
) -> ProjectFloor:
    role_name = _role_name(current_user)
    allowed_roles = {"DESIGNER"} if save else {"ADMIN", "DESIGNER"}
    if role_name not in allowed_roles:
        _fail("AUTHORIZATION_DENIED")

    try:
        get_accessible_project(
            database_session,
            current_user=current_user,
            project_id=project_id,
        )
    except ProjectNotFoundError:
        _fail("LAYOUT_NOT_FOUND")

    project_floor = find_project_floor_by_id_and_project(
        database_session,
        project_floor_id=project_floor_id,
        project_id=project_id,
    )
    if project_floor is None:
        _fail("LAYOUT_NOT_FOUND")
    return project_floor


def _canonical_document(value: object):
    try:
        return canonical_geometry_from_dict(value)
    except (
        CanonicalGeometryError,
        AttributeError,
        OverflowError,
        TypeError,
        ValueError,
    ):
        _fail("INVALID_LAYOUT_GEOMETRY")


def retrieve_accessible_current_layout(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int,
) -> LayoutVersionRecord:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    try:
        _accessible_floor(
            database_session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            save=False,
        )
        try:
            return retrieve_current_layout_version(
                database_session,
                project_id=project_id,
                project_floor_id=project_floor_id,
            )
        except LayoutVersionServiceError as error:
            if error.code == "CURRENT_LAYOUT_NOT_FOUND":
                _fail("LAYOUT_NOT_FOUND")
            _fail("LAYOUT_RETRIEVAL_FAILED")
    except LayoutServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_RETRIEVAL_FAILED")


def save_owned_layout(
    database_session: Session,
    *,
    current_user: User,
    project_id: int,
    project_floor_id: int,
    geometry_payload: object,
    expected_version_number: int | None,
    idempotency_key: str,
    extension_payload: object | None = None,
) -> LayoutVersionRecord:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    try:
        project_floor = _accessible_floor(
            database_session,
            current_user=current_user,
            project_id=project_id,
            project_floor_id=project_floor_id,
            save=True,
        )
        document = _canonical_document(geometry_payload)
        if (
            document.project_id != project_id
            or document.floor.project_floor_id != project_floor_id
            or document.floor.name != project_floor.name
            or document.floor.sort_order != project_floor.sort_order
        ):
            _fail("INVALID_LAYOUT_GEOMETRY")

        extension = None
        if extension_payload is not None:
            try:
                if type(extension_payload) is CanonicalExtensionV2:
                    extension = canonical_extension_from_dict(extension_payload.to_dict(), document)
                else:
                    extension = canonical_extension_from_dict(extension_payload, document)
            except (CanonicalGeometryError, TypeError, ValueError, OverflowError, AttributeError):
                _fail("INVALID_LAYOUT_GEOMETRY")

        try:
            return save_layout_snapshot_conditionally(
                database_session,
                document,
                expected_version_number=expected_version_number,
                idempotency_key=idempotency_key,
                created_by_user_id=current_user.id,
                extension=extension,
            )
        except LayoutVersionServiceError as error:
            if error.code in {
                "INVALID_LAYOUT_DOCUMENT",
                "UNSUPPORTED_SCHEMA_VERSION",
                "LAYOUT_CONTEXT_MISMATCH",
            }:
                _fail("INVALID_LAYOUT_GEOMETRY")
            if error.code == "LAYOUT_CONTEXT_NOT_FOUND":
                _fail("LAYOUT_NOT_FOUND")
            if error.code in {
                "STALE_LAYOUT_VERSION",
                "IDEMPOTENCY_KEY_CONFLICT",
            }:
                _fail(error.code)
            _fail("LAYOUT_SAVE_FAILED")
    except LayoutServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_SAVE_FAILED")
