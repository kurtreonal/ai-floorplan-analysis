from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DecimalException

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.geometry.coordinates import CanonicalCoordinateSystem, CanonicalPoint
from app.geometry.walls import (
    CanonicalWall,
    CanonicalWallCandidate,
    NormalizedWallGeometry,
    RawPixelPoint,
    RawPixelWall,
)
from app.models import Wall
from app.repositories.wall_repository import (
    add_detected_walls,
    delete_detected_walls,
    find_processing_job,
    has_verified_walls,
    list_walls,
    lock_floor_plan,
)
from app.services.processing_job_service import FLOOR_PLAN_ANALYSIS_JOB_TYPE


ERROR_MESSAGES = {
    "INVALID_FLOOR_PLAN_ID": "The floor-plan identifier is invalid.",
    "INVALID_PROCESSING_JOB_ID": "The processing-job identifier is invalid.",
    "INVALID_GEOMETRY": "The normalized wall geometry is invalid.",
    "TRUNCATED_GEOMETRY": "Truncated wall geometry cannot be persisted.",
    "FLOOR_PLAN_NOT_FOUND": "The floor plan does not exist.",
    "PROCESSING_JOB_NOT_FOUND": "The processing job does not exist.",
    "PROCESSING_JOB_FLOOR_PLAN_MISMATCH": (
        "The processing job does not belong to the floor plan."
    ),
    "INVALID_PROCESSING_JOB_TYPE": "The processing-job type is invalid.",
    "INVALID_PROCESSING_JOB_STATUS": "The processing job is not processing.",
    "VERIFIED_WALLS_PROTECTED": "Verified walls cannot be replaced by machine output.",
    "WALL_PERSISTENCE_FAILED": "Wall geometry could not be persisted.",
    "WALL_RETRIEVAL_FAILED": "Wall geometry could not be retrieved.",
}

SCALE_QUANTUM = Decimal("0.000000001")
RAW_LENGTH_QUANTUM = Decimal("0.000001")
METRIC_QUANTUM = Decimal("0.000000001")
ANGLE_QUANTUM = Decimal("0.000001")
MAX_INTEGER = 2_147_483_647
MAX_SCALE_OR_METRIC = Decimal("99999999999.999999999")
MAX_RAW_LENGTH = Decimal("99999999999999.999999")


class WallPersistenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        self.message = ERROR_MESSAGES[code]
        super().__init__(self.message)


def _error(code: str) -> WallPersistenceError:
    return WallPersistenceError(code)


@dataclass(frozen=True)
class PersistedWallRecord:
    id: int
    floor_plan_id: int
    processing_job_id: int
    candidate_id: int
    status: str
    pixels_per_meter: Decimal
    raw_start_x: int
    raw_start_y: int
    raw_end_x: int
    raw_end_y: int
    raw_length_pixels: Decimal
    canonical_start_x: Decimal
    canonical_start_y: Decimal
    canonical_end_x: Decimal
    canonical_end_y: Decimal
    canonical_length_meters: Decimal
    angle_degrees: Decimal
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "processing_job_id": self.processing_job_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "pixels_per_meter": float(self.pixels_per_meter),
            "raw_start_x": self.raw_start_x,
            "raw_start_y": self.raw_start_y,
            "raw_end_x": self.raw_end_x,
            "raw_end_y": self.raw_end_y,
            "raw_length_pixels": float(self.raw_length_pixels),
            "canonical_start_x": float(self.canonical_start_x),
            "canonical_start_y": float(self.canonical_start_y),
            "canonical_end_x": float(self.canonical_end_x),
            "canonical_end_y": float(self.canonical_end_y),
            "canonical_length_meters": float(self.canonical_length_meters),
            "angle_degrees": float(self.angle_degrees),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True)
class _PreparedWall:
    candidate_id: int
    pixels_per_meter: Decimal
    raw_start_x: int
    raw_start_y: int
    raw_end_x: int
    raw_end_y: int
    raw_length_pixels: Decimal
    canonical_start_x: Decimal
    canonical_start_y: Decimal
    canonical_end_x: Decimal
    canonical_end_y: Decimal
    canonical_length_meters: Decimal
    angle_degrees: Decimal


def _positive_identifier(value: object, code: str) -> int:
    if type(value) is not int or value <= 0:
        raise _error(code)
    return value


def _integer_coordinate(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise _error("INVALID_GEOMETRY")
    return value


def _decimal_value(
    value: object,
    *,
    quantum: Decimal,
    maximum: Decimal,
    positive: bool = False,
) -> Decimal:
    if type(value) not in (int, float):
        raise _error("INVALID_GEOMETRY")
    try:
        numeric = float(value)
        decimal_value = Decimal(str(value))
        quantized = decimal_value.quantize(quantum)
    except (DecimalException, OverflowError, TypeError, ValueError):
        raise _error("INVALID_GEOMETRY") from None
    if (
        not math.isfinite(numeric)
        or not quantized.is_finite()
        or quantized > maximum
        or (quantized <= 0 if positive else quantized < 0)
    ):
        raise _error("INVALID_GEOMETRY")
    return quantized


def _validate_coordinate_system(
    value: object,
) -> tuple[Decimal, float, int, int]:
    if type(value) is not CanonicalCoordinateSystem:
        raise _error("INVALID_GEOMETRY")
    if (
        value.unit != "meter"
        or value.origin != "image_top_left"
        or value.x_direction != "right"
        or value.y_direction != "down"
        or type(value.image_width_pixels) is not int
        or type(value.image_height_pixels) is not int
        or value.image_width_pixels <= 0
        or value.image_height_pixels <= 0
    ):
        raise _error("INVALID_GEOMETRY")
    scale = _decimal_value(
        value.pixels_per_meter,
        quantum=SCALE_QUANTUM,
        maximum=MAX_SCALE_OR_METRIC,
        positive=True,
    )
    scale_float = float(value.pixels_per_meter)
    width = _decimal_value(
        value.width_meters,
        quantum=METRIC_QUANTUM,
        maximum=MAX_SCALE_OR_METRIC,
    )
    height = _decimal_value(
        value.height_meters,
        quantum=METRIC_QUANTUM,
        maximum=MAX_SCALE_OR_METRIC,
    )
    expected_width = _decimal_value(
        value.image_width_pixels / scale_float,
        quantum=SCALE_QUANTUM,
        maximum=MAX_SCALE_OR_METRIC,
    )
    expected_height = _decimal_value(
        value.image_height_pixels / scale_float,
        quantum=SCALE_QUANTUM,
        maximum=MAX_SCALE_OR_METRIC,
    )
    if width != expected_width or height != expected_height:
        raise _error("INVALID_GEOMETRY")
    return scale, scale_float, value.image_width_pixels, value.image_height_pixels


def _validate_point(value: object, *, raw: bool) -> tuple[int, int] | tuple[Decimal, Decimal]:
    if raw:
        if type(value) is not RawPixelPoint:
            raise _error("INVALID_GEOMETRY")
        return _integer_coordinate(value.x), _integer_coordinate(value.y)
    if type(value) is not CanonicalPoint:
        raise _error("INVALID_GEOMETRY")
    return (
        _decimal_value(
            value.x,
            quantum=METRIC_QUANTUM,
            maximum=MAX_SCALE_OR_METRIC,
        ),
        _decimal_value(
            value.y,
            quantum=METRIC_QUANTUM,
            maximum=MAX_SCALE_OR_METRIC,
        ),
    )


def _prepare_geometry(geometry: object) -> tuple[_PreparedWall, ...]:
    if type(geometry) is not NormalizedWallGeometry:
        raise _error("INVALID_GEOMETRY")
    if type(geometry.source_truncated) is not bool:
        raise _error("INVALID_GEOMETRY")
    if geometry.source_truncated:
        raise _error("TRUNCATED_GEOMETRY")
    if not isinstance(geometry.walls, tuple):
        raise _error("INVALID_GEOMETRY")
    scale, scale_float, image_width, image_height = _validate_coordinate_system(
        geometry.coordinate_system
    )
    prepared = []
    previous_sort_key = None
    seen_segments = set()
    for expected_id, candidate in enumerate(geometry.walls, start=1):
        if (
            type(candidate) is not CanonicalWallCandidate
            or type(candidate.candidate_id) is not int
            or candidate.candidate_id != expected_id
            or candidate.candidate_id > MAX_INTEGER
            or type(candidate.raw_pixels) is not RawPixelWall
            or type(candidate.canonical) is not CanonicalWall
        ):
            raise _error("INVALID_GEOMETRY")
        raw_start_x, raw_start_y = _validate_point(
            candidate.raw_pixels.start,
            raw=True,
        )
        raw_end_x, raw_end_y = _validate_point(candidate.raw_pixels.end, raw=True)
        if (
            raw_start_x >= image_width
            or raw_end_x >= image_width
            or raw_start_y >= image_height
            or raw_end_y >= image_height
        ):
            raise _error("INVALID_GEOMETRY")
        sort_key = (raw_start_y, raw_start_x, raw_end_y, raw_end_x)
        segment = (raw_start_x, raw_start_y, raw_end_x, raw_end_y)
        if (
            (previous_sort_key is not None and sort_key < previous_sort_key)
            or segment in seen_segments
        ):
            raise _error("INVALID_GEOMETRY")
        previous_sort_key = sort_key
        seen_segments.add(segment)
        canonical_start_x, canonical_start_y = _validate_point(
            candidate.canonical.start,
            raw=False,
        )
        canonical_end_x, canonical_end_y = _validate_point(
            candidate.canonical.end,
            raw=False,
        )
        raw_length = _decimal_value(
            candidate.raw_pixels.length_pixels,
            quantum=RAW_LENGTH_QUANTUM,
            maximum=MAX_RAW_LENGTH,
        )
        canonical_length = _decimal_value(
            candidate.canonical.length_meters,
            quantum=METRIC_QUANTUM,
            maximum=MAX_SCALE_OR_METRIC,
        )
        raw_angle = _decimal_value(
            candidate.raw_pixels.angle_degrees,
            quantum=ANGLE_QUANTUM,
            maximum=Decimal("179.999999"),
        )
        canonical_angle = _decimal_value(
            candidate.canonical.angle_degrees,
            quantum=ANGLE_QUANTUM,
            maximum=Decimal("179.999999"),
        )
        if raw_angle != canonical_angle:
            raise _error("INVALID_GEOMETRY")
        expected_canonical = (
            _decimal_value(
                raw_start_x / scale_float,
                quantum=METRIC_QUANTUM,
                maximum=MAX_SCALE_OR_METRIC,
            ),
            _decimal_value(
                raw_start_y / scale_float,
                quantum=METRIC_QUANTUM,
                maximum=MAX_SCALE_OR_METRIC,
            ),
            _decimal_value(
                raw_end_x / scale_float,
                quantum=METRIC_QUANTUM,
                maximum=MAX_SCALE_OR_METRIC,
            ),
            _decimal_value(
                raw_end_y / scale_float,
                quantum=METRIC_QUANTUM,
                maximum=MAX_SCALE_OR_METRIC,
            ),
        )
        if (
            canonical_start_x,
            canonical_start_y,
            canonical_end_x,
            canonical_end_y,
        ) != expected_canonical:
            raise _error("INVALID_GEOMETRY")
        expected_length = _decimal_value(
            math.hypot(
                float(canonical_end_x - canonical_start_x),
                float(canonical_end_y - canonical_start_y),
            ),
            quantum=METRIC_QUANTUM,
            maximum=MAX_SCALE_OR_METRIC,
        )
        if canonical_length != expected_length:
            raise _error("INVALID_GEOMETRY")
        prepared.append(
            _PreparedWall(
                candidate_id=candidate.candidate_id,
                pixels_per_meter=scale,
                raw_start_x=raw_start_x,
                raw_start_y=raw_start_y,
                raw_end_x=raw_end_x,
                raw_end_y=raw_end_y,
                raw_length_pixels=raw_length,
                canonical_start_x=canonical_start_x,
                canonical_start_y=canonical_start_y,
                canonical_end_x=canonical_end_x,
                canonical_end_y=canonical_end_y,
                canonical_length_meters=canonical_length,
                angle_degrees=canonical_angle,
            )
        )
    return tuple(prepared)


def _record(wall: Wall) -> PersistedWallRecord:
    return PersistedWallRecord(
        id=wall.id,
        floor_plan_id=wall.floor_plan_id,
        processing_job_id=wall.processing_job_id,
        candidate_id=wall.candidate_id,
        status=wall.status,
        pixels_per_meter=wall.pixels_per_meter,
        raw_start_x=wall.raw_start_x,
        raw_start_y=wall.raw_start_y,
        raw_end_x=wall.raw_end_x,
        raw_end_y=wall.raw_end_y,
        raw_length_pixels=wall.raw_length_pixels,
        canonical_start_x=wall.canonical_start_x,
        canonical_start_y=wall.canonical_start_y,
        canonical_end_x=wall.canonical_end_x,
        canonical_end_y=wall.canonical_end_y,
        canonical_length_meters=wall.canonical_length_meters,
        angle_degrees=wall.angle_degrees,
        created_at=wall.created_at,
        updated_at=wall.updated_at,
    )


def replace_detected_wall_geometry(
    database_session: Session,
    floor_plan_id: int,
    processing_job_id: int,
    geometry: NormalizedWallGeometry,
) -> tuple[PersistedWallRecord, ...]:
    floor_plan_id = _positive_identifier(floor_plan_id, "INVALID_FLOOR_PLAN_ID")
    processing_job_id = _positive_identifier(
        processing_job_id,
        "INVALID_PROCESSING_JOB_ID",
    )
    try:
        floor_plan = lock_floor_plan(
            database_session,
            floor_plan_id=floor_plan_id,
        )
        if floor_plan is None:
            raise _error("FLOOR_PLAN_NOT_FOUND")
        processing_job = find_processing_job(
            database_session,
            processing_job_id=processing_job_id,
        )
        if processing_job is None:
            raise _error("PROCESSING_JOB_NOT_FOUND")
        if processing_job.floor_plan_id != floor_plan_id:
            raise _error("PROCESSING_JOB_FLOOR_PLAN_MISMATCH")
        if processing_job.job_type != FLOOR_PLAN_ANALYSIS_JOB_TYPE:
            raise _error("INVALID_PROCESSING_JOB_TYPE")
        if processing_job.status != "processing":
            raise _error("INVALID_PROCESSING_JOB_STATUS")
        prepared = _prepare_geometry(geometry)
        if has_verified_walls(database_session, floor_plan_id=floor_plan_id):
            raise _error("VERIFIED_WALLS_PROTECTED")
        delete_detected_walls(database_session, floor_plan_id=floor_plan_id)
        walls = tuple(
            Wall(
                floor_plan_id=floor_plan_id,
                processing_job_id=processing_job_id,
                status="detected",
                **prepared_wall.__dict__,
            )
            for prepared_wall in prepared
        )
        add_detected_walls(database_session, walls)
        database_session.commit()
        return tuple(_record(wall) for wall in walls)
    except WallPersistenceError:
        database_session.rollback()
        raise
    except SQLAlchemyError:
        database_session.rollback()
        raise _error("WALL_PERSISTENCE_FAILED") from None


def retrieve_persisted_walls(
    database_session: Session,
    floor_plan_id: int,
) -> tuple[PersistedWallRecord, ...]:
    floor_plan_id = _positive_identifier(floor_plan_id, "INVALID_FLOOR_PLAN_ID")
    try:
        return tuple(
            _record(wall)
            for wall in list_walls(
                database_session,
                floor_plan_id=floor_plan_id,
            )
        )
    except SQLAlchemyError:
        database_session.rollback()
        raise _error("WALL_RETRIEVAL_FAILED") from None
