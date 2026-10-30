"""Unmeasured A* draft paths. Never observations, circuits, or takeoff inputs."""
import math
import re
from time import monotonic

from app.routing.astar import astar
from app.routing.graph import RoutingError


def _closest(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((point[0]-a[0])*dx + (point[1]-a[1])*dy) / (dx*dx+dy*dy))) if dx or dy else 0
    return (round(a[0]+t*dx, 6), round(a[1]+t*dy, 6))


def _segments(wire):
    points = [(p["x"], p["y"]) for p in wire["points"]]
    return list(zip(points, points[1:]))


def _contact(a, b, c, d):
    """Literal geometric contact, not crossing/junction or circuit evidence."""
    epsilon = 1e-5
    if any(max(min(a[i], b[i]), min(c[i], d[i])) >
           min(max(a[i], b[i]), max(c[i], d[i])) + epsilon for i in (0, 1)):
        return False
    if any(math.dist(p, _closest(p, x, y)) <= epsilon
           for p, x, y in ((a,c,d), (b,c,d), (c,a,b), (d,a,b))):
        return True
    # Interior crossings are not junction evidence. This helper describes only
    # geometric continuity; circuit membership must still be explicit.
    return False


def _wire_components(wires):
    """Geometric draft runs at the same height, NOT electrical circuits."""
    parents = list(range(len(wires)))
    methods=[{w.get("installation_method","unknown")}-{"unknown"} for w in wires]
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    segments = [_segments(w) for w in wires]
    for i, wire in enumerate(wires):
        for j in range(i):
            if root(i) == root(j) or wire.get("elevation_meters") != wires[j].get("elevation_meters"):
                continue
            combined=methods[root(i)]|methods[root(j)]
            if len(combined)>1:
                continue
            if any(_contact(a,b,c,d) for a,b in segments[i] for c,d in segments[j]):
                parents[root(i)] = root(j)
                methods[root(j)]=combined
    groups = {}
    for i in range(len(wires)):
        groups.setdefault(root(i), []).append(i)
    return list(groups.values())


def _inherit_trace_types(existing, observed):
    result=[dict(w) for w in existing]
    active=observed+[w for w in result if w.get("disposition")!="rejected"]
    if len(active)>256 or sum(len(w["points"])-1 for w in active)>512:
        return result
    for group in _wire_components(active):
        metadata=_wire_type([active[i] for i in group if i<len(observed)])
        if metadata:
            for i in group:
                if i>=len(observed) and active[i].get("installation_method","unknown")=="unknown":
                    active[i].update(metadata)
    return result


def _wire_type(wires):
    typed=[w for w in wires if w.get("installation_method","unknown")!="unknown"]
    if len({w["installation_method"] for w in typed})!=1:
        return {}
    wire=typed[0]
    return {key:wire[key] for key in ("line_style","installation_method","wiring_legend_id","wiring_legend_name") if key in wire}


def _suggest_plan_placement(routes, observed, regions):
    """Placement suggestion only, never a circuit or connectivity assignment.

    Vote inside the proposal's own plan region. Mixed sheets cannot borrow a
    majority from another drawing. Reviewed/edited routes remain authoritative.
    """
    plans = [r.bounds for r in regions if r.kind == 'plan_region']
    def inside(point, bounds):
        return bounds.x <= point['x'] <= bounds.x+bounds.width and bounds.y <= point['y'] <= bounds.y+bounds.height
    result = []
    for route in routes:
        if (route.get('disposition') != 'unresolved' or route.get('suppression_reason')
            or route.get('installation_method','unknown') != 'unknown'):
            result.append(route); continue
        matches = [b for b in plans if all(inside(p,b) for p in route['points'])]
        if len(matches) != 1:
            result.append(route); continue
        votes = {}
        for wire in observed:
            method = wire.get('installation_method','unknown')
            if (wire.get('disposition') != 'rejected' and not wire.get('suppression_reason')
                and method in ('concealed_in_ceiling','concealed_under_floor')
                and all(inside(p,matches[0]) for p in wire['points'])):
                votes[method] = votes.get(method,0)+1
        ranked = sorted(votes,key=votes.get,reverse=True)
        if ranked and (len(ranked)==1 or votes[ranked[0]]>votes[ranked[1]]):
            method = ranked[0]
            route = {**route,'installation_method':method,'line_style':'dashed' if method=='concealed_under_floor' else 'solid'}
        result.append(route)
    return result


def _prune_redundant(existing, observed):
    """Recoverably suppress automatic cycles, never edited/manual paths.

    Both endpoints must already share a literal-contact network containing an
    observed trace at the same height/type. Remove longest cycles first and
    recheck after each removal so connectivity cannot be lost.
    """
    result=[dict(w) for w in existing]
    if len(observed)+len(result)>256 or sum(len(w["points"])-1 for w in observed+result)>512:
        return result
    for index in sorted(range(len(result)),key=lambda i:-sum(math.dist(a,b) for a,b in _segments(result[i]))):
        wire=result[index]
        if wire.get("disposition")!="unresolved" or wire.get("elevation_meters") is not None:
            continue
        others=observed+[w for i,w in enumerate(result) if i!=index and w.get("disposition")!="rejected"]
        ends=[(p["x"],p["y"]) for p in (wire["points"][0],wire["points"][-1])]
        for group in _wire_components(others):
            if not any(i<len(observed) for i in group):
                continue
            if any(others[i].get("elevation_meters")!=wire.get("elevation_meters") for i in group):
                continue
            methods={w.get("installation_method","unknown") for w in [wire,*[others[i] for i in group]]}-{"unknown"}
            if len(methods)>1:
                continue
            if all(any(math.dist(p,_closest(p,a,b))<=1e-5 for i in group for a,b in _segments(others[i])) for p in ends):
                result[index]={**wire,"disposition":"rejected","suppression_reason":"redundant_observed_connection"}
                break
    return result


def _component_joins(wires, symbols, regions, walls, clearances, removed_devices, deadline):
    """Append wall-safe A* joins between exact device anchors on separate runs.

    Respect deliberate removals, explicit heights, and drawing boundaries.
    Existing paths remain byte-for-byte unchanged; no conductor assignment inferred.
    """
    groups = _wire_components(wires)
    failed = set()
    while len(groups) > 1 and monotonic() < deadline:
        anchors = []
        for group_index, group in enumerate(groups):
            # Do not guess how to connect explicit/underground elevations.
            if any(wires[i].get("elevation_meters") is not None for i in group):
                continue
            if any(identity in removed_devices and any(
                    math.dist(point, _closest(point,a,b)) <= 1e-5
                    for i in group for a,b in _segments(wires[i]))
                   for identity,point,_ in symbols):
                # An alternate endpoint must not silently bypass a removed join.
                continue
            for identity, point, _ in symbols:
                if identity not in removed_devices and any(
                        math.dist(point, _closest(point,a,b)) <= 1e-5
                        for i in group for a,b in _segments(wires[i])):
                    anchors.append((identity, point, group_index))
        choices = sorted((math.dist(p,q), identity, other, p, q, g, h)
            for n,(identity,p,g) in enumerate(anchors)
            for other,q,h in anchors[:n] if g != h and tuple(sorted((identity,other))) not in failed)
        panel_ids={identity for identity,_,panel in symbols if panel}
        panel_groups={g for identity,_,g in anchors if identity in panel_ids}
        # One detected panel is the network root, not a separate star wire to
        # every outlet. Multiple panels require an explicit circuit assignment.
        if len(panel_ids)>1:
            break
        if len(panel_groups)==1:
            root_group=next(iter(panel_groups))
            choices=[choice for choice in choices if root_group in choice[-2:]]
        joined = False
        for _, identity, other, point, goal, g, h in choices:
            if monotonic() >= deadline:
                break
            failed.add(tuple(sorted((identity,other))))
            region = next((r for r in regions if all(
                r.x <= p["x"] <= r.x+r.width and r.y <= p["y"] <= r.y+r.height
                for i in groups[g]+groups[h] for p in wires[i]["points"])), None)
            if not region:
                continue
            methods={wires[i].get("installation_method","unknown") for i in groups[g]+groups[h]}-{"unknown"}
            if len(methods)>1:
                continue
            try:
                points = draft_path(point, goal, (region.x,region.y,region.x+region.width,region.y+region.height),
                    walls, endpoint_clearances=(clearances[identity],clearances[other]))
            except RoutingError:
                continue
            if len(wires) >= 256 or sum(len(w["points"])-1 for w in wires)+len(points)-1 > 512:
                return  # joining must not expand beyond the bounded geometry set
            wire = {"disposition":"unresolved", "points":[{"x":x,"y":y} for x,y in points],
                    "completeness":"partial", "elevation_meters":None, "algorithm":"astar",
                    "source_device_id":identity, "target_id":other, "target_kind":"device"}
            wire.update(_wire_type([wires[i] for i in groups[g]+groups[h]]))
            yield wire
            wires.append(wire)
            groups = _wire_components(wires)
            joined = True
            break
        if not joined:
            break


def _blocked(a, b, wall, endpoints, clearances=(0,0)):
    """Intersect an edge with the wall band; permit only local endpoint exits."""
    c, d, half = wall
    length = math.dist(c, d)
    if not length:
        return False
    ux, uy = (d[0]-c[0])/length, (d[1]-c[1])/length
    local = lambda p: ((p[0]-c[0])*ux+(p[1]-c[1])*uy, -(p[0]-c[0])*uy+(p[1]-c[1])*ux)
    p, q = local(a), local(b)
    lo, hi = 0., 1.
    for axis, low, high in ((0, -half, length+half), (1, -half, half)):
        delta = q[axis]-p[axis]
        if not delta:
            if not low <= p[axis] <= high:
                return False
        else:
            t1, t2 = sorted(((low-p[axis])/delta, (high-p[axis])/delta))
            lo, hi = max(lo, t1), min(hi, t2)
            if lo > hi:
                return False
    hits = [(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])) for t in (lo, hi)]
    return not any(math.dist(endpoint, _closest(endpoint, c, d)) <= half+2+clearance
                   and all(math.dist(hit, endpoint) <= half+3+clearance for hit in hits)
                   for endpoint,clearance in zip(endpoints,clearances))


def draft_path(start, goal, bounds, walls, *, endpoint_clearances=(0,0)):
    """Shortest orthogonal path on a bounded source-pixel grid, or NO_ROUTE."""
    left, top, right, bottom = bounds
    if not all(left <= p[0] <= right and top <= p[1] <= bottom for p in (start, goal)) or start == goal:
        raise RoutingError("NO_ROUTE")
    # Try the complete set of zero/one-bend Manhattan paths with the SAME A*
    # and wall-band predicate first. A reachable path achieves the Manhattan
    # lower bound, so a dense grid cannot make it shorter. If both bends are
    # blocked, retain the existing obstacle-routing grid (never cross a wall).
    corners=sorted({start,goal,(start[0],goal[1]),(goal[0],start[1])})
    direct={p:[] for p in corners}
    for i,a in enumerate(corners):
        for b in corners[:i]:
            if (a[0]==b[0] or a[1]==b[1]) and not any(
                    _blocked(a,b,wall,(start,goal),endpoint_clearances) for wall in walls):
                cost=math.dist(a,b)
                direct[a].append((b,cost)); direct[b].append((a,cost))
    try:
        return astar(direct,start,goal,lambda a,b: abs(a[0]-b[0])+abs(a[1]-b[1]))
    except RoutingError:
        pass
    xs = sorted({start[0], goal[0], *(round(left+(right-left)*i/24, 6) for i in range(25))})
    ys = sorted({start[1], goal[1], *(round(top+(bottom-top)*i/24, 6) for i in range(25))})
    graph = {(x,y): [] for x in xs for y in ys}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            a = (x,y)
            for b in ([(xs[i+1],y)] if i+1 < len(xs) else []) + ([(x,ys[j+1])] if j+1 < len(ys) else []):
                if not any(_blocked(a,b,wall,(start,goal),endpoint_clearances) for wall in walls):
                    cost = math.dist(a,b)
                    graph[a].append((b,cost)); graph[b].append((a,cost))
    path = astar(graph,start,goal,lambda a,b: abs(a[0]-b[0])+abs(a[1]-b[1]))
    simplified = []
    for point in path:
        if len(simplified) >= 2 and (simplified[-2][0] == simplified[-1][0] == point[0]
                                    or simplified[-2][1] == simplified[-1][1] == point[1]):
            simplified[-1] = point
        else:
            simplified.append(point)
    return simplified


def generate_draft_wiring(candidate, review=None, *, maximum_devices=64, budget_seconds=3,
                          legacy_completion=False):
    """Preserve saved proposals without inferring connectivity on load/save.

    ``legacy_completion`` is an explicit opt-in for the old benchmark only.
    It must not be enabled by ordinary review retrieval or draft persistence.

    Anchor selection is a visual nearest-anchor heuristic, NOT circuit inference.
    No path leaves its plan region, crosses a wall band, or invents a remote panel.
    Saved generated paths (including removal tombstones) are never regenerated.
    Newly added/classified devices can receive additional, separately saved paths.
    Disconnected unmeasured runs are joined at device anchors without inferring circuits.
    """
    payload = candidate.payload
    from app.ai.floor_plan_interpretation.reviewed_reference import has_manual_wiring_replacement
    if has_manual_wiring_replacement(review):
        # An explicit manual replacement is not permission to reconnect separate
        # annotated branches or regenerate every removed automatic path.
        return list(review.get('generated_wiring', [])), [
            'Saved drawing-specific wiring replaces automatic paths.']
    regions = [r.bounds for r in payload.regions if r.kind == "plan_region"]
    saved_symbols = {s["id"]: s for s in (review or {}).get("symbols", [])}
    symbols, unknown = [], []
    clearances = {}
    candidates = {s.id:s for s in payload.symbols.items}
    identities = saved_symbols if review is not None and "symbols" in review else candidates
    for identity in identities:
        symbol = candidates.get(identity)
        saved = saved_symbols.get(identity, {})
        if saved.get("disposition") == "rejected":
            continue
        label = saved.get("class_name") or (
            (symbol.training_legend.name if symbol.training_legend else symbol.observed_label) if symbol else "") or ""
        if re.search(r"home.?run|circuit.*notation", label, re.I):
            continue
        if saved.get("class_id") is None and not re.search(
                r"lamp|light|troffer|fluorescent|switch|outlet|receptacle|socket|panel|distribution board|detector|smoke|alarm|bell|horn|sounder|pull station|call point|data port|connection port|camera|keypad|contact|breaker|meter|service entrance|push button|pull box|utility box|junction box|fan", label, re.I):
            unknown.append(identity)
            continue
        p = saved.get("center") or {"x":symbol.center.x, "y":symbol.center.y}
        symbols.append((identity,(p["x"],p["y"]),bool(re.search(r"panel|distribution board",label,re.I))))
        # A wall-device glyph may be drawn slightly off its wall centerline.
        # Permit only a local glyph-sized attachment, never an entire wall pass.
        clearances[identity] = min(40,12+min(symbol.bounds.width,symbol.bounds.height)/2) if (
            symbol and symbol.bounds and re.search(r"switch|outlet|receptacle|socket|panel|distribution board|pull station|call point|data port|connection port",label,re.I)) else 0
    wires = (review or {}).get("observed_wiring")
    if wires is None:
        wires = [{"id":w.id,"points":[p.model_dump() for p in w.points]} for w in payload.observed_routes.segments]
    wires = [w for w in wires if w.get("disposition") != "rejected"]
    existing = list((review or {}).get("generated_wiring", []))
    # Loading/saving a review must not invent branches for moved/added devices,
    # splice unrelated circuits, or erase prior edited routing. Observed ink
    # remains editable with unresolved topology. A* is an independent proposal
    # source, not evidence that a device touches a particular drawing trace.
    if not legacy_completion:
        from app.routing.homerun_proposals import propose
        existing, homerun_notes = propose(candidate, review, existing, budget_seconds=min(1,budget_seconds))
        existing = _inherit_trace_types(existing, wires)
        if payload.observed_routes.recovery is not None:
            from app.routing.geometric_draft import propose_geometric_drafts
            result, notes = propose_geometric_drafts(candidate,review,symbols,wires,existing,clearances,budget_seconds=budget_seconds)
            return _suggest_plan_placement(_inherit_trace_types(result,wires),wires,payload.regions), homerun_notes + notes
        return _suggest_plan_placement(existing,wires,payload.regions), homerun_notes + (["Observed wiring connectivity is unresolved unless explicitly attached. No proximity-based A* joins were added."] if wires else [])
    existing = _prune_redundant(_inherit_trace_types(existing, wires), wires)
    active = wires + [w for w in existing if w.get("disposition") != "rejected"]
    touches = lambda p: any(math.dist(p,_closest(p,(a["x"],a["y"]),(b["x"],b["y"]))) <= 1e-5
        for w in active for a,b in zip(w["points"],w["points"][1:]))
    protected = {identity for w in existing for identity in (
        w["source_device_id"],w["target_id"] if w["target_kind"]=="device" else None)
        if not w.get("suppression_reason")}
    notes = ["Device type needed for automatic wiring: "+", ".join(sorted(unknown))] if unknown else []
    walls = (review or {}).get("walls")
    if walls is None:
        walls = [w.model_dump() for w in payload.walls.items]
    # Keep graph work bounded; do not route with silently dropped obstacles.
    if len(walls)>128 or len(wires)>256 or not regions:
        return existing, notes + ["Automatic draft routing needs a bounded drawing region and wall/trace set."]
    bands = [((w["start"]["x"],w["start"]["y"]),(w["end"]["x"],w["end"]["y"]),
              max(2,float(w.get("estimated_thickness_pixels") or 6)/2)) for w in walls if w.get("disposition") != "rejected"]
    result, missing = existing, []
    last_id = max((int(w["id"].rsplit("-",1)[1]) for w in existing), default=0)
    served = set()
    deadline = monotonic()+budget_seconds
    for identity, point, is_panel in sorted(symbols)[:maximum_devices]:
        if identity in served:
            continue
        if touches(point):
            continue
        if identity in protected:
            missing.append(identity)
            continue
        region = next((r for r in regions if r.x<=point[0]<=r.x+r.width and r.y<=point[1]<=r.y+r.height),None)
        if not region:
            missing.append(identity); continue
        bounds = (region.x,region.y,region.x+region.width,region.y+region.height)
        within = lambda p: bounds[0]<=p[0]<=bounds[2] and bounds[1]<=p[1]<=bounds[3]
        targets = []
        for wire in wires:
            for a,b in zip(wire["points"],wire["points"][1:]):
                q = _closest(point,(a["x"],a["y"]),(b["x"],b["y"]))
                if within(q):
                    targets.append((0,math.dist(point,q),wire["id"],"visible_trace",q))
        if any(t[1]<=1e-5 for t in targets):
            continue
        for other,q,panel in symbols:
            if other != identity and within(q):
                targets.append((1 if panel and not is_panel else 2,math.dist(point,q),other,"device",q))
        found = False
        # Distinct deterministic anchors, visible evidence first. No direct fallback.
        ordered = sorted(set(targets))
        # Failed nearby traces must not starve reachable panel/device anchors.
        choices = [t for t in ordered if t[0]==0][:2] + [t for t in ordered if t[0]==1][:1] + [t for t in ordered if t[0]==2][:2]
        for _,distance,target_id,target_kind,goal in choices:
            if monotonic() >= deadline or len(result)>=2048 or last_id>=9999:
                break
            if not distance:
                continue
            try:
                points = draft_path(point,goal,bounds,bands,endpoint_clearances=(
                    clearances[identity],clearances.get(target_id,0) if target_kind=="device" else 0))
            except RoutingError:
                continue
            last_id += 1
            metadata=_wire_type([w for w in wires if w["id"]==target_id]) if target_kind=="visible_trace" else {}
            result.append({"id":f"manual-route-{last_id:04d}","disposition":"unresolved",
                           "points":[{"x":x,"y":y} for x,y in points],"completeness":"partial",
                           "elevation_meters":None,"algorithm":"astar","source_device_id":identity,
                           "target_id":target_id,"target_kind":target_kind,**metadata})
            served.add(identity)
            if target_kind == "device":
                served.add(target_id)
            found = True; break
        if not found:
            missing.append(identity)
    if len(symbols)>maximum_devices:
        missing.extend(s[0] for s in sorted(symbols)[maximum_devices:])
    # Report actual final coverage, including moved devices and saved removals.
    active = wires + [w for w in result if w.get("disposition") != "rejected"]
    missing = [identity for identity,p,_ in symbols if not touches(p)]
    # A covered device is not proof that its branch joins the rest of the draft.
    # Bound pairwise segment work separately from the bounded A* grids.
    if len(active) <= 256 and sum(len(w["points"])-1 for w in active) <= 512:
        removed_devices = {identity for w in existing if w.get("disposition") == "rejected" and not w.get("suppression_reason")
                           for identity in (w["source_device_id"],w["target_id"])}
        for wire in _component_joins(active, sorted(symbols)[:maximum_devices], regions, bands,
                                     clearances, removed_devices, deadline):
            if len(result) >= 2048 or last_id >= 9999:
                break
            last_id += 1
            result.append({"id":f"manual-route-{last_id:04d}", **wire})
        groups = _wire_components(active)
        has_anchor=[any(math.dist(p,_closest(p,a,b))<=1e-5
                        for _,p,_ in symbols for i in group for a,b in _segments(active[i])) for group in groups]
        anchored=sum(has_anchor)
        if anchored > 1:
            notes.append(f"Disconnected draft wiring: {anchored} device-anchored runs remain (blocked, removed, "
                         "different heights, missing device anchors, or routing budget).")
        orphan_observations=sum(not found and any(i<len(wires) for i in group)
                                for found,group in zip(has_anchor,groups))
        if orphan_observations:
            notes.append(f"Unattached drawing traces: {orphan_observations} fragments have no exact device anchor; "
                         "preserved for correction, not invented as connected branches.")
    else:
        notes.append("Draft wiring joins exceeded the bounded trace/segment limit.")
    result=_prune_redundant(_inherit_trace_types(result,wires),wires)
    if sum(panel for _,_,panel in symbols)>1:
        notes.append("Multiple panelboards: circuit assignment is needed before joining their networks.")
    return result, notes + (["Unwired draft devices: "+", ".join(sorted(missing))] if missing else [])
