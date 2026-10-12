"""Guarded structural colour evidence; monochrome drawings retain the CV path."""
import math
import re

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    CandidateCollection, CandidateWarning, FloorPlanInterpretationPayload, PixelPoint, WallCandidate,
)
from app.ai.wall_detection.detector import (
    _consolidate_wall_segments, _has_compact_annotated_outline,
    _has_compact_parallel_bars, _is_repeated_grid_member, _thin_connected_strokes,
)
from app.ai.wall_detection.band_geometry import refine_filled_bands
from app.ai.wall_detection.junctions import snap_observed_junctions,unique_wall_spans
from app.ai.wall_detection.paired_boundaries import recover_paired_boundaries

CONFIGURATION = dict(version='chromatic-structural-bands-v3', strong_saturation=30,
                     strong_value=180, seed_saturation=12, seed_value=235,
                     hue_tolerance=25, minimum_thickness_ratio=.0067,
                     maximum_hough_lines=2048, maximum_segments=300)


def _suppress_same_band_duplicates(segments, mask):
    """Drop contained hypotheses only when the intervening band is filled.

    Nearby parallel partitions with white space between them are NOT duplicates.
    Retain the longer longitudinal span. A shared centreline is allowed only
    when its entire span is independently supported by that same filled band.
    """
    kept = []
    for segment in sorted(segments, key=lambda s: (-math.dist(s[:2], s[2:4]), s)):
        a, b = np.array(segment[:2]), np.array(segment[2:4])
        duplicate = False
        for index, other in enumerate(kept):
            c, d = np.array(other[:2]), np.array(other[2:4])
            axis = (d - c) / np.linalg.norm(d - c)
            normal = np.array([-axis[1], axis[0]])
            direction = (b - a) / np.linalg.norm(b - a)
            if abs(float(direction @ axis)) < .999:
                continue
            low, high = sorted(float((p - c) @ axis) for p in (a, b))
            if low < -3 or high > np.linalg.norm(d - c) + 3:
                continue
            offsets = [float((p - c) @ normal) for p in (a, b)]
            if max(map(abs, offsets)) > max(segment[4], other[4]) * .6:
                continue
            # Several slices through the overlap must belong to one broad band.
            points = np.linspace(a, b, 32)
            projected = c + ((points - c) @ axis)[:, None] * axis
            corridor = np.array([points * t + projected * (1 - t) for t in np.linspace(0, 1, 5)])
            xy = np.rint(corridor).astype(int)
            if (xy < 0).any() or (xy[..., 0] >= mask.shape[1]).any() or (xy[..., 1] >= mask.shape[0]).any():
                continue
            if (mask[xy[..., 1], xy[..., 0]] > 0).mean() >= .95:
                shift = normal * float(np.mean(offsets)) / 2
                start, end = c + shift, d + shift
                center = np.rint(np.linspace(start, end, max(2, math.ceil(np.linalg.norm(d - c)) + 1))).astype(int)
                if (mask[center[:, 1], center[:, 0]] > 0).mean() >= .95:
                    kept[index] = (*map(int, np.rint(start)), *map(int, np.rint(end)), max(segment[4], other[4]))
                duplicate = True
                break
        if not duplicate:
            kept.append(segment)
    return sorted(kept)


def chromatic_wall_segments(image_rgb, regions, symbols):
    """None means insufficient structural evidence, not an empty wall result."""
    h, w = image_rgb.shape[:2]
    edge = min(w, h)
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    scope = np.zeros((h, w), np.uint8)
    for region in regions:
        b = region.bounds
        scope[max(0, math.ceil(b.y)):min(h, math.floor(b.y + b.height)),
              max(0, math.ceil(b.x)):min(w, math.floor(b.x + b.width))] = 255
    eligible = ((hsv[:, :, 1] >= CONFIGURATION['strong_saturation'])
                & (hsv[:, :, 2] < CONFIGURATION['strong_value']) & (scope > 0))
    if eligible.sum() < max(64, edge * .1):
        return None
    hue = int(np.argmax(np.bincount(hsv[:, :, 0][eligible], minlength=180)))
    delta = abs(hsv[:, :, 0].astype(int) - hue)
    delta = np.minimum(delta, 180 - delta)
    seed = ((hsv[:, :, 1] >= CONFIGURATION['seed_saturation'])
            & (hsv[:, :, 2] < CONFIGURATION['seed_value']) & (delta <= CONFIGURATION['hue_tolerance'])
            & (scope > 0)).astype(np.uint8) * 255
    for symbol in symbols:
        b = symbol.bounds
        training=getattr(symbol,'training_legend',None)
        name=training.name if training else symbol.observed_label or ''
        # Wall-mounted devices and broad annotation boxes must not cut away
        # structural evidence. Only ceiling-fixture interiors are exclusions.
        if b and re.search(r'troffer|fluorescent|downlight|ceiling light',name,re.I):
            seed[max(0, math.floor(b.y) - 3):min(h, math.ceil(b.y + b.height) + 4),
                 max(0, math.floor(b.x) - 3):min(w, math.ceil(b.x + b.width) + 4)] = 0
    seed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    def long_components(mask, ratio):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        keep = np.zeros(count, np.uint8)
        for label in range(1, count):
            if max(stats[label, cv2.CC_STAT_WIDTH], stats[label, cv2.CC_STAT_HEIGHT]) >= edge * ratio:
                keep[label] = 255
        return keep[labels]

    mask = long_components(seed, .14)
    radius = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    mask = cv2.bitwise_and(mask, cv2.dilate((radius >= 2).astype(np.uint8) * 255,
                                         np.ones((5, 5), np.uint8)))
    mask = long_components(mask, .12)
    if not mask.any() or (mask > 0).mean() > .35:
        return None
    skeleton = _thin_connected_strokes(mask)
    radius = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    lines = cv2.HoughLinesP(skeleton, 1, math.pi / 180, 12,
                          minLineLength=max(24, round(edge * .02)), maxLineGap=3)
    if lines is None:
        return None
    rows = sorted((tuple(map(int, row)) for row in lines[:, 0]))
    if len(rows) > CONFIGURATION['maximum_hough_lines']:
        return None
    segments = []
    for x1, y1, x2, y2 in rows:
        length = math.hypot(x2 - x1, y2 - y1)
        axis = np.array([x2 - x1, y2 - y1]) / length
        normal = np.array([-axis[1], axis[0]])
        xs = np.rint(np.linspace(x1, x2, max(2, round(length)))).astype(int)
        ys = np.rint(np.linspace(y1, y2, max(2, round(length)))).astype(int)
        thickness = float(np.median(radius[ys, xs]) * 2)
        if thickness < max(3, edge * CONFIGURATION['minimum_thickness_ratio']):
            continue
        # Follow existing band pixels only; never extrapolate through an opening.
        ends = []
        for origin, direction in ((np.array([x1, y1]), -1), (np.array([x2, y2]), 1)):
            last = origin
            for step in range(1, max(h, w)):
                point = origin + axis * direction * step
                supported = False
                for jitter in (-1, 0, 1):
                    px, py = np.rint(point + normal * jitter).astype(int)
                    if 0 <= px < w and 0 <= py < h and mask[py, px]:
                        supported = True
                if not supported:
                    break
                last = point
            ends.append(tuple(map(int, np.rint(last))))
        a, b = ends
        segments.append((*a, *b, thickness, math.dist(a, b)))
    segments = _consolidate_wall_segments(segments, w, h, 3, evidence_mask=mask)
    segments = _suppress_same_band_duplicates(segments, mask)
    segments = refine_filled_bands(segments, mask)
    segments = _consolidate_wall_segments([(*s,math.dist(s[:2],s[2:4])) for s in segments],w,h,3,evidence_mask=mask)
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, max(31, round(edge * .09)) | 1, 12)
    segments = [s for s in segments if not _has_compact_parallel_bars(s, binary)
                and not _has_compact_annotated_outline(s, binary)
                and not _is_repeated_grid_member(s, binary)]
    # Colour alone is not structure: require sustained broad bands in BOTH axes.
    long = [s for s in segments if math.dist(s[:2], s[2:4]) >= edge * .12]
    horizontal = sum(abs(s[3] - s[1]) < abs(s[2] - s[0]) * .1 for s in long)
    vertical = sum(abs(s[2] - s[0]) < abs(s[3] - s[1]) * .1 for s in long)
    if horizontal < 2 or vertical < 2 or len(segments) > CONFIGURATION['maximum_segments']:
        return None
    segments=unique_wall_spans(snap_observed_junctions(segments,mask,3,round_coordinates=False))
    recovered=recover_paired_boundaries(image_rgb,segments,scope,symbols)
    if recovered and len(segments)+len(recovered)<=CONFIGURATION['maximum_segments']:
        # Original paired boundaries support the new contacts; filled-band
        # masks alone cannot describe an outlined wall's blank interior.
        source_ink=cv2.bitwise_not(binary);source_ink[scope==0]=0
        segments=unique_wall_spans(snap_observed_junctions(segments+recovered,source_ink,3,round_coordinates=False))
    return sorted(segments)


def with_chromatic_wall_evidence(payload, image_rgb):
    if (not isinstance(image_rgb, np.ndarray) or image_rgb.dtype != np.uint8
            or image_rgb.shape != (payload.source_plane.height_pixels, payload.source_plane.width_pixels, 3)):
        raise ValueError('Chromatic evidence requires matching source pixels.')
    # Never break opening references, gateway observations, or oversized jobs.
    if payload.openings.items or image_rgb.shape[0] * image_rgb.shape[1] > 12_000_000:
        return payload
    regions = [r for r in payload.regions if r.kind == 'plan_region']
    if not regions:
        return payload
    segments = chromatic_wall_segments(image_rgb, regions, payload.symbols.items)
    if segments is None or len(payload.warnings) >= 256:
        return payload
    walls = []
    for i, (x1, y1, x2, y2, thickness) in enumerate(segments, 1):
        refs = tuple(f'region:{r.id}' for r in regions if all(
            r.bounds.x <= x <= r.bounds.x + r.bounds.width
            and r.bounds.y <= y <= r.bounds.y + r.bounds.height for x, y in ((x1, y1), (x2, y2))))
        if refs:
            walls.append(WallCandidate(id=f'wall-{i:04d}', start=PixelPoint(x=x1, y=y1),
                                       end=PixelPoint(x=x2, y=y2), estimated_thickness_pixels=thickness,
                                       evidence_refs=refs, ambiguity='ambiguous'))
    # Rooms derived from superseded wall hypotheses cannot remain authoritative.
    value = payload.model_copy(update={
        'walls': CandidateCollection(state='partial', items=tuple(walls), truncated=False),
        'rooms': CandidateCollection(state='unavailable', items=(), truncated=False),
        'document_state': 'partial',
        'warnings': payload.warnings + (CandidateWarning(code='chromatic_structural_bands', severity='info',
            message='Sustained structural colour bands refined wall candidates; openings and thickness remain reviewable.'),),
    })
    return FloorPlanInterpretationPayload.model_validate(value.model_dump())
