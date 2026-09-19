"""Bounded orthogonal graph, derived exclusively from metric canonical layouts."""
import math


class RoutingError(ValueError):
    pass


def intersects(a, b, box):
    """Closed segment/AABB slab test, including thin obstacles between nodes."""
    lo, hi = 0.0, 1.0
    for axis in range(2):
        delta = b[axis] - a[axis]
        minimum, maximum = box[axis], box[axis + 2]
        if abs(delta) < 1e-12:
            if a[axis] < minimum or a[axis] > maximum:
                return False
        else:
            first, last = sorted(((minimum - a[axis]) / delta, (maximum - a[axis]) / delta))
            lo, hi = max(lo, first), min(hi, last)
            if lo > hi:
                return False
    return True


def structural_boxes(document, elevation):
    boxes = []
    for wall in document.walls:
        if wall.status != "verified" or wall.height_meters is None or wall.thickness_meters is None:
            raise RoutingError("WALL_REVIEW_REQUIRED")
        if document.floor.elevation_meters <= elevation <= document.floor.elevation_meters + wall.height_meters:
            half = wall.thickness_meters / 2
            # Conservative bounds: diagonal walls may exclude extra space, never
            # allow a path through a structure based on a missed intersection.
            boxes.append((min(wall.start.x, wall.end.x) - half, min(wall.start.y, wall.end.y) - half,
                          max(wall.start.x, wall.end.x) + half, max(wall.start.y, wall.end.y) + half))
    return boxes


def floor_graph(document, config, anchors, step, obstacles=()):
    width = document.coordinate_system.width_meters
    height = document.coordinate_system.height_meters
    if config.service_elevation_meters <= document.floor.elevation_meters:
        raise RoutingError("INVALID_SERVICE_ELEVATION")
    nx, ny = math.ceil(width / step), math.ceil(height / step)
    if nx > 10000 or ny > 10000 or (nx + 1) * (ny + 1) > 20000:
        raise RoutingError("GRAPH_RESOURCE_LIMIT")
    if any(not (0 <= x <= width and 0 <= y <= height) for x, y in anchors):
        raise RoutingError("ENDPOINT_OUTSIDE_FLOOR")
    xs = sorted({0.0, width, *(min(i * step, width) for i in range(nx + 1)), *(p[0] for p in anchors)})
    ys = sorted({0.0, height, *(min(i * step, height) for i in range(ny + 1)), *(p[1] for p in anchors)})
    if len(xs) * len(ys) > 20000:
        raise RoutingError("GRAPH_RESOURCE_LIMIT")
    boxes = structural_boxes(document, config.service_elevation_meters)
    boxes += [(o.min_x, o.min_y, o.max_x, o.max_y) for o in obstacles
              if o.floor_id == config.floor_id and o.bottom <= config.service_elevation_meters <= o.top]
    graph = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            point = (x, y)
            if any(intersects(point, point, box) for box in boxes):
                continue
            graph[point] = []
            for dx, dy in ((-1, 0), (0, -1)):
                if i + dx < 0 or j + dy < 0:
                    continue
                other = (xs[i + dx], ys[j + dy])
                if other in graph and not any(intersects(point, other, box) for box in boxes):
                    distance = abs(x - other[0]) + abs(y - other[1])
                    graph[point].append((other, distance))
                    graph[other].append((point, distance))
    return graph
