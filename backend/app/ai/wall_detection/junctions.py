"""Join already-detected wall ends using original strokes, not proximity alone."""
import math

import cv2
import numpy as np


def unique_wall_spans(rows):
    """Junction fitting can make two hypotheses exactly coincident."""
    kept={}
    for row in rows:
        a,b=tuple(round(float(x),6) for x in row[:2]),tuple(round(float(x),6) for x in row[2:4])
        key=tuple(sorted((a,b)))
        if key not in kept:kept[key]=row
    return list(kept.values())


def snap_observed_junctions(segments, original_ink, maximum_gap, *, round_coordinates=True):
    if not segments or len(segments) > 512:
        return list(segments)
    height, width = original_ink.shape
    nearby = cv2.dilate(original_ink, np.ones((3, 3), np.uint8))
    radius = cv2.distanceTransform(original_ink, cv2.DIST_L2, 5)
    baseline = list(segments)
    result = list(segments)
    limit = min(32., min(width, height) * .03, max(4., maximum_gap * 4))

    def cross(left, right):
        return float(left[0] * right[1] - left[1] * right[0])

    def supported(point, axis, thickness):
        normal = np.array([-axis[1], axis[0]])
        center = np.rint(point).astype(int)
        edges = [np.rint(point + side * normal * (thickness - 1) / 2).astype(int) for side in (-1, 1)]
        if any(not (0 <= p[0] < width and 0 <= p[1] < height) for p in [center, *edges]):
            return False
        paired = (thickness >= 4 and all(nearby[p[1], p[0]] for p in edges)
                  and original_ink[center[1], center[0]] == 0)
        solid = radius[center[1], center[0]] >= max(2.5, thickness * .3)
        return paired or solid

    for index, row in enumerate(baseline):
        a, b = np.asarray(row[:2], float), np.asarray(row[2:4], float)
        length = np.linalg.norm(b - a)
        # A thick hatch block is not a linear wall anchor. Do not enlarge an
        # existing false positive merely because its rectangle has ink edges.
        if length < max(12, row[4] * 3):
            continue
        axis = (b - a) / length
        new_points = [a, b]
        for end_index, (origin, direction) in enumerate(((a, -1), (b, 1))):
            # A source-backed wall, not a single circuit stroke, must anchor the extension.
            inside = origin - direction * axis * min(length / 2, max(6, row[4]))
            if not supported(inside, axis, row[4]):
                continue
            proposals = []
            for other_index, other in enumerate(baseline):
                if other_index == index:
                    continue
                c, d = np.asarray(other[:2], float), np.asarray(other[2:4], float)
                other_length = np.linalg.norm(d - c)
                if other_length < max(12, other[4] * 3):
                    continue
                other_axis = (d - c) / other_length
                denominator = cross(axis, other_axis)
                if abs(denominator) < .5:
                    continue
                delta = c - origin
                travel = cross(delta, other_axis) / denominator
                projection = cross(delta, axis) / denominator
                along=direction*travel
                # Trim an endpoint overshoot only inside the other observed
                # wall footprint. Never shorten a continuing branch across air.
                if not (.5<along<=limit or (-other[4]/2<=along<-.5 and abs(travel)<=length*.25)):
                    continue
                if not 0 <= projection <= other_length:
                    # Both ends can stop short of a real L corner. Allow only
                    # bounded, independently source-supported continuation of
                    # the OTHER original wall, never a newly repaired anchor.
                    other_end = c if projection < 0 else d
                    other_sign = -1 if projection < 0 else 1
                    other_gap = -projection if projection < 0 else projection-other_length
                    if other_gap > limit:
                        continue
                    inside_other = other_end-other_sign*other_axis*min(other_length/2,max(6,other[4]))
                    if not supported(inside_other, other_axis, other[4]):
                        continue
                    other_points = other_end + np.linspace(0, other_sign*other_gap, math.ceil(other_gap)+1)[:,None]*other_axis
                    def other_interval_supported(point):
                        within_self = abs(cross(axis, point-origin)) <= row[4]/2
                        probe = origin+axis*float((point-origin) @ axis) if within_self else point
                        return supported(probe, axis if within_self else other_axis,
                                         row[4] if within_self else other[4])
                    if not all(other_interval_supported(p) for p in other_points):
                        continue
                target = origin + axis * travel
                if not (0<=target[0]<width and 0<=target[1]<height):continue
                if not supported(target, other_axis, other[4]):
                    continue
                points = origin + np.linspace(0, travel, math.ceil(abs(travel)) + 1)[:, None] * axis
                valid = True
                for point in points:
                    # Meeting the other wall's observed footprint is not an air gap.
                    within_other = abs(cross(other_axis, point - c)) <= other[4] / 2
                    probe = c + other_axis * float((point - c) @ other_axis) if within_other else point
                    if not supported(probe, other_axis if within_other else axis,
                                     other[4] if within_other else row[4]):
                        valid = False
                        break
                if valid:
                    proposals.append((abs(travel), tuple(target)))
            if proposals:
                new_points[end_index] = np.asarray(min(proposals)[1])
        convert=(lambda v:int(round(v))) if round_coordinates else float
        result[index] = (*map(convert,new_points[0]),*map(convert,new_points[1]),row[4])
    return result
