from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.geometry import (
    CanonicalExtensionV2,
    CanonicalGeometryDocument,
    CanonicalGeometryError,
    canonical_extension_from_dict,
    canonical_geometry_from_dict,
)
from app.services.canonical_extension_storage import (
    delete_canonical_extension,
    retrieve_canonical_extension,
    save_canonical_extension,
)
from app.models import LayoutSaveRequest, LayoutVersion
from app.repositories.layout_version_repository import (
    add_layout_save_request,
    add_layout_version,
    clear_current_marker,
    find_current_layout_version,
    find_floor_plan_for_floor,
    find_layout_save_request,
    find_layout_version,
    find_layout_version_by_id,
    list_current_versions,
    list_layout_versions,
    lock_project_floor,
    maximum_version_number,
    set_current_marker,
)


SCHEMA_VERSION = 1
MAXIMUM_IDENTIFIER = 9_007_199_254_740_991
MAXIMUM_VERSION_NUMBER = 2_147_483_647
ERROR_MESSAGE = "The layout snapshot operation could not be completed."


class LayoutVersionServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGE)


def _fail(code: str) -> None:
    raise LayoutVersionServiceError(code)


@dataclass(frozen=True)
class LayoutVersionRecord:
    id: int
    project_id: int
    project_floor_id: int
    floor_plan_id: int
    version_number: int
    schema_version: int
    is_current: bool
    created_at: datetime
    geometry: CanonicalGeometryDocument
    extension: CanonicalExtensionV2 | None = None


@dataclass(frozen=True)
class LayoutVersionMetadata:
    id: int
    project_id: int
    project_floor_id: int
    floor_plan_id: int
    version_number: int
    schema_version: int
    is_current: bool
    created_at: datetime


def _identifier(value: object) -> int:
    if type(value) is not int or not 0 < value <= MAXIMUM_IDENTIFIER:
        _fail("INVALID_IDENTIFIER")
    return value


def _version_number(value: object) -> int:
    if type(value) is not int or not 0 < value <= MAXIMUM_VERSION_NUMBER:
        _fail("INVALID_VERSION_NUMBER")
    return value


def _reconstruct(value: object) -> CanonicalGeometryDocument:
    try:
        return canonical_geometry_from_dict(value)
    except (
        CanonicalGeometryError,
        AttributeError,
        OverflowError,
        TypeError,
        ValueError,
    ):
        _fail("INVALID_STORED_GEOMETRY")


def _record(
    layout_version: LayoutVersion,
    *,
    current_override: bool | None = None,
    extension: CanonicalExtensionV2 | None = None,
) -> LayoutVersionRecord:
    geometry = _reconstruct(layout_version.geometry_document)
    if (
        geometry.schema_version != layout_version.schema_version
        or geometry.project_id != layout_version.project_id
        or geometry.floor.project_floor_id != layout_version.project_floor_id
        or geometry.floor_plan_id != layout_version.floor_plan_id
    ):
        _fail("INVALID_STORED_GEOMETRY")
    if extension is None:
        extension = retrieve_canonical_extension(layout_version.id, geometry)
    return LayoutVersionRecord(
        id=layout_version.id,
        project_id=layout_version.project_id,
        project_floor_id=layout_version.project_floor_id,
        floor_plan_id=layout_version.floor_plan_id,
        version_number=layout_version.version_number,
        schema_version=layout_version.schema_version,
        is_current=(
            layout_version.is_current is True
            if current_override is None
            else current_override
        ),
        created_at=layout_version.created_at,
        geometry=geometry,
        extension=extension,
    )


def _metadata(layout_version: LayoutVersion) -> LayoutVersionMetadata:
    return LayoutVersionMetadata(
        id=layout_version.id,
        project_id=layout_version.project_id,
        project_floor_id=layout_version.project_floor_id,
        floor_plan_id=layout_version.floor_plan_id,
        version_number=layout_version.version_number,
        schema_version=layout_version.schema_version,
        is_current=layout_version.is_current is True,
        created_at=layout_version.created_at,
    )


def _validated_document(value: object) -> tuple[CanonicalGeometryDocument, dict[str, object]]:
    if type(value) is not CanonicalGeometryDocument:
        _fail("INVALID_LAYOUT_DOCUMENT")
    try:
        serialized = value.to_dict()
        document = canonical_geometry_from_dict(serialized)
    except (
        CanonicalGeometryError,
        AttributeError,
        OverflowError,
        TypeError,
        ValueError,
    ):
        _fail("INVALID_LAYOUT_DOCUMENT")
    if document.schema_version != SCHEMA_VERSION:
        _fail("UNSUPPORTED_SCHEMA_VERSION")
    return document, serialized


def _request_key(value: object) -> str:
    if type(value) is not str or len(value) != 36:
        _fail("INVALID_IDEMPOTENCY_KEY")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        _fail("INVALID_IDEMPOTENCY_KEY")
    if parsed.version != 4 or str(parsed) != value:
        _fail("INVALID_IDEMPOTENCY_KEY")
    return value


def _expected_version(value: object) -> int | None:
    if value is None:
        return None
    return _version_number(value)


def _geometry_hash(serialized: dict[str, object]) -> str:
    encoded = json.dumps(
        serialized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _locked_context(
    database_session: Session,
    document: CanonicalGeometryDocument,
):
    project_floor = lock_project_floor(
        database_session,
        project_floor_id=document.floor.project_floor_id,
    )
    if project_floor is None:
        _fail("LAYOUT_CONTEXT_NOT_FOUND")
    if (
        project_floor.project_id != document.project_id
        or project_floor.name != document.floor.name
        or project_floor.sort_order != document.floor.sort_order
    ):
        _fail("LAYOUT_CONTEXT_MISMATCH")
    floor_plan = find_floor_plan_for_floor(
        database_session,
        floor_plan_id=document.floor_plan_id,
        project_floor_id=document.floor.project_floor_id,
    )
    if floor_plan is None:
        _fail("LAYOUT_CONTEXT_MISMATCH")
    current = list_current_versions(
        database_session,
        project_floor_id=document.floor.project_floor_id,
    )
    if len(current) > 1:
        _fail("CURRENT_MARKER_INTEGRITY_FAILED")
    maximum = maximum_version_number(
        database_session,
        project_floor_id=document.floor.project_floor_id,
    )
    return current, maximum


def _insert_snapshot(
    database_session: Session,
    *,
    document: CanonicalGeometryDocument,
    serialized: dict[str, object],
    maximum: int | None,
) -> LayoutVersion:
    if maximum is not None and maximum >= MAXIMUM_VERSION_NUMBER:
        _fail("VERSION_NUMBER_OVERFLOW")
    next_version = 1 if maximum is None else maximum + 1
    clear_current_marker(
        database_session,
        project_floor_id=document.floor.project_floor_id,
    )
    layout_version = LayoutVersion(
        project_id=document.project_id,
        project_floor_id=document.floor.project_floor_id,
        floor_plan_id=document.floor_plan_id,
        version_number=next_version,
        schema_version=SCHEMA_VERSION,
        geometry_document=serialized,
        is_current=True,
    )
    add_layout_version(database_session, layout_version)
    return layout_version


def save_layout_snapshot(
    database_session: Session,
    document: CanonicalGeometryDocument,
) -> LayoutVersionRecord:
    document, serialized = _validated_document(document)
    try:
        _current, maximum = _locked_context(database_session, document)
        layout_version = _insert_snapshot(
            database_session,
            document=document,
            serialized=serialized,
            maximum=maximum,
        )
        record = _record(layout_version)
        database_session.commit()
        return record
    except LayoutVersionServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_PERSISTENCE_FAILED")


def save_layout_snapshot_conditionally(
    database_session: Session,
    document: CanonicalGeometryDocument,
    *,
    expected_version_number: int | None,
    idempotency_key: str,
    created_by_user_id: int,
    extension: CanonicalExtensionV2 | None = None,
) -> LayoutVersionRecord:
    document, serialized = _validated_document(document)
    if extension is not None:
        if type(extension) is not CanonicalExtensionV2:
            try:
                extension = canonical_extension_from_dict(extension, document)
            except Exception:
                _fail("INVALID_LAYOUT_DOCUMENT")
        else:
            try:
                canonical_extension_from_dict(extension.to_dict(), document)
            except Exception:
                _fail("INVALID_LAYOUT_DOCUMENT")

    expected_version_number = _expected_version(expected_version_number)
    idempotency_key = _request_key(idempotency_key)
    created_by_user_id = _identifier(created_by_user_id)
    geometry_sha256 = _geometry_hash(serialized)
    try:
        current, maximum = _locked_context(database_session, document)
        previous = find_layout_save_request(
            database_session,
            project_floor_id=document.floor.project_floor_id,
            idempotency_key=idempotency_key,
        )
        if previous is not None:
            if (
                previous.expected_version_number != expected_version_number
                or previous.geometry_sha256 != geometry_sha256
                or previous.created_by_user_id != created_by_user_id
            ):
                _fail("IDEMPOTENCY_KEY_CONFLICT")
            layout_version = find_layout_version_by_id(
                database_session,
                layout_version_id=previous.layout_version_id,
            )
            if layout_version is None:
                _fail("IDEMPOTENCY_RECORD_INTEGRITY_FAILED")
            record = _record(layout_version, current_override=True, extension=extension)
            database_session.rollback()
            return record

        current_version = current[0].version_number if current else None
        if expected_version_number != current_version:
            _fail("STALE_LAYOUT_VERSION")
        layout_version = _insert_snapshot(
            database_session,
            document=document,
            serialized=serialized,
            maximum=maximum,
        )
        if extension is not None:
            save_canonical_extension(layout_version.id, extension)
        add_layout_save_request(
            database_session,
            LayoutSaveRequest(
                project_floor_id=document.floor.project_floor_id,
                idempotency_key=idempotency_key,
                expected_version_number=expected_version_number,
                geometry_sha256=geometry_sha256,
                created_by_user_id=created_by_user_id,
                layout_version_id=layout_version.id,
            ),
        )
        record = _record(layout_version, extension=extension)
        database_session.commit()
        return record
    except LayoutVersionServiceError:
        if extension is not None and "layout_version" in locals() and hasattr(layout_version, "id"):
            delete_canonical_extension(layout_version.id)
        database_session.rollback()
        raise
    except SQLAlchemyError:
        if extension is not None and "layout_version" in locals() and hasattr(layout_version, "id"):
            delete_canonical_extension(layout_version.id)
        database_session.rollback()
        _fail("LAYOUT_PERSISTENCE_FAILED")


def retrieve_layout_version(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
    version_number: int,
) -> LayoutVersionRecord:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    version_number = _version_number(version_number)
    try:
        layout_version = find_layout_version(
            database_session,
            project_id=project_id,
            project_floor_id=project_floor_id,
            version_number=version_number,
        )
        if layout_version is None:
            _fail("LAYOUT_VERSION_NOT_FOUND")
        return _record(layout_version)
    except LayoutVersionServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_RETRIEVAL_FAILED")


def retrieve_current_layout_version(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
) -> LayoutVersionRecord:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    try:
        current = find_current_layout_version(
            database_session,
            project_id=project_id,
            project_floor_id=project_floor_id,
        )
        if len(current) != 1:
            _fail(
                "CURRENT_LAYOUT_NOT_FOUND"
                if not current
                else "CURRENT_MARKER_INTEGRITY_FAILED"
            )
        return _record(current[0])
    except LayoutVersionServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_RETRIEVAL_FAILED")


def list_layout_version_history(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
) -> tuple[LayoutVersionMetadata, ...]:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    try:
        return tuple(
            _metadata(layout_version)
            for layout_version in list_layout_versions(
                database_session,
                project_id=project_id,
                project_floor_id=project_floor_id,
            )
        )
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_RETRIEVAL_FAILED")


def mark_layout_version_current(
    database_session: Session,
    *,
    project_id: int,
    project_floor_id: int,
    version_number: int,
) -> LayoutVersionRecord:
    project_id = _identifier(project_id)
    project_floor_id = _identifier(project_floor_id)
    version_number = _version_number(version_number)
    try:
        project_floor = lock_project_floor(
            database_session,
            project_floor_id=project_floor_id,
        )
        if project_floor is None or project_floor.project_id != project_id:
            _fail("LAYOUT_VERSION_NOT_FOUND")
        target = find_layout_version(
            database_session,
            project_id=project_id,
            project_floor_id=project_floor_id,
            version_number=version_number,
        )
        if target is None:
            _fail("LAYOUT_VERSION_NOT_FOUND")
        current = list_current_versions(
            database_session,
            project_floor_id=project_floor_id,
        )
        if len(current) > 1:
            _fail("CURRENT_MARKER_INTEGRITY_FAILED")
        if target.is_current is not True:
            clear_current_marker(
                database_session,
                project_floor_id=project_floor_id,
            )
            set_current_marker(
                database_session,
                layout_version_id=target.id,
            )
        record = _record(target, current_override=True)
        database_session.commit()
        return record
    except LayoutVersionServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        _fail("LAYOUT_PERSISTENCE_FAILED")
