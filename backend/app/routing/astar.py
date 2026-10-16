from heapq import heappop, heappush
from itertools import count
import math

from app.routing.graph import RoutingError


def astar(graph, start, goal, heuristic=lambda a, b: 0):
    """A* with deterministic tie-breaking; zero heuristic is valid for any graph."""
    return astar_to_any(graph, start, {goal}, lambda node: heuristic(node, goal))


def astar_to_any(graph, start, goals, heuristic=lambda node: 0):
    """Lowest permitted edge cost to one eligible graph node (not global design).

    No bend penalty is configured in this graph. If one is introduced, the
    search state must also include incoming direction, not just position.
    """
    goals = set(goals)
    if start not in graph or not goals or not goals.issubset(graph):
        raise RoutingError("NO_ROUTE")
    order = count()
    queue = [(heuristic(start), next(order), 0, start)]
    costs, parents = {start: 0}, {}
    while queue:
        _, _, cost, node = heappop(queue)
        if cost != costs[node]:
            continue
        if node in goals:
            path = [node]
            while node in parents:
                node = parents[node]
                path.append(node)
            return path[::-1]
        for neighbor, weight in graph[node]:
            if not math.isfinite(weight) or weight < 0:
                raise RoutingError("INVALID_GRAPH_WEIGHT")
            proposed = cost + weight
            if proposed < costs.get(neighbor, math.inf):
                costs[neighbor], parents[neighbor] = proposed, node
                heappush(queue, (proposed + heuristic(neighbor), next(order), proposed, neighbor))
    raise RoutingError("NO_ROUTE")
