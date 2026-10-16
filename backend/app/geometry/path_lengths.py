"""Unique physical centerline spans within ONE explicit logical path.

No cross-path network or circuit membership is inferred. Intersecting and
parallel lines remain separate; only coincident collinear intervals unite.
"""
import math


def unique_polyline_length(points):
    groups = []
    for a, b in zip(points, points[1:]):
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
