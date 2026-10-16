import math

from app.routing.astar import astar, astar_to_any
from app.routing.contracts import Endpoint, Point, RouteResult, Segment
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


def attachment(endpoint, config, document, obstacles, installation_method="ceiling_service"):
    service = config.service_elevation_meters
    if endpoint.elevation_meters == service:
        return None
    if installation_method != "underground" or endpoint.elevation_meters > document.floor.elevation_meters:
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


def validate_service_elevations(request, documents):
    """Validate explicit depth before constructing any endpoint legs."""
    if request.installation_method == "underground":
        for config in request.floors:
            if config.service_elevation_meters >= documents[config.floor_id].floor.elevation_meters:
                raise RoutingError("INVALID_UNDERGROUND_ELEVATION")


def vertical_kind(start, end, installation_method, floor_elevation):
    direction = "rise" if end.elevation_meters > start.elevation_meters else "drop"
    underground = (installation_method == "underground"
                   and max(start.elevation_meters, end.elevation_meters) <= floor_elevation)
    return f"underground_{direction}" if underground else f"wall_{direction}"


def endpoint_segments(start, end, installation_method, floor_elevation):
    points = [start]
    low, high = sorted((start.elevation_meters, end.elevation_meters))
    if installation_method == "underground" and low < floor_elevation < high:
        points.append(Point(floor_id=start.floor_id, x=start.x, y=start.y,
                            elevation_meters=floor_elevation))
    points.append(end)
    return [segment(a, b, vertical_kind(a, b, installation_method, floor_elevation))
            for a, b in zip(points, points[1:])]


def service_graph(request, documents, endpoints):
    """One bounded service-plane graph with exact anchors for every endpoint."""
    configs = {c.floor_id: c for c in request.floors}
    graph, connector_edges = {}, {}
    for config in request.floors:
        anchors = [(e.x, e.y) for e in endpoints if e.floor_id == config.floor_id]
        anchors += [(c.x-config.offset_x, c.y-config.offset_y) for c in request.connectors
                    if config.floor_id in (c.from_floor_id, c.to_floor_id)]
        local = floor_graph(documents[config.floor_id], config, anchors, request.grid_step_meters,
                            request.obstacles, request.installation_method)
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
    return graph, connector_edges, configs


def world_point(node, configs):
    floor_id, x, y = node
    config = configs[floor_id]
    return Point(floor_id=floor_id, x=x+config.offset_x, y=y+config.offset_y,
                 elevation_meters=config.service_elevation_meters)


def generate_route(request, documents, *, service_sources=()):
    validate_target(request, documents)
    validate_service_elevations(request, documents)
    configs = {c.floor_id: c for c in request.floors}
    panel = attachment(request.panel, configs[request.panel.floor_id], documents[request.panel.floor_id], request.obstacles, request.installation_method)
    target = attachment(request.target, configs[request.target.floor_id], documents[request.target.floor_id], request.obstacles, request.installation_method)
    # Only the caller's version-matched SAME-circuit generated tree may supply
    # these anchors. Never discover circuit membership by nearest source ink.
    sources = tuple(sorted(set(service_sources), key=lambda p: (p.floor_id, p.x, p.y, p.elevation_meters)))
    anchors = []
    for point in sources:
        config = configs.get(point.floor_id)
        if config is None or point.elevation_meters != config.service_elevation_meters:
            raise RoutingError('INVALID_SERVICE_ATTACHMENT')
        anchors.append(Endpoint(floor_id=point.floor_id, x=point.x-config.offset_x,
                               y=point.y-config.offset_y, elevation_meters=point.elevation_meters))
    graph, connector_edges, configs = service_graph(request, documents, (request.panel, request.target, *anchors))
    def world(node):
        return world_point(node, configs)
    def heuristic(a, b):
        a, b = world(a), world(b)
        return abs(a.x-b.x) + abs(a.y-b.y) + abs(a.elevation_meters-b.elevation_meters)
    start = (request.panel.floor_id, request.panel.x, request.panel.y)
    end = (request.target.floor_id, request.target.x, request.target.y)
    if anchors:
        eligible = {(p.floor_id, p.x, p.y) for p in anchors} & graph.keys()
        if start in graph:
            eligible.add(start)
        # Reverse search finds the least NEW permitted length to this assigned
        # tree; zero heuristic is admissible for multiple targets/floors.
        path = list(reversed(astar_to_any(graph, end, eligible)))
    else:
        path = astar(graph, start, end, heuristic)
    points = [world(node) for node in path]
    segments = [segment(points[i], points[i+1], "riser" if a[0] != b[0] else request.installation_method,
                        connector_edges.get((a, b))) for i, (a, b) in enumerate(zip(path, path[1:]))]
    if panel and path[0] == start and not anchors:
        segments = endpoint_segments(panel, points[0], request.installation_method,
                                    documents[panel.floor_id].floor.elevation_meters) + segments
    if target:
        segments.extend(endpoint_segments(points[-1], target, request.installation_method,
                                          documents[target.floor_id].floor.elevation_meters))
    if not segments and anchors:
        # Explicit same-circuit assignment at an existing service-tree vertex:
        # persist the device binding, not an artificial zero-length cylinder.
        return RouteResult(points=points, segments=[], horizontal_meters=0,
                           vertical_meters=0, total_meters=0)
    return result(segments)
