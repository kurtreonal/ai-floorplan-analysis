"""Automatic visible-ink proposals, not inferred circuits or installation routes."""
import math

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    CandidateWarning, FloorPlanInterpretationPayload, ObservedRoutes,
    ObservedRouteSegment, PixelPoint,
)

EVIDENCE_VERSION = "device-anchored-visible-ink-v1"


def _near_box(point, bounds, tolerance):
    x, y = point
    return (bounds.x - tolerance <= x <= bounds.x + bounds.width + tolerance
            and bounds.y - tolerance <= y <= bounds.y + bounds.height + tolerance)


def _parallel_wall(segment, walls, tolerance):
    a, b = np.asarray(segment[0], float), np.asarray(segment[1], float)
    axis = (b - a) / np.linalg.norm(b - a)
    for wall in walls:
        c, d = np.array([wall.start.x, wall.start.y]), np.array([wall.end.x, wall.end.y])
        length = np.linalg.norm(d - c)
        if length == 0:
            continue
        direction = (d - c) / length
        if abs(float(axis @ direction)) < math.cos(math.radians(5)):
            continue
        normal = np.array([-direction[1], direction[0]])
        if max(abs(float((p - c) @ normal)) for p in (a, b)) > tolerance:
            continue
        low, high = sorted(float((p - c) @ direction) for p in (a, b))
        if min(length, high) - max(0, low) >= (high - low) * .8:
            return True
    return False


def with_automatic_wiring(payload, image_rgb, *, maximum_segments=128):
    """Find continuous strokes with two distinct nearby device proposals.

    Symbol bounds anchor candidate fragments, never prove connectivity. Gaps,
    curves, one-ended branches, installation elevations and circuit topology are
    deliberately not completed. Missing extraction remains partial/unknown.
    """
    if (type(payload) is not FloorPlanInterpretationPayload
            or not isinstance(image_rgb, np.ndarray) or image_rgb.dtype != np.uint8
            or image_rgb.ndim != 3 or image_rgb.shape[2] != 3
            or image_rgb.shape[:2] != (payload.source_plane.height_pixels, payload.source_plane.width_pixels)
            or max(image_rgb.shape[:2]) > 4096
            or type(maximum_segments) is not int or not 1 <= maximum_segments <= 512):
        raise ValueError("Automatic wiring requires bounded, matching source pixels.")
    # Do not overwrite local-gateway observations or an existing candidate run.
    if payload.observed_routes.segments:
        return payload
    # A valid normalized page can exceed this extractor's working budget.
    # Keep symbol/wall processing successful instead of failing the whole job.
    if image_rgb.shape[0] * image_rgb.shape[1] > 12_000_000:
        value = payload.model_dump(mode="json")
        value["warnings"].append(CandidateWarning(code="automatic_wiring_budget", severity="warning",
            message="Automatic wiring exceeded its working limit; draw missing traces in the editor.").model_dump())
        return FloorPlanInterpretationPayload.model_validate(value)
    regions = [region for region in payload.regions if region.kind == "plan_region"]
    symbols = [symbol for symbol in payload.symbols.items if symbol.bounds is not None]
    if not regions or len(symbols) < 2:
        return payload
    height, width = image_rgb.shape[:2]
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    block = max(31, round(min(width, height) * .09)) | 1
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, block, 12)
    scope = np.zeros_like(ink)
    for region in regions:
        bounds = region.bounds
        x, y = math.ceil(bounds.x), math.ceil(bounds.y)
        right, bottom = min(width, math.floor(bounds.x + bounds.width)), min(height, math.floor(bounds.y + bounds.height))
        scope[y:bottom, x:right] = 255
    ink = cv2.bitwise_and(ink, scope)
    search = ink.copy()
    padding = max(2, min(6, round(min(width, height) * .0015)))
    # Glyph interiors cannot masquerade as a wire connecting a device to itself.
    for symbol in symbols:
        bounds = symbol.bounds
        left, top = max(0, math.floor(bounds.x) - padding), max(0, math.floor(bounds.y) - padding)
        right = min(width, math.ceil(bounds.x + bounds.width) + padding + 1)
        bottom = min(height, math.ceil(bounds.y + bounds.height) + padding + 1)
        search[top:bottom, left:right] = 0
    minimum = max(12, round(min(width, height) * .005))
    raw = cv2.HoughLinesP(search, 1, math.pi / 180, max(8, round(minimum * .7)),
                          minLineLength=minimum, maxLineGap=0)
    if raw is None:
        rows = []
    else:
        rows = sorted((tuple(map(int, line[0])) for line in raw),
                      key=lambda row: (-math.hypot(row[2] - row[0], row[3] - row[1]), row))
    truncated = len(rows) > 4096
    selected = []
    support = cv2.dilate(ink, np.ones((3, 3), np.uint8))
    for x1, y1, x2, y2 in rows[:4096]:
        a, b = (x1, y1), (x2, y2)
        if b < a:
            a, b = b, a
        if _parallel_wall((a, b), payload.walls.items, padding + 4):
            continue
        anchors_a = {symbol.id for symbol in symbols if _near_box(a, symbol.bounds, padding + 4)}
        anchors_b = {symbol.id for symbol in symbols if _near_box(b, symbol.bounds, padding + 4)}
        pairs = {tuple(sorted((left, right))) for left in anchors_a for right in anchors_b if left != right}
        if not pairs:
            continue
        count = math.ceil(math.dist(a, b)) + 1
        xs = np.rint(np.linspace(a[0], b[0], count)).astype(int)
        ys = np.rint(np.linspace(a[1], b[1], count)).astype(int)
        # No interpolation across unsupported gaps, even beside detected devices.
        if not np.all(support[ys, xs]):
            continue
        if any(pairs & other_pairs and max(math.dist(a, c), math.dist(b, d)) <= 5
               for c, d, other_pairs in selected):
            continue
        selected.append((a, b, pairs))
    truncated = truncated or len(selected) > maximum_segments
    segments = []
    for index, (a, b, _) in enumerate(sorted(selected[:maximum_segments]), 1):
        refs = tuple(sorted(f"region:{region.id}" for region in regions
                            if _near_box(a, region.bounds, 0) and _near_box(b, region.bounds, 0)))
        if not refs:
            continue
        segments.append(ObservedRouteSegment(id=f"segment-{index:04d}",
                        points=(PixelPoint(x=a[0], y=a[1]), PixelPoint(x=b[0], y=b[1])),
                        evidence_refs=refs, ambiguity="ambiguous"))
    value = payload.model_dump(mode="json")
    if value["document_state"] == "completed":
        value["document_state"] = "partial"
    value["observed_routes"] = ObservedRoutes(state="partial", segments=tuple(segments),
                                               connections=(), truncated=truncated).model_dump()
    value["warnings"].append(CandidateWarning(code="automatic_visible_wiring", severity="info",
        message="Visible wiring proposals require review; gaps, circuit connections and heights remain unresolved.").model_dump())
    return FloorPlanInterpretationPayload.model_validate(value)
