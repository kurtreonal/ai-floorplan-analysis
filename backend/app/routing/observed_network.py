"""Explicit, version-pinned observed-network reuse; no nearest-circuit inference.

Only shared ENDPOINTS connect selected paths. Interior crossings are not
junctions. Existing source paths are read, never copied into generated output.
"""
import math
from bisect import bisect_left, bisect_right

from app.routing.contracts import Point
from app.routing.graph import RoutingError, intersects


def _key(point):
    return point.project_floor_id, point.x, point.y, point.elevation_meters


def assigned_observed_sources(request, documents, extensions):
    if not request.observed_route_assignments:
        return set()
    configs = {item.floor_id: item for item in request.floors}
    paths = []
    details = {}
    for assignment in request.observed_route_assignments:
        document, extension = documents[assignment.floor_id], extensions.get(assignment.floor_id)
        route = next((r for r in document.routes if r.id == assignment.route_id), None)
        detail = next((d for d in extension.route_details if d.route_id == assignment.route_id), None) if extension else None
        if route is None or detail is None or detail.route_kind != 'observed':
            raise RoutingError('OBSERVED_NETWORK_REFERENCE_REQUIRED')
        if getattr(detail, 'circuit_id', None) not in (None, request.circuit_id):
            raise RoutingError('OBSERVED_NETWORK_CIRCUIT_CONFLICT')
        details[assignment.floor_id, route.id] = detail
        if len(route.points) < 2 or any(p.project_floor_id != assignment.floor_id for p in route.points):
            raise RoutingError('OBSERVED_NETWORK_FLOOR_REVIEW_REQUIRED')
        for a, b in zip(route.points, route.points[1:]):
            low, high = sorted((a.elevation_meters, b.elevation_meters))
            if any(o.floor_id == assignment.floor_id and low <= o.top and high >= o.bottom
                   and intersects((a.x, a.y), (b.x, b.y), (o.min_x, o.min_y, o.max_x, o.max_y))
                   for o in request.obstacles):
                raise RoutingError('OBSERVED_NETWORK_OBSTACLE_CONFLICT')
        paths.append(route)
        if sum(len(path.points) for path in paths) > 4096:
            raise RoutingError('GRAPH_RESOURCE_LIMIT')

    # The entered physical panel endpoint must already belong to this reviewed
    # network. Do not add a fictional lead or rise to make selected ink usable.
    root = (request.panel.floor_id, request.panel.x, request.panel.y, request.panel.elevation_meters)
    reached = {root}
    reached_junctions = set()
    pending = list(paths)
    while pending:
        def contacts(route):
            return getattr(details[route.points[0].project_floor_id, route.id], 'junction_connections', None) or ()
        joined = [route for route in pending if _key(route.points[0]) in reached or _key(route.points[-1]) in reached
                  or any(c['junction_id'] in reached_junctions
                         or (route.points[0].project_floor_id, c['anchor']['x'], c['anchor']['y'], c['anchor']['elevation_meters']) in reached
                         for c in contacts(route))]
        if not joined:
            raise RoutingError('OBSERVED_NETWORK_PANEL_CONNECTION_REQUIRED')
        for route in joined:
            reached.update((_key(route.points[0]), _key(route.points[-1])))
            reached_junctions.update(c['junction_id'] for c in contacts(route))
            pending.remove(route)

    sources = set()
    axes = {}
    for floor, config in configs.items():
        document = documents[floor]
        for axis, limit in [('x', document.coordinate_system.width_meters), ('y', document.coordinate_system.height_meters)]:
            count = math.ceil(limit/request.grid_step_meters)
            if count > 10000:
                raise RoutingError('GRAPH_RESOURCE_LIMIT')
            values = {min(i*request.grid_step_meters, limit) for i in range(count+1)}
            values.update(getattr(t, axis) for t in request.targets if t.floor_id == floor)
            values.update(getattr(p, axis) for route in paths for p in route.points if p.project_floor_id == floor)
            axes[floor, axis] = sorted(values)
    def add(floor, x, y):
        config = configs[floor]
        sources.add(Point(floor_id=floor, x=x+config.offset_x, y=y+config.offset_y,
                          elevation_meters=config.service_elevation_meters))
        if len(sources) > 4096:
            raise RoutingError('GRAPH_RESOURCE_LIMIT')

    for route in paths:
        floor = route.points[0].project_floor_id
        config = configs[floor]
        for point in route.points:
            if point.elevation_meters == config.service_elevation_meters:
                add(floor, point.x, point.y)
        for a, b in zip(route.points, route.points[1:]):
            if a.elevation_meters != config.service_elevation_meters or b.elevation_meters != config.service_elevation_meters:
                continue
            # Intersections with this bounded orthogonal routing graph become
            # eligible attachment anchors, not newly inferred source junctions.
            if a.y == b.y and a.x != b.x:
                axis, fixed = 'x', a.y
            elif a.x == b.x and a.y != b.y:
                axis, fixed = 'y', a.x
            else:
                continue  # Angled observed paths remain intact; use their vertices.
            lo, hi = sorted((getattr(a, axis), getattr(b, axis)))
            values = axes[floor, axis]
            for value in values[bisect_left(values, lo):bisect_right(values, hi)]:
                add(floor, value if axis == 'x' else fixed, fixed if axis == 'x' else value)
    if not sources:
        raise RoutingError('OBSERVED_NETWORK_SERVICE_ELEVATION_REQUIRED')
    return sources


def observed_attachment(request, documents, point):
    """Reference the exact selected source span at a new branch's origin."""
    from app.routing.circuit import ObservedNetworkAttachment
    config = next(c for c in request.floors if c.floor_id == point.floor_id)
    x, y = point.x-config.offset_x, point.y-config.offset_y
    for assignment in sorted(request.observed_route_assignments, key=lambda a: (a.floor_id, a.route_id)):
        if assignment.floor_id != point.floor_id:
            continue
        route = next(r for r in documents[point.floor_id].routes if r.id == assignment.route_id)
        for index, (a, b) in enumerate(zip(route.points, route.points[1:])):
            if any((p.x, p.y, p.elevation_meters) == (x, y, point.elevation_meters) for p in (a, b)):
                return ObservedNetworkAttachment(floor_id=point.floor_id, route_id=route.id, segment_index=index, anchor=point)
            if a.elevation_meters != point.elevation_meters or b.elevation_meters != point.elevation_meters:
                continue
            dx, dy = b.x-a.x, b.y-a.y
            length2 = dx*dx+dy*dy
            if not length2:
                continue
            t = ((x-a.x)*dx+(y-a.y)*dy)/length2
            if 0 <= t <= 1 and math.hypot(x-a.x-t*dx, y-a.y-t*dy) <= 1e-9:
                return ObservedNetworkAttachment(floor_id=point.floor_id, route_id=route.id, segment_index=index, anchor=point)
    return None
