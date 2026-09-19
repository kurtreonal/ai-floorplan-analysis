"""Measure generated metric routes without inventing engineering allowances."""
from dataclasses import dataclass
import math

from app.routing.contracts import RouteResult


@dataclass(frozen=True)
class MaterialLengths:
    horizontal_meters: float
    vertical_meters: float
    riser_meters: float
    conduit_meters: float
    conductor_count: int | None
    wire_meters: float | None
    unit: str = "meter"


def measure_material_lengths(route: RouteResult, *, conductor_count: int | None = None) -> MaterialLengths:
    route = RouteResult.model_validate(route.model_dump())
    if conductor_count is not None and (type(conductor_count) is not int or not 1 <= conductor_count <= 1000):
        raise ValueError("Conductor count must be an explicit positive integer no greater than 1000.")
    if not route.segments or route.points != [route.segments[0].start, *(s.end for s in route.segments)]:
        raise ValueError("Route points must match ordered segments.")
    horizontal, vertical, riser = [], [], []
    previous = None
    for segment in route.segments:
        a, b = segment.start, segment.end
        if previous is not None and a != previous:
            raise ValueError("Disconnected route segments.")
        previous = b
        dx, dy, dz = abs(b.x - a.x), abs(b.y - a.y), abs(b.elevation_meters - a.elevation_meters)
        if sum(value > 0 for value in (dx, dy, dz)) != 1:
            raise ValueError("Route segments must be nonzero and orthogonal.")
        if segment.kind == "ceiling_service":
            valid = dz == 0 and a.floor_id == b.floor_id and segment.connector_id is None
        elif segment.kind == "riser":
            valid = dx == dy == 0 and a.floor_id != b.floor_id and bool(segment.connector_id)
            riser.append(dz)
        else:
            valid = dx == dy == 0 and a.floor_id == b.floor_id and segment.connector_id is None
            valid &= b.elevation_meters > a.elevation_meters if segment.kind == "wall_rise" else b.elevation_meters < a.elevation_meters
        if not valid:
            raise ValueError("Route segment type contradicts geometry or floor identity.")
        h = math.hypot(dx, dy)
        if not math.isclose(h, segment.horizontal_meters, abs_tol=1e-9) or not math.isclose(dz, segment.vertical_meters, abs_tol=1e-9):
            raise ValueError("Stored segment measurements disagree with geometry.")
        horizontal.append(h)
        vertical.append(dz)
    h, v = math.fsum(horizontal), math.fsum(vertical)
    total = h + v
    if not all(math.isclose(actual, stored, abs_tol=1e-9) for actual, stored in (
            (h, route.horizontal_meters), (v, route.vertical_meters), (total, route.total_meters))):
        raise ValueError("Stored route totals disagree with geometry.")
    wire = total * conductor_count if conductor_count is not None else None
    if not math.isfinite(total) or (wire is not None and not math.isfinite(wire)):
        raise ValueError("Route measurement exceeds numeric limits.")
    return MaterialLengths(h, v, math.fsum(riser), total, conductor_count, wire)
