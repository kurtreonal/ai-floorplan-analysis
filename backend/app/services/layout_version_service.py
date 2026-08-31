from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.geometry import (
    CanonicalGeometryDocument,
    CanonicalGeometryError,
    canonical_geometry_from_dict,
)
from app.models import LayoutVersion
from app.repositories.layout_version_repository import (
    add_layout_version,
    clear_current_marker,
    find_current_layout_version,
    find_floor_plan_for_floor,
    find_layout_version,
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
) -> LayoutVersionRecord:
    geometry = _reconstruct(layout_version.geometry_document)
    if (
        geometry.schema_version != layout_version.schema_version
        or geometry.project_id != layout_version.project_id
        or geometry.floor.project_floor_id != layout_version.project_floor_id
        or geometry.floor_plan_id != layout_version.floor_plan_id
    ):
        _fail("INVALID_STORED_GEOMETRY")
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


def save_layout_snapshot(
    database_session: Session,
    document: CanonicalGeometryDocument,
) -> LayoutVersionRecord:
    document, serialized = _validated_document(document)
    try:
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
        record = _record(layout_version)
        database_session.commit()
        return record
    except LayoutVersionServiceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
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
