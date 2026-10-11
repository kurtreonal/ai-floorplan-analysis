"""Source-ink observations between adjacent fixture axes, never circuit inference."""
import math
import re

import cv2
import numpy as np


FIXTURE_PATTERN = r'troffer|fluorescent|downlight|ceiling light|lighting point'
CONFIGURATION = dict(version='fixture-axis-source-ink-v1', threshold_c=8,
                     minimum_support=.95, maximum_white_run=3,
                     maximum_fixtures=192, maximum_pairs=8192)


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
    centers = np.array([(s.center.x, s.center.y) for s in fixtures])
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
            # Stable tie-break: nearest centre axis first, then signed offset.
            for offset in sorted(range(-offset_limit, offset_limit + 1), key=lambda x: (abs(x), x)):
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
                if not (solid or dashed):
                    continue
                if best is None or score > best[0]:
                    best = score, tuple(map(float, a)), tuple(map(float, b)), not solid
            if best:
                rows.append((best[1], best[2], set(), best[3]))
    return sorted(rows), truncated
