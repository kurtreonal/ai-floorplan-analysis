import math

from app.routing.astar import astar
from app.routing.contracts import Point, RouteResult, Segment
from app.routing.graph import RoutingError, floor_graph


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


def generate_route(request, documents):
    validate_target(request, documents)
    if len(request.floors) != 1:
        raise RoutingError("CONNECTOR_REQUIRED")
    config = request.floors[0]
    if any(endpoint.elevation_meters != config.service_elevation_meters for endpoint in (request.panel, request.target)):
        raise RoutingError("WALL_ATTACHMENT_REQUIRED")
    start = (request.panel.x, request.panel.y)
    end = (request.target.x, request.target.y)
    graph = floor_graph(documents[config.floor_id], config, [start, end], request.grid_step_meters, request.obstacles)
    path = astar(graph, start, end, lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1]))
    points = [Point(floor_id=config.floor_id, x=x + config.offset_x, y=y + config.offset_y,
                    elevation_meters=config.service_elevation_meters) for x, y in path]
    return result([segment(a, b, "ceiling_service") for a, b in zip(points, points[1:])])
