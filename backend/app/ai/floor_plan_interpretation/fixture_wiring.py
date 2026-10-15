"""Source-ink observations between adjacent fixture axes, never circuit inference."""
import math
import re

import cv2
import numpy as np


FIXTURE_PATTERN = r'troffer|fluorescent|downlight|ceiling light|lighting point'
CONFIGURATION = dict(version='fixture-axis-source-ink-v3', threshold_c=8,
                     minimum_support=.95, maximum_white_run=3,
                     maximum_fixtures=192, maximum_pairs=8192,maximum_offsets=64)


def _bounded_terminal(ink, scope, first_box, last_box, axis, position):
    """A wider offset needs a source stop/turn outside at least one glyph.

    A continuous ceiling-grid stroke may intersect both fixture rectangles.
    Inspect beyond the outer bounds so the glyph itself cannot create the stop.
    Leaving the source/scope is missing evidence, rather than a source terminal.
    """
    attribute = 'x' if axis == 0 else 'y'
    extent = 'width' if axis == 0 else 'height'
    ordered = sorted((first_box, last_box), key=lambda box: getattr(box, attribute))
    minor = min(first_box.width, first_box.height, last_box.width, last_box.height)
    distance = max(8, min(24, round(minor * .75)))
    radius = max(2, min(9, round(minor * .2)))
    height, width = ink.shape
    for box, direction in ((ordered[0], -1), (ordered[1], 1)):
        boundary = getattr(box, attribute) + (getattr(box, extent) if direction > 0 else 0)
        along = boundary + direction * np.arange(3, distance + 3)
        xy = np.empty((len(along), 2), dtype=int)
        xy[:, axis] = np.rint(along).astype(int)
        xy[:, 1 - axis] = round(position)
        if ((xy < 0).any() or (xy[:, 0] >= width).any()
                or (xy[:, 1] >= height).any()
                or not (scope[xy[:, 1], xy[:, 0]] > 0).all()):
            continue
        cross_samples = xy[:, 1 - axis, None] + np.arange(-radius, radius + 1)
        if (cross_samples < 0).any() or (cross_samples >= (height if axis == 0 else width)).any():
            continue
        # Follow the local stroke band, including raster edge wobble. Sampling
        # just one faint edge of a broad continuous grid can manufacture a stop.
        supported = (ink[cross_samples, xy[:, 0, None]] if axis == 0
                     else ink[xy[:, 1, None], cross_samples]).any(axis=1)
        # Several consecutive blank pixels distinguish a stop/turn from one
        # thresholding hole in an otherwise uninterrupted source stroke.
        if supported.mean() <= .5 and np.convolve(
                (~supported).astype(int), np.ones(3, dtype=int), mode='valid').max() == 3:
            return True
    return False


def ceiling_fixtures(payload):
    return sorted((s for s in payload.symbols.items if s.bounds and re.search(
        FIXTURE_PATTERN, s.training_legend.name if s.training_legend else s.observed_label or '', re.I)),
        key=lambda s: (s.center.x, s.center.y, s.id))


def fixture_axis_traces(payload, image_rgb, scope, *, dash_validator=None):
    """Return None for other drawing styles; an empty list means no ink evidence.

    Fixture alignment merely bounds the search. Glyph interiors cannot supply
    evidence, and no attachment, junction, circuit or height is inferred here.
    """
    fixtures = ceiling_fixtures(payload)
    if len(fixtures) < 4:
        return None, False
    truncated = len(fixtures) > CONFIGURATION['maximum_fixtures']
    fixtures = fixtures[:CONFIGURATION['maximum_fixtures']]
    height, width = image_rgb.shape[:2]
    edge = min(width, height)
    tolerance = max(3, edge * .009)
    offset_limit = max(2, round(edge * .006))
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, max(31, round(edge * .09)) | 1, CONFIGURATION['threshold_c'])
    ink = cv2.dilate(cv2.bitwise_and(ink, scope), np.ones((3, 3), np.uint8))
    glyphs = np.zeros((height, width), np.uint8)
    for symbol in fixtures:
        box = symbol.bounds
        glyphs[max(0, math.ceil(box.y)):min(height, math.floor(box.y + box.height) + 1),
               max(0, math.ceil(box.x)):min(width, math.floor(box.x + box.width) + 1)] = 1
    centers = np.array([(s.center.x, s.center.y) for s in fixtures], dtype=float)
    rows, tested = [], 0
    for i, first in enumerate(centers):
        for j in range(i + 1, len(centers)):
            last = centers[j]
            delta = last - first
            horizontal = abs(delta[1]) < tolerance and abs(delta[0]) > max(30, edge * .02)
            vertical = abs(delta[0]) < tolerance and abs(delta[1]) > max(30, edge * .02)
            if not (horizontal or vertical):
                continue
            axis = 0 if horizontal else 1
            cross = 1 - axis
            middle = (first[cross] + last[cross]) / 2
            between = ((centers[:, axis] > min(first[axis], last[axis]))
                       & (centers[:, axis] < max(first[axis], last[axis]))
                       & (abs(centers[:, cross] - middle) < tolerance))
            between[[i, j]] = False
            if between.any():
                continue
            tested += 1
            if tested > CONFIGURATION['maximum_pairs']:
                return rows, True
            best = None
            # A detector centre is not a measured terminal. Bound the scan by
            # the two glyphs' shared cross-axis interval, rather than letting
            # small centre bias exclude a fully supported solid source stroke.
            # No axis outside BOTH device bounds is eligible.
            first_box,last_box=fixtures[i].bounds,fixtures[j].bounds
            attribute='x' if cross==0 else 'y'
            extent='width' if cross==0 else 'height'
            low=max(getattr(first_box,attribute),getattr(last_box,attribute))
            high=min(getattr(first_box,attribute)+getattr(first_box,extent),
                     getattr(last_box,attribute)+getattr(last_box,extent))
            port_scan=max(offset_limit,min(first_box.width,first_box.height,
                                           last_box.width,last_box.height)*.5)
            # Long fixture tips often intersect ceiling-grid strokes. Restrict
            # the wider solid scan to a glyph-size-derived central port band.
            low=max(low,middle-port_scan);high=min(high,middle+port_scan)
            # Keep the established tight centre search for dashed proposals;
            # wider bounded locations require the stronger continuous-ink gate.
            offsets=sorted(range(math.ceil(low-middle),math.floor(high-middle)+1),key=lambda x: (abs(x),x))
            truncated |= len(offsets)>CONFIGURATION['maximum_offsets']
            for offset in offsets[:CONFIGURATION['maximum_offsets']]:
                a, b = first.copy(), last.copy()
                a[cross] = b[cross] = middle + offset
                points = np.linspace(a, b, max(2, math.ceil(np.linalg.norm(b - a)) + 1))
                xy = np.rint(points).astype(int)
                if (xy < 0).any() or (xy[:, 0] >= width).any() or (xy[:, 1] >= height).any():
                    continue
                if not (scope[xy[:, 1], xy[:, 0]] > 0).all():
                    continue
                outside = glyphs[xy[:, 1], xy[:, 0]] == 0
                if outside.sum() < 12:
                    continue
                evidence = ink[xy[:, 1], xy[:, 0]][outside] > 0
                score = float(evidence.mean())
                transitions = np.flatnonzero(np.r_[True, evidence[1:] != evidence[:-1], True])
                gaps = [q - p for p, q in zip(transitions, transitions[1:]) if not evidence[p]]
                dashed = bool(dash_validator and dash_validator(evidence, max(8, min(64, round(edge * .035)))))
                solid = (score >= CONFIGURATION['minimum_support']
                         and max(gaps, default=0) <= CONFIGURATION['maximum_white_run'])
                if solid and abs(offset) > offset_limit:
                    solid = _bounded_terminal(ink, scope, first_box, last_box, axis, middle + offset)
                if not (solid or (dashed and abs(offset)<=offset_limit)):
                    continue
                if best is None or score > best[0]:
                    best = score, tuple(map(float, a)), tuple(map(float, b)), not solid
            if best:
                rows.append((best[1], best[2], set(), best[3]))
    return sorted(rows), truncated
