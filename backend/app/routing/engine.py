import math

from app.routing.astar import astar
from app.routing.contracts import Point, RouteResult, Segment
from app.routing.graph import RoutingError, floor_graph, intersects, structural_boxes


def segment(start, end, kind, connector_id=None):
    horizontal = math.hypot(end.x - start.x, end.y - start.y)
    vertical = abs(end.elevation_meters - start.elevation_meters)
    if horizontal and vertical:
        raise RoutingError("NON_ORTHOGONAL_ROUTE")
    return Segment(start=start, end=end, kind=kind, connector_id=connector_id,
                   horizontal_meters=horizontal, vertical_meters=vertical)


def result(segments):
    if not segments:
        raise RoutingError("ZERO_LENGTH_ROUTE")
    horizontal = sum(s.horizontal_meters for s in segments)
    vertical = sum(s.vertical_meters for s in segments)
    return RouteResult(points=[segments[0].start, *(s.end for s in segments)], segments=segments,
                       horizontal_meters=horizontal, vertical_meters=vertical, total_meters=horizontal + vertical)


def validate_target(request, documents):
    target = request.target
    symbol = next((s for s in documents[target.floor_id].symbols if s.id == target.symbol_id), None)
    if symbol is None or not math.isclose(symbol.position.x, target.x, abs_tol=1e-9) or not math.isclose(symbol.position.y, target.y, abs_tol=1e-9):
        raise RoutingError("TARGET_MUST_MATCH_SAVED_SYMBOL")


def attachment(endpoint, config, document, obstacles):
    service = config.service_elevation_meters
    if endpoint.elevation_meters == service:
        return None
    wall = next((w for w in document.walls if w.id == endpoint.wall_id), None)
    if wall is None or wall.status != 'verified' or not wall.height_meters or not wall.thickness_meters:
        raise RoutingError("WALL_ATTACHMENT_REQUIRED")
    if not document.floor.elevation_meters <= endpoint.elevation_meters <= document.floor.elevation_meters + wall.height_meters:
        raise RoutingError("ENDPOINT_OUTSIDE_WALL_HEIGHT")
    dx, dy = wall.end.x-wall.start.x, wall.end.y-wall.start.y
    length2 = dx*dx + dy*dy
    if length2 == 0:
        raise RoutingError("WALL_ATTACHMENT_REQUIRED")
    t = max(0, min(1, ((endpoint.x-wall.start.x)*dx + (endpoint.y-wall.start.y)*dy)/length2))
    if math.hypot(endpoint.x-wall.start.x-t*dx, endpoint.y-wall.start.y-t*dy) > wall.thickness_meters/2 + 1e-9:
        raise RoutingError("ENDPOINT_NOT_ON_WALL")
    low, high = sorted((endpoint.elevation_meters, service))
    for obstacle in obstacles:
        if obstacle.floor_id == endpoint.floor_id and low <= obstacle.top and high >= obstacle.bottom:
            if intersects((endpoint.x, endpoint.y), (endpoint.x, endpoint.y),
                          (obstacle.min_x, obstacle.min_y, obstacle.max_x, obstacle.max_y)):
                raise RoutingError("NO_ROUTE")
    return Point(floor_id=endpoint.floor_id, x=endpoint.x + config.offset_x,
                 y=endpoint.y + config.offset_y, elevation_meters=endpoint.elevation_meters)


def generate_route(request, documents):
    validate_target(request, documents)
    configs = {c.floor_id: c for c in request.floors}
    panel = attachment(request.panel, configs[request.panel.floor_id], documents[request.panel.floor_id], request.obstacles)
    target = attachment(request.target, configs[request.target.floor_id], documents[request.target.floor_id], request.obstacles)
    graph, connector_edges = {}, {}
    for config in request.floors:
        anchors = [(e.x, e.y) for e in (request.panel, request.target) if e.floor_id == config.floor_id]
        anchors += [(c.x-config.offset_x, c.y-config.offset_y) for c in request.connectors
                    if config.floor_id in (c.from_floor_id, c.to_floor_id)]
        local = floor_graph(documents[config.floor_id], config, anchors, request.grid_step_meters, request.obstacles)
        for (x, y), edges in local.items():
            graph[(config.floor_id, x, y)] = [((config.floor_id, p[0], p[1]), cost) for p, cost in edges]
        if len(graph) > 40000:
            raise RoutingError("GRAPH_RESOURCE_LIMIT")
    for connector in request.connectors:
        first, last = (configs[connector.from_floor_id], configs[connector.to_floor_id])
        a = (first.floor_id, connector.x-first.offset_x, connector.y-first.offset_y)
        b = (last.floor_id, connector.x-last.offset_x, connector.y-last.offset_y)
        low, high = sorted((first.service_elevation_meters, last.service_elevation_meters))
        if low == high:
            raise RoutingError("INVALID_RISER_ELEVATION")
        blocked = False
        for config in request.floors:
            point = (connector.x-config.offset_x, connector.y-config.offset_y)
            document = documents[config.floor_id]
            # Check any structural intersection across the riser's height span.
            for wall in document.walls:
                if wall.height_meters and low <= document.floor.elevation_meters + wall.height_meters and high >= document.floor.elevation_meters:
                    boxes = structural_boxes(document, max(low, document.floor.elevation_meters))
                    blocked |= any(intersects(point, point, box) for box in boxes)
            for o in request.obstacles:
                if o.floor_id == config.floor_id and low <= o.top and high >= o.bottom:
                    blocked |= intersects(point, point, (o.min_x, o.min_y, o.max_x, o.max_y))
        if a in graph and b in graph and not blocked:
            graph[a].append((b, high-low))
            graph[b].append((a, high-low))
            connector_edges[(a, b)] = connector_edges[(b, a)] = connector.id
    def world(node):
        floor_id, x, y = node
        config = configs[floor_id]
        return Point(floor_id=floor_id, x=x+config.offset_x, y=y+config.offset_y,
                     elevation_meters=config.service_elevation_meters)
    def heuristic(a, b):
        a, b = world(a), world(b)
        return abs(a.x-b.x) + abs(a.y-b.y) + abs(a.elevation_meters-b.elevation_meters)
    start = (request.panel.floor_id, request.panel.x, request.panel.y)
    end = (request.target.floor_id, request.target.x, request.target.y)
    path = astar(graph, start, end, heuristic)
    points = [world(node) for node in path]
    segments = [segment(points[i], points[i+1], "riser" if a[0] != b[0] else "ceiling_service",
                        connector_edges.get((a, b))) for i, (a, b) in enumerate(zip(path, path[1:]))]
    if panel:
        segments.insert(0, segment(panel, points[0], "wall_rise" if panel.elevation_meters < points[0].elevation_meters else "wall_drop"))
    if target:
        segments.append(segment(points[-1], target, "wall_drop" if target.elevation_meters < points[-1].elevation_meters else "wall_rise"))
    return result(segments)
