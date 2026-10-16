"""Unique physical centerline spans within an explicitly supplied path/network.

Callers own connectivity; this module never discovers circuit membership.
Crossings and parallel lines remain separate. Only collinear intervals unite.
"""
import math


def unique_polyline_length(points):
    return unique_paths_length([points])


def unique_paths_length(paths):
    """Union collinear spans in explicitly associated paths, never bridge them."""
    groups = []
    for a, b in (edge for points in paths for edge in zip(points, points[1:])):
        ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
        if not all(math.isfinite(v) for v in (ax, ay, bx, by)):
            raise ValueError('Path coordinates must be finite.')
        dx, dy = bx-ax, by-ay
        length = math.hypot(dx, dy)
        if not length:
            continue
        ux, uy = dx/length, dy/length
        if (ux, uy) < (0, 0):
            ux, uy = -ux, -uy
        for group in groups:
            gx, gy, x, y, intervals = group
            # Numerical identity only, never a source-pixel snapping radius.
            if abs(ux*gy-uy*gx) <= 1e-12 and abs((ax-x)*gy-(ay-y)*gx) <= 1e-9:
                break
        else:
            intervals = []
            groups.append((ux, uy, ax, ay, intervals))
            gx, gy, x, y = ux, uy, ax, ay
        intervals.append(sorted(((ax-x)*gx+(ay-y)*gy, (bx-x)*gx+(by-y)*gy)))
    lengths = []
    for *_, intervals in groups:
        low, high = sorted(intervals)[0]
        for first, last in sorted(intervals)[1:]:
            if first <= high:
                high = max(high, last)
            else:
                lengths.append(high-low)
                low, high = first, last
        lengths.append(high-low)
    return math.fsum(lengths)


def unique_metric_edges(edges):
    """Physical horizontal/vertical union inside ONE explicit metric network.

    Keep floor/elevation and riser connector identities separate. No display
    geometry, conductor multiplication or unnamed floor shortcuts are accepted.
    """
    horizontal, vertical = {}, {}
    for edge in edges:
        a, b = edge['start'], edge['end']
        if not all(math.isfinite(p[k]) for p in (a,b) for k in ('x','y','elevation_meters')):
            raise ValueError('Network coordinates must be finite.')
        if a['elevation_meters'] == b['elevation_meters']:
            if a['floor_id'] != b['floor_id']: raise ValueError('Horizontal paths cannot shortcut floors.')
            horizontal.setdefault((a['floor_id'], a['elevation_meters']), []).append([a,b])
        else:
            if (a['x'],a['y']) != (b['x'],b['y']): raise ValueError('A height change requires a vertical segment.')
            floors = tuple(sorted((a['floor_id'], b['floor_id'])))
            if floors[0] != floors[1] and not edge.get('connector_id'): raise ValueError('An inter-floor segment requires a connector.')
            key = (floors, edge.get('connector_id'), a['x'], a['y'])
            vertical.setdefault(key, []).append([dict(x=a['elevation_meters'],y=0),dict(x=b['elevation_meters'],y=0)])
    h = math.fsum(unique_paths_length(paths) for paths in horizontal.values())
    v = math.fsum(unique_paths_length(paths) for paths in vertical.values())
    return h, v
