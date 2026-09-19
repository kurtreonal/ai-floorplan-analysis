import math

from app.routing.astar import astar
from app.routing.contracts import Point, RouteResult, Segment
from app.routing.graph import RoutingError, floor_graph, intersects


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
    if len(request.floors) != 1:
        raise RoutingError("CONNECTOR_REQUIRED")
    config = request.floors[0]
    panel = attachment(request.panel, config, documents[config.floor_id], request.obstacles)
    target = attachment(request.target, config, documents[config.floor_id], request.obstacles)
    start = (request.panel.x, request.panel.y)
    end = (request.target.x, request.target.y)
    graph = floor_graph(documents[config.floor_id], config, [start, end], request.grid_step_meters, request.obstacles)
    path = astar(graph, start, end, lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1]))
    points = [Point(floor_id=config.floor_id, x=x + config.offset_x, y=y + config.offset_y,
                    elevation_meters=config.service_elevation_meters) for x, y in path]
    segments = [segment(a, b, "ceiling_service") for a, b in zip(points, points[1:])]
    if panel:
        segments.insert(0, segment(panel, points[0], "wall_rise" if panel.elevation_meters < points[0].elevation_meters else "wall_drop"))
    if target:
        segments.append(segment(points[-1], target, "wall_drop" if target.elevation_meters < points[-1].elevation_meters else "wall_rise"))
    return result(segments)
