"""Backend physical centerline measurement, independent of display geometry.

The caller supplies physical-path identity and connectivity. Geometry alone
never establishes a junction or says that coincident conduits are the same run.
All coordinates and absolute elevations are metres in the project datum.
"""
from dataclasses import dataclass
import math


MEASUREMENT_REVISION = 'canonical_centerline_3d_v1'


@dataclass(frozen=True)
class RouteMeasurement:
    horizontal_meters: float
    vertical_meters: float
    physical_meters: float
    measurement_revision: str = MEASUREMENT_REVISION


def measure_metric_network(edges):
    """Union only collinear spans of the SAME explicitly supplied physical path.

    Omitted physical_path_id means one caller-scoped physical network, not an
    invitation to combine unrelated circuits. Slopes require explicit support.
    Horizontal/vertical values are projections; never add them to spatial length.
    """
    groups = {}
    for edge in edges:
        a, b = edge['start'], edge['end']
        for point in (a, b):
            if type(point['floor_id']) is not int or point['floor_id'] <= 0:
                raise ValueError('A valid floor reference is required.')
            if any(type(point[k]) not in (int, float) or not math.isfinite(point[k])
                   for k in ('x', 'y', 'elevation_meters')):
                raise ValueError('Metric route coordinates must be finite numbers.')
        first = (a['x'], a['y'], a['elevation_meters'])
        delta = tuple(b[k] - a[k] for k in ('x', 'y', 'elevation_meters'))
        horizontal = math.hypot(*delta[:2])
        vertical = abs(delta[2])
        if a['floor_id'] != b['floor_id'] and not edge.get('connector_id'):
            raise ValueError('Inter-floor measurement requires an explicit connector.')
        if horizontal and vertical and edge.get('slope_supported') is not True:
            raise ValueError('Sloped geometry requires explicit support.')
        length = math.hypot(*delta)
        if not math.isfinite(length):
            raise ValueError('Route length exceeds numeric limits.')
        if not length:
            continue
        direction = tuple(value / length for value in delta)
        if direction < (0, 0, 0):
            direction = tuple(-value for value in direction)
        key = (edge.get('physical_path_id'), tuple(sorted((a['floor_id'], b['floor_id']))),
               edge.get('connector_id'))
        lines = groups.setdefault(key, [])
        for origin, axis, intervals in lines:
            # Numerical equality only. No source-pixel proximity or junction snap.
            offset = tuple(x - y for x, y in zip(first, origin))
            projection = sum(x * y for x, y in zip(offset, axis))
            if (max(abs(x-y) for x, y in zip(direction, axis)) <= 1e-12
                    and math.hypot(*(x-projection*y for x, y in zip(offset, axis))) <= 1e-9):
                break
        else:
            origin, axis, intervals = first, direction, []
            lines.append((origin, axis, intervals))
        start = sum((x-y)*z for x, y, z in zip(first, origin, axis))
        end = start + sum(x*y for x, y in zip(delta, axis))
        intervals.append(sorted((start, end)))
    totals, horizontal, vertical = [], [], []
    for lines in groups.values():
        for _, axis, intervals in lines:
            low, high = sorted(intervals)[0]
            spans = []
            for first, last in sorted(intervals)[1:]:
                if first <= high + 1e-9:
                    high = max(high, last)
                else:
                    spans.append(high-low)
                    low, high = first, last
            spans.append(high-low)
            length = math.fsum(spans)
            totals.append(length)
            horizontal.append(length * math.hypot(*axis[:2]))
            vertical.append(length * abs(axis[2]))
    return RouteMeasurement(math.fsum(horizontal), math.fsum(vertical), math.fsum(totals))
