from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from app.geometry.coordinates import CanonicalCoordinateSystem, CanonicalPoint, rounded_metric
from app.geometry.walls import NormalizedWallGeometry
if TYPE_CHECKING:
    from app.services.authoritative_symbol_service import AuthoritativeSymbolCandidate


SCHEMA_VERSION = 1
MAXIMUM_IDENTIFIER = 9_007_199_254_740_991
MAXIMUM_IMAGE_EDGE = 4096
MAXIMUM_NAME_LENGTH = 255
ERROR_MESSAGE = "The canonical geometry document is invalid."


class CanonicalGeometryError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGE)


def _fail(code: str) -> None:
    raise CanonicalGeometryError(code)


def _exact_keys(value: object, keys: set[str], code: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        _fail(code)
    return value


def _identifier(value: object, code: str = "INVALID_IDENTIFIER") -> int:
    if type(value) is not int or not 0 < value <= MAXIMUM_IDENTIFIER:
        _fail(code)
    return value


def _integer(value: object, code: str) -> int:
    if type(value) is not int or abs(value) > MAXIMUM_IDENTIFIER:
        _fail(code)
    return value


def _number(value: object, code: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if type(value) not in (int, float):
        _fail(code)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        _fail(code)
    if not math.isfinite(number) or (positive and number <= 0) or (nonnegative and number < 0):
        _fail(code)
    return number


def _name(value: object, code: str, *, nullable: bool = False, maximum: int = MAXIMUM_NAME_LENGTH) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str or value != value.strip() or not value or len(value) > maximum or "\x00" in value:
        _fail(code)
    return value


def _close(left: float, right: float) -> bool:
    # Serialized metric values use H2's nine-decimal public precision.
    return math.isclose(left, right, rel_tol=0.0, abs_tol=5e-9)


def _is_authoritative_symbol(value: object) -> bool:
    value_type = type(value)
    return (
        value_type.__module__ == "app.services.authoritative_symbol_service"
        and value_type.__name__ == "AuthoritativeSymbolCandidate"
    )


@dataclass(frozen=True)
class CanonicalFloor:
    project_floor_id: int
    name: str
    sort_order: int
    elevation_meters: float

    def to_dict(self) -> dict[str, object]:
        return {
            "project_floor_id": self.project_floor_id,
            "name": self.name,
            "sort_order": self.sort_order,
            "elevation_meters": rounded_metric(self.elevation_meters),
        }


@dataclass(frozen=True)
class CanonicalDocumentWall:
    id: int
    source_candidate_id: int | None
    processing_job_id: int | None
    status: str
    start: CanonicalPoint
    end: CanonicalPoint
    length_meters: float
    angle_degrees: float
    thickness_meters: float | None = None
    height_meters: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_candidate_id": self.source_candidate_id,
            "processing_job_id": self.processing_job_id,
            "status": self.status,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "length_meters": rounded_metric(self.length_meters),
            "angle_degrees": rounded_metric(self.angle_degrees),
            "thickness_meters": None if self.thickness_meters is None else rounded_metric(self.thickness_meters),
            "height_meters": None if self.height_meters is None else rounded_metric(self.height_meters),
        }


@dataclass(frozen=True)
class CanonicalRoom:
    id: int
    name: str | None
    boundary: tuple[CanonicalPoint, ...]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "boundary": [point.to_dict() for point in self.boundary]}


@dataclass(frozen=True)
class CanonicalSymbol:
    id: str
    source_type: str
    source_record_id: int
    processing_job_id: int
    status: str
    class_id: int
    class_name: str
    position: CanonicalPoint

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_record_id": self.source_record_id,
            "processing_job_id": self.processing_job_id,
            "status": self.status,
            "class": {"id": self.class_id, "name": self.class_name},
            "position": self.position.to_dict(),
        }


@dataclass(frozen=True)
class CanonicalRoutePoint:
    project_floor_id: int
    x: float
    y: float
    elevation_meters: float

    def to_dict(self) -> dict[str, object]:
        return {
            "project_floor_id": self.project_floor_id,
            "x": rounded_metric(self.x),
            "y": rounded_metric(self.y),
            "elevation_meters": rounded_metric(self.elevation_meters),
        }


@dataclass(frozen=True)
class CanonicalRoute:
    id: int
    points: tuple[CanonicalRoutePoint, ...]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "points": [point.to_dict() for point in self.points]}


@dataclass(frozen=True)
class CanonicalGeometryDocument:
    schema_version: int
    project_id: int
    floor: CanonicalFloor
    floor_plan_id: int
    coordinate_system: CanonicalCoordinateSystem
    walls: tuple[CanonicalDocumentWall, ...]
    rooms: tuple[CanonicalRoom, ...]
    symbols: tuple[CanonicalSymbol, ...]
    routes: tuple[CanonicalRoute, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "floor": self.floor.to_dict(),
            "floor_plan_id": self.floor_plan_id,
            "coordinate_system": self.coordinate_system.to_dict(),
            "walls": [wall.to_dict() for wall in self.walls],
            "rooms": [room.to_dict() for room in self.rooms],
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "routes": [route.to_dict() for route in self.routes],
        }


def _coordinate_system(value: object) -> CanonicalCoordinateSystem:
    data = _exact_keys(value, {"unit", "origin", "x_direction", "y_direction", "pixels_per_meter", "image_width_pixels", "image_height_pixels", "width_meters", "height_meters"}, "INVALID_COORDINATE_SYSTEM")
    if (data["unit"], data["origin"], data["x_direction"], data["y_direction"]) != ("meter", "image_top_left", "right", "down"):
        _fail("INVALID_COORDINATE_SYSTEM")
    scale = _number(data["pixels_per_meter"], "INVALID_COORDINATE_SYSTEM", positive=True)
    width = _integer(data["image_width_pixels"], "INVALID_COORDINATE_SYSTEM")
    height = _integer(data["image_height_pixels"], "INVALID_COORDINATE_SYSTEM")
    if not 0 < width <= MAXIMUM_IMAGE_EDGE or not 0 < height <= MAXIMUM_IMAGE_EDGE:
        _fail("INVALID_COORDINATE_SYSTEM")
    width_meters = _number(data["width_meters"], "INVALID_COORDINATE_SYSTEM", positive=True)
    height_meters = _number(data["height_meters"], "INVALID_COORDINATE_SYSTEM", positive=True)
    if not _close(width_meters, width / scale) or not _close(height_meters, height / scale):
        _fail("INVALID_COORDINATE_SYSTEM")
    return CanonicalCoordinateSystem(scale, width, height, width_meters, height_meters)


def _point(value: object, coordinate_system: CanonicalCoordinateSystem, code: str = "INVALID_POINT") -> CanonicalPoint:
    data = _exact_keys(value, {"x", "y"}, code)
    x = _number(data["x"], code, nonnegative=True)
    y = _number(data["y"], code, nonnegative=True)
    if x > coordinate_system.width_meters or y > coordinate_system.height_meters:
        _fail(code)
    return CanonicalPoint(x, y)


def _nullable_positive(value: object, code: str) -> float | None:
    return None if value is None else _number(value, code, positive=True)


def _wall(value: object, cs: CanonicalCoordinateSystem) -> CanonicalDocumentWall:
    data = _exact_keys(value, {"id", "source_candidate_id", "processing_job_id", "status", "start", "end", "length_meters", "angle_degrees", "thickness_meters", "height_meters"}, "INVALID_WALL")
    start, end = _point(data["start"], cs, "INVALID_WALL"), _point(data["end"], cs, "INVALID_WALL")
    length = _number(data["length_meters"], "INVALID_WALL", nonnegative=True)
    derived = math.hypot(end.x - start.x, end.y - start.y)
    if not _close(length, derived):
        _fail("INVALID_WALL")
    angle = _number(data["angle_degrees"], "INVALID_WALL")
    if not 0 <= angle < 180 or type(data["status"]) is not str or data["status"] not in {"detected", "verified"}:
        _fail("INVALID_WALL")
    return CanonicalDocumentWall(
        _identifier(data["id"]),
        None if data["source_candidate_id"] is None else _identifier(data["source_candidate_id"]),
        None if data["processing_job_id"] is None else _identifier(data["processing_job_id"]),
        data["status"], start, end, derived, angle,
        _nullable_positive(data["thickness_meters"], "INVALID_WALL"),
        _nullable_positive(data["height_meters"], "INVALID_WALL"),
    )


def _room(value: object, cs: CanonicalCoordinateSystem) -> CanonicalRoom:
    data = _exact_keys(value, {"id", "name", "boundary"}, "INVALID_ROOM")
    if type(data["boundary"]) is not list or len(data["boundary"]) < 3:
        _fail("INVALID_ROOM")
    points = tuple(_point(item, cs, "INVALID_ROOM") for item in data["boundary"])
    if any(
        _close(points[index].x, points[(index + 1) % len(points)].x)
        and _close(points[index].y, points[(index + 1) % len(points)].y)
        for index in range(len(points))
    ):
        _fail("INVALID_ROOM")
    return CanonicalRoom(_identifier(data["id"]), _name(data["name"], "INVALID_ROOM", nullable=True), points)


def _symbol(value: object, cs: CanonicalCoordinateSystem) -> CanonicalSymbol:
    data = _exact_keys(value, {"id", "source_type", "source_record_id", "processing_job_id", "status", "class", "position"}, "INVALID_SYMBOL")
    source_type = data["source_type"]
    record_id = _identifier(data["source_record_id"])
    if type(source_type) is not str:
        _fail("INVALID_SYMBOL")
    expected_status = {"detected": "confirmed", "manual": "manually_added"}.get(source_type)
    if expected_status is None or data["status"] != expected_status or data["id"] != f"{source_type}:{record_id}":
        _fail("INVALID_SYMBOL")
    class_data = _exact_keys(data["class"], {"id", "name"}, "INVALID_SYMBOL")
    if type(class_data["id"]) is not int or not 0 <= class_data["id"] <= MAXIMUM_IDENTIFIER:
        _fail("INVALID_SYMBOL")
    return CanonicalSymbol(data["id"], source_type, record_id, _identifier(data["processing_job_id"]), data["status"], class_data["id"], _name(class_data["name"], "INVALID_SYMBOL"), _point(data["position"], cs, "INVALID_SYMBOL"))


def _route(value: object, cs: CanonicalCoordinateSystem) -> CanonicalRoute:
    data = _exact_keys(value, {"id", "points"}, "INVALID_ROUTE")
    if type(data["points"]) is not list or len(data["points"]) < 2:
        _fail("INVALID_ROUTE")
    points = []
    for item in data["points"]:
        point = _exact_keys(item, {"project_floor_id", "x", "y", "elevation_meters"}, "INVALID_ROUTE")
        metric = _point({"x": point["x"], "y": point["y"]}, cs, "INVALID_ROUTE")
        points.append(CanonicalRoutePoint(_identifier(point["project_floor_id"]), metric.x, metric.y, _number(point["elevation_meters"], "INVALID_ROUTE")))
    return CanonicalRoute(_identifier(data["id"]), tuple(points))


def canonical_geometry_from_dict(value: object) -> CanonicalGeometryDocument:
    data = _exact_keys(value, {"schema_version", "project_id", "floor", "floor_plan_id", "coordinate_system", "walls", "rooms", "symbols", "routes"}, "INVALID_DOCUMENT")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        _fail("UNSUPPORTED_SCHEMA_VERSION")
    floor_data = _exact_keys(data["floor"], {"project_floor_id", "name", "sort_order", "elevation_meters"}, "INVALID_FLOOR")
    floor = CanonicalFloor(_identifier(floor_data["project_floor_id"]), _name(floor_data["name"], "INVALID_FLOOR", maximum=100), _integer(floor_data["sort_order"], "INVALID_FLOOR"), _number(floor_data["elevation_meters"], "INVALID_FLOOR"))
    cs = _coordinate_system(data["coordinate_system"])
    for key in ("walls", "rooms", "symbols", "routes"):
        if type(data[key]) is not list:
            _fail("INVALID_DOCUMENT")
    return CanonicalGeometryDocument(SCHEMA_VERSION, _identifier(data["project_id"]), floor, _identifier(data["floor_plan_id"]), cs, tuple(_wall(item, cs) for item in data["walls"]), tuple(_room(item, cs) for item in data["rooms"]), tuple(_symbol(item, cs) for item in data["symbols"]), tuple(_route(item, cs) for item in data["routes"]))


def build_canonical_geometry(*, project_id: object, project_floor_id: object, floor_name: object, floor_sort_order: object, floor_elevation_meters: object, floor_plan_id: object, wall_geometry: NormalizedWallGeometry, authoritative_symbols: Iterable["AuthoritativeSymbolCandidate"], symbol_processing_job_id: object, wall_processing_job_id: object | None = None, wall_status: str = "detected", rooms: Iterable[CanonicalRoom] = (), routes: Iterable[CanonicalRoute] = ()) -> CanonicalGeometryDocument:
    if type(wall_geometry) is not NormalizedWallGeometry or wall_status not in {"detected", "verified"}:
        _fail("INVALID_WALL")
    wall_job = None if wall_processing_job_id is None else _identifier(wall_processing_job_id)
    symbols = []
    job_id = _identifier(symbol_processing_job_id)
    plan_id = _identifier(floor_plan_id)
    cs = wall_geometry.coordinate_system
    walls = tuple(CanonicalDocumentWall(w.candidate_id, w.candidate_id, wall_job, wall_status, w.canonical.start, w.canonical.end, w.canonical.length_meters, float(w.canonical.angle_degrees)) for w in wall_geometry.walls)
    try:
        candidates = tuple(authoritative_symbols)
        canonical_rooms = tuple(rooms)
        canonical_routes = tuple(routes)
    except (TypeError, ValueError):
        _fail("INVALID_DOCUMENT")
    if any(type(room) is not CanonicalRoom for room in canonical_rooms):
        _fail("INVALID_ROOM")
    if any(type(route) is not CanonicalRoute for route in canonical_routes):
        _fail("INVALID_ROUTE")
    for candidate in candidates:
        if not _is_authoritative_symbol(candidate) or candidate.floor_plan_id != plan_id or candidate.processing_job_id != job_id or candidate.image_width_pixels != cs.image_width_pixels or candidate.image_height_pixels != cs.image_height_pixels:
            _fail("INVALID_SYMBOL_PROVENANCE")
        expected_status = {"detected": "confirmed", "manual": "manually_added"}.get(candidate.source_type)
        if expected_status is None or candidate.status != expected_status:
            _fail("INVALID_SYMBOL_PROVENANCE")
        x = _number(candidate.center_x_pixels, "INVALID_SYMBOL", nonnegative=True) / cs.pixels_per_meter
        y = _number(candidate.center_y_pixels, "INVALID_SYMBOL", nonnegative=True) / cs.pixels_per_meter
        point = _point({"x": x, "y": y}, cs, "INVALID_SYMBOL")
        if type(candidate.class_id) is not int or not 0 <= candidate.class_id <= MAXIMUM_IDENTIFIER:
            _fail("INVALID_SYMBOL")
        symbols.append(CanonicalSymbol(f"{candidate.source_type}:{_identifier(candidate.source_record_id)}", candidate.source_type, candidate.source_record_id, job_id, candidate.status, candidate.class_id, _name(candidate.class_name, "INVALID_SYMBOL"), point))
    document = CanonicalGeometryDocument(SCHEMA_VERSION, _identifier(project_id), CanonicalFloor(_identifier(project_floor_id), _name(floor_name, "INVALID_FLOOR", maximum=100), _integer(floor_sort_order, "INVALID_FLOOR"), _number(floor_elevation_meters, "INVALID_FLOOR")), plan_id, cs, walls, canonical_rooms, tuple(symbols), canonical_routes)
    try:
        return canonical_geometry_from_dict(document.to_dict())
    except CanonicalGeometryError:
        raise
    except (AttributeError, TypeError, ValueError, OverflowError):
        _fail("INVALID_DOCUMENT")
