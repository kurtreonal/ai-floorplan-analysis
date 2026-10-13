"""Automatic visible-ink proposals, not inferred circuits or installation routes."""
import math
import re

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.fixture_wiring import fixture_axis_traces
from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence

from app.ai.floor_plan_interpretation.candidate import (
    CandidateCollection, CandidateWarning, FloorPlanInterpretationPayload, ObservedRoutes,
    ObservedRouteSegment, PixelPoint,
)

EVIDENCE_VERSION = "raw-source-device-port-evidence-v8"


def with_fixture_wall_conflicts(payload):
    """Reject unverified wall strokes through multiple ceiling-fixture cores.

    Raw hypotheses survive in warnings; saved review geometry is never modified.
    A wall hosting an opening remains protected. No device class is invented.
    """
    fixtures=[s for s in payload.symbols.items if s.bounds and re.search(
        r'troffer|fluorescent|downlight|ceiling light|lighting point',
        s.training_legend.name if s.training_legend else s.observed_label or '',re.I)]
    protected={o.wall_ref for o in payload.openings.items if o.wall_ref}
    kept,conflicts=[],[]
    for wall in payload.walls.items:
        a=np.array([wall.start.x,wall.start.y],float)
        d=np.array([wall.end.x,wall.end.y],float)-a
        length_squared=float(d@d)
        hits=[]
        for symbol in fixtures:
            p=np.array([symbol.center.x,symbol.center.y],float)
            t=float((p-a)@d/length_squared)
            if .05<t<.95 and np.linalg.norm(p-(a+t*d))<=max(2,min(symbol.bounds.width,symbol.bounds.height)*.20):
                hits.append(symbol.id)
        if len(hits)>=2 and wall.id not in protected and len(conflicts)<16:
            conflicts.append(wall)
        else:
            kept.append(wall)
    if not conflicts or len(payload.warnings)+len(conflicts)>256:
        return payload
    warnings=tuple(CandidateWarning(code='fixture_wall_conflict',severity='warning',
        message=f'Unverified wall crossing multiple ceiling-fixture cores omitted from routing; '
                f'raw hypothesis {w.id}: ({w.start.x}, {w.start.y}) to ({w.end.x}, {w.end.y}).')
                   for w in conflicts)
    return FloorPlanInterpretationPayload.model_validate(payload.model_copy(update={
        'walls':CandidateCollection(state='partial',items=tuple(kept),truncated=payload.walls.truncated),
        'warnings':payload.warnings+warnings,'document_state':'partial'}).model_dump())


def _dash_corner(a, b, c, d, maximum_gap):
    """A short orthogonal turn with repeated-dash evidence on an arm."""
    if abs(a[1]-b[1])<=2 and abs(c[0]-d[0])<=2:
        corner=(round((c[0]+d[0])/2),round((a[1]+b[1])/2))
    elif abs(a[0]-b[0])<=2 and abs(c[1]-d[1])<=2:
        corner=(round((a[0]+b[0])/2),round((c[1]+d[1])/2))
    else:
        return None
    i=min(range(2),key=lambda i:math.dist((a,b)[i],corner))
    j=min(range(2),key=lambda i:math.dist((c,d)[i],corner))
    return (i,j,corner) if max(math.dist((a,b)[i],corner),math.dist((c,d)[j],corner))<=maximum_gap else None


def _contained_trace(a, b, c, d, tolerance):
    """Suppress duplicate Hough subsets, not separate parallel branches."""
    axis=np.asarray(d,float)-np.asarray(c,float)
    length=float(np.linalg.norm(axis))
    if not length:
        return False
    axis/=length
    normal=np.array([-axis[1],axis[0]])
    return (max(abs(float((np.asarray(p)-c)@normal)) for p in (a,b))<=tolerance
            and all(-tolerance<=float((np.asarray(p)-c)@axis)<=length+tolerance for p in (a,b)))


def _regular_dash_evidence(samples, maximum_gap):
    """Repeated visible dashes, never a single erased/missing stroke."""
    transitions = np.flatnonzero(np.r_[True,samples[1:] != samples[:-1],True])
    lengths = np.diff(transitions)
    states = samples[transitions[:-1]]
    gaps = lengths[~states]
    strokes = lengths[states]
    if len(gaps)<2 or len(strokes)<3 or not .35<=float(samples.mean())<.95:
        return False
    # Endpoint clipping may shorten the first/last dash; compare interior ink.
    interior = strokes[1:-1] if len(strokes)>2 else strokes
    return bool(min(gaps)>=2 and max(gaps)<=maximum_gap
                and max(gaps)<=min(gaps)*2.5 and min(interior)>=4
                and max(interior)<=min(interior)*3)


def _dash_span(samples, maximum_gap):
    """Keep the longest supported dash sequence, excluding border/text tails."""
    edges=np.flatnonzero(np.r_[True,samples[1:]!=samples[:-1],True])
    strokes=[(int(a),int(b)) for a,b in zip(edges,edges[1:]) if samples[a]]
    if not 3<=len(strokes)<=64:
        return None
    best=None
    for i in range(len(strokes)-2):
        for j in range(i+2,len(strokes)):
            a,b=strokes[i][0],strokes[j][1]
            if best is not None and b-a<=best[1]-best[0]:
                continue
            if _regular_dash_evidence(samples[a:b],maximum_gap):
                best=(a,b)
    return best


def _near_box(point, bounds, tolerance):
    x, y = point
    return (bounds.x - tolerance <= x <= bounds.x + bounds.width + tolerance
            and bounds.y - tolerance <= y <= bounds.y + bounds.height + tolerance)


def _near_port(point, symbol, direction, tolerance):
    """Centre-axis contact, not arbitrary edges of an elongated fixture.

    Grid lines brushing fixture tips are not independent branches. Real strokes
    along either centre axis remain eligible; this never classifies a device.
    """
    bounds=symbol.bounds
    if not _near_box(point,bounds,tolerance):
        return False
    short_edge=min(bounds.width,bounds.height)
    if abs(direction[0])>=abs(direction[1]):
        return abs(point[1]-symbol.center.y)<=max(4,short_edge*.5)
    return abs(point[0]-symbol.center.x)<=max(4,short_edge*.5)


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
    """Find device-anchored strokes on the original pre-annotation source raster.

    Symbol bounds only anchor fragments; overlays are never source ink. Repeated
    dashed ink can support a partial trace; a missing stroke cannot. Curves,
    elevations and circuit topology remain unresolved.
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
        return payload if payload.observed_routes.connections else with_device_contact_evidence(payload, image_rgb)
    # A valid normalized page can exceed this extractor's working budget.
    # Keep symbol/wall processing successful instead of failing the whole job.
    if image_rgb.shape[0] * image_rgb.shape[1] > 12_000_000:
        value = payload.model_dump(mode="json")
        value["warnings"].append(CandidateWarning(code="automatic_wiring_budget", severity="warning",
            message="Automatic wiring exceeded its working limit; draw missing traces in the editor.").model_dump())
        return FloorPlanInterpretationPayload.model_validate(value)
    regions = [region for region in payload.regions if region.kind == "plan_region"]
    symbols = [symbol for symbol in payload.symbols.items if symbol.bounds is not None
               and not re.search(r"home.?run|circuit.*notation",
                   (symbol.training_legend.name if symbol.training_legend else symbol.observed_label) or "", re.I)]
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
    for symbol in payload.symbols.items:
        bounds = symbol.bounds
        if bounds is None:
            continue
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
    dash_gap = max(8,min(64,round(min(width,height)*.035)))
    dashed = cv2.HoughLinesP(search,1,math.pi/180,max(8,round(minimum*.7)),
                            minLineLength=minimum,maxLineGap=dash_gap)
    if dashed is not None:
        rows = sorted(set(rows) | {tuple(map(int,line[0])) for line in dashed},
                      key=lambda row: (-math.hypot(row[2]-row[0],row[3]-row[1]),row))
    truncated = len(rows) > 4096
    selected = []
    support = cv2.dilate(ink, np.ones((3, 3), np.uint8))
    dashed_selected = False
    for x1, y1, x2, y2 in rows[:4096]:
        a, b = (x1, y1), (x2, y2)
        if b < a:
            a, b = b, a
        # Sample the dominant source-pixel axis, not Hough's slight raster wobble.
        if abs(a[0]-b[0])<=padding+5:
            a,b=(round((a[0]+b[0])/2),a[1]),(round((a[0]+b[0])/2),b[1])
        elif abs(a[1]-b[1])<=padding+5:
            a,b=(a[0],round((a[1]+b[1])/2)),(b[0],round((a[1]+b[1])/2))
        # Glyph masking may cut an endpoint short, but nearby annotations must
        # not become device anchors merely because they share a room.
        anchor_tolerance=padding+4+min(16,dash_gap//2)
        anchors_a = {symbol.id for symbol in symbols if _near_box(a, symbol.bounds, anchor_tolerance)}
        anchors_b = {symbol.id for symbol in symbols if _near_box(b, symbol.bounds, anchor_tolerance)}
        pairs = {tuple(sorted((left, right))) for left in anchors_a for right in anchors_b if left != right}
        count = math.ceil(math.dist(a, b)) + 1
        xs = np.rint(np.linspace(a[0], b[0], count)).astype(int)
        ys = np.rint(np.linspace(a[1], b[1], count)).astype(int)
        samples = support[ys,xs]>0
        regular_dashes = not samples.all() and _regular_dash_evidence(samples,dash_gap)
        if not regular_dashes and not samples.all():
            span=_dash_span(samples,dash_gap)
            if span:
                low,high=span
                a,b=(int(xs[low]),int(ys[low])),(int(xs[high-1]),int(ys[high-1]))
                samples=samples[low:high]
                anchors_a={s.id for s in symbols if _near_box(a,s.bounds,anchor_tolerance)}
                anchors_b={s.id for s in symbols if _near_box(b,s.bounds,anchor_tolerance)}
                pairs={tuple(sorted((left,right))) for left in anchors_a for right in anchors_b if left!=right}
                regular_dashes=True
        if math.dist(a,b)<max(24,minimum*2):
            continue
        if samples.all() and math.dist(a,b)<32:
            continue
        if not regular_dashes and _parallel_wall((a,b),payload.walls.items,padding*4+4):
            continue
        # A single gap or irregular missing span cannot become a connection.
        if not samples.all() and not regular_dashes:
            continue
        direction=(b[0]-a[0],b[1]-a[1])
        anchors_a={s.id for s in symbols if _near_port(a,s,direction,anchor_tolerance)}
        anchors_b={s.id for s in symbols if _near_port(b,s,direction,anchor_tolerance)}
        pairs={tuple(sorted((left,right))) for left in anchors_a for right in anchors_b if left!=right}
        if not pairs and not regular_dashes and not (anchors_a or anchors_b):
            continue
        if any(_contained_trace(a,b,c,d,padding+5)
               for c,d,_,_,_ in selected):
            continue
        selected.append((a,b,pairs,regular_dashes,anchors_a|anchors_b))
        dashed_selected |= regular_dashes
        if len(selected)>=256:
            truncated=True
            break
    # One arm of a bent dashed route need not have a device at its corner.
    # Keep supported partial arms; a regular one-ended trace is not a proven
    # connection. This is observed geometry, never inferred circuit topology.
    parents=list(range(len(selected)))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]]
            i=parents[i]
        return i
    turns=[]
    for i,(a,b,_,regular,_) in enumerate(selected):
        for j,(c,d,_,other_regular,other_anchors) in enumerate(selected[:i]):
            turn=_dash_corner(a,b,c,d,dash_gap) if regular or other_regular else None
            if regular and other_regular and selected[i][4]&other_anchors:
                parents[root(i)]=root(j)
            if turn:
                parents[root(i)]=root(j)
                turns.append((i,j,turn))
    anchors={}
    for i,(_,_,_,_,ids) in enumerate(selected):
        anchors.setdefault(root(i),set()).update(ids)
    dashed_groups={root(i) for i,row in enumerate(selected) if row[3]}
    eligible={i for i,(_,_,pairs,_,_) in enumerate(selected)
              if pairs or (selected[i][3] and root(i) in dashed_groups and len(anchors[root(i)])>=2)
              or (selected[i][3] and selected[i][4])}
    endpoints={i:[row[0],row[1]] for i,row in enumerate(selected)}
    for i,j,(a_end,b_end,corner) in turns:
        if i in eligible and j in eligible:
            endpoints[i][a_end]=corner
            endpoints[j][b_end]=corner
    selected=[(*endpoints[i],row[2],root(i) in dashed_groups) for i,row in enumerate(selected) if i in eligible
              and endpoints[i][0]!=endpoints[i][1]]
    fixture_rows, fixture_truncated = fixture_axis_traces(
        payload, image_rgb, scope, dash_validator=_regular_dash_evidence)
    if fixture_rows is not None:
        # Global Hough votes favour repeated ceiling grids. On fixture-rich
        # drawings use the bounded, source-supported axis search. Validate real
        # repeated dashes there too: Hough corner grouping alone cannot turn
        # interrupted grid/text strokes into a longer observed route.
        selected = [row for row in fixture_rows
                    if row[3] or not _parallel_wall(row[:2], payload.walls.items, padding * 4 + 4)]
        dashed_selected = any(row[3] for row in selected)
        truncated |= fixture_truncated
    truncated = truncated or len(selected) > maximum_segments
    segments = []
    for index, (a, b, _, dashed_line) in enumerate(sorted(selected[:maximum_segments]), 1):
        refs = tuple(sorted(f"region:{region.id}" for region in regions
                            if _near_box(a, region.bounds, 0) and _near_box(b, region.bounds, 0)))
        if not refs:
            continue
        segments.append(ObservedRouteSegment(id=f"segment-{index:04d}",
                        points=(PixelPoint(x=a[0], y=a[1]), PixelPoint(x=b[0], y=b[1])),
                        line_style="dashed" if dashed_line else "solid",
                        evidence_refs=refs, ambiguity="ambiguous"))
    value = payload.model_dump(mode="json")
    if value["document_state"] == "completed":
        value["document_state"] = "partial"
    value["observed_routes"] = ObservedRoutes(state="partial", segments=tuple(segments),
                                               connections=(), truncated=truncated).model_dump()
    value["warnings"].append(CandidateWarning(code="automatic_visible_wiring", severity="info",
        message="Drawing traces are editable; gaps, circuit connections and heights remain unresolved.").model_dump())
    if dashed_selected:
        value["warnings"].append(CandidateWarning(code="regular_dashed_wiring",severity="info",
            message="Repeated dashed ink supports partial trace proposals, not confirmed circuit connections.").model_dump())
    return with_device_contact_evidence(FloorPlanInterpretationPayload.model_validate(value), image_rgb)
