"""Refine already-supported traces inside their own contiguous source ink band.

Not a wire classifier or gap closer. No widest/nearest alternative line search:
ambiguous cross-sections and glyphs cannot vote for a different parallel stroke.
"""
import math

import numpy as np


def refine_axis_trace(a, b, ink, excluded, *, dashed=False):
    a, b = tuple(a), tuple(b)
    if a[0] == b[0]:
        axis, cross = 1, 0
    elif a[1] == b[1]:
        axis, cross = 0, 1
    else:
        return a, b
    original = a[cross]
    radius = 4  # Local pixel-band identity, never a device/endpoint join radius.
    centers, widths, eligible = [], [], 0
    for along in range(math.ceil(min(a[axis], b[axis])), math.floor(max(a[axis], b[axis])) + 1):
        xy = [0, 0]
        xy[axis], xy[cross] = along, round(original)
        x, y = xy
        if not (radius <= x < ink.shape[1]-radius and radius <= y < ink.shape[0]-radius):
            continue
        if excluded[y, x]:
            continue
        eligible += 1
        low = round(original)-radius
        values = (ink[y, low:low+radius*2+1] if cross == 0
                  else ink[low:low+radius*2+1, x]) > 0
        edges = np.flatnonzero(np.r_[False, values, False][1:] != np.r_[False, values, False][:-1])
        runs = [(lo, hi-1) for lo, hi in zip(edges[::2], edges[1::2])
                if lo > 0 and hi < len(values) and lo-1 <= radius <= hi]
        # More than one possible stroke, or a crossing filling the scan window:
        # no independent centerline evidence from this cross-section.
        if len(runs) != 1:
            continue
        lo, hi = runs[0]
        centers.append(low+(lo+hi)/2)
        widths.append(hi-lo+1)
    if len(centers) < max(12, eligible*(.30 if dashed else .80)):
        return a, b
    center, width = float(np.median(centers)), float(np.median(widths))
    if np.median(np.abs(np.asarray(centers)-center)) > max(.5, width*.25):
        return a, b
    # It must still belong to the same local band, not jump to a parallel line.
    if abs(center-original) > min(2, width/2+1):
        return a, b
    first, last = list(a), list(b)
    first[cross] = last[cross] = center
    return tuple(first), tuple(last)


def chain_exact_traces(segments):
    """One polyline per unbranched chain, with no new edges or gap tolerance.

    Interior crossings are deliberately not nodes. T/X branches stop a chain;
    different line styles and disjoint source-view evidence remain separate.
    """
    paths = list(segments)
    changed = True
    while changed:
        changed = False
        ends = {}
        for i, segment in enumerate(paths):
            for p in (segment.points[0], segment.points[-1]):
                ends.setdefault((p.x, p.y), []).append(i)
        for point, indices in sorted(ends.items()):
            if len(indices) != 2 or indices[0] == indices[1]:
                continue
            i, j = indices
            first, last = paths[i], paths[j]
            if first.line_style != last.line_style or not set(first.evidence_refs) & set(last.evidence_refs):
                continue
            # A third path passing through the proposed join is unresolved
            # branch/crossing evidence, not permission to flatten that network.
            x, y = point
            if any(abs((x-a.x)*(b.y-a.y)-(y-a.y)*(b.x-a.x)) <= 1e-9
                   and min(a.x,b.x) <= x <= max(a.x,b.x) and min(a.y,b.y) <= y <= max(a.y,b.y)
                   for k, path in enumerate(paths) if k not in (i, j)
                   for a, b in zip(path.points, path.points[1:])):
                continue
            left = first.points if (first.points[-1].x, first.points[-1].y) == point else first.points[::-1]
            right = last.points if (last.points[0].x, last.points[0].y) == point else last.points[::-1]
            combined = left + right[1:]
            refs = tuple(sorted(set(first.evidence_refs + last.evidence_refs)))
            if len(combined) > 512 or len(refs) > 32:
                continue
            combined = min(combined, combined[::-1], key=lambda chain: tuple((p.x, p.y) for p in chain))
            merged = first.model_copy(update={'points': combined, 'evidence_refs': refs,
                'ambiguity': 'unknown' if 'unknown' in (first.ambiguity,last.ambiguity) else
                             'ambiguous' if 'ambiguous' in (first.ambiguity,last.ambiguity) else 'clear'})
            paths = [path for k, path in enumerate(paths) if k not in (i, j)] + [merged]
            changed = True
            break
    return tuple(path.model_copy(update={'id': f'segment-{i:04d}'}) for i, path in enumerate(
        sorted(paths, key=lambda p: tuple((v.x,v.y) for v in p.points)), 1))
