"""Bounded planning preview for one explicitly assigned service circuit.

Greedily attach the closest unconnected target to the existing service tree.
This is a graph heuristic, not a proof of global conduit/wire optimality or
electrical design approval. No circuit membership, height or installation type
is inferred, and this preview does not publish quantities or change layouts.
"""
from heapq import heappop, heappush
import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.routing.contracts import (
    Contract, Connector, Endpoint, FloorConfig, Number, Obstacle, Point, RoutingRequest, Segment,
)
from app.routing.engine import (attachment, segment, service_graph, validate_target, world_point,
                                validate_service_elevations, vertical_kind)
from app.routing.graph import RoutingError


class CircuitPlanningRequest(Contract):
    routing_mode: Literal['shared_circuit', 'missing_devices'] = 'shared_circuit'
    circuit_id: Annotated[str, Field(min_length=1, max_length=80, strict=True)]
    installation_method: Literal['ceiling_service', 'underground']
    floor_passages_confirmed: Annotated[bool, Field(strict=True)] = False
    floors: Annotated[list[FloorConfig], Field(min_length=1, max_length=8)]
    panel: Endpoint
    targets: Annotated[list[Endpoint], Field(min_length=1, max_length=32)]
    connectors: Annotated[list[Connector], Field(max_length=32)] = []
    obstacles: Annotated[list[Obstacle], Field(max_length=128)] = []
    grid_step_meters: Annotated[float, Field(ge=0.1, le=5, allow_inf_nan=False)]
    alignment_confirmed: Literal[True]
    purpose: Literal['planning'] = 'planning'

    @model_validator(mode='after')
    def references(self):
        if not self.circuit_id.strip():
            raise ValueError('A circuit identifier is required.')
        identities = [(target.floor_id, target.symbol_id) for target in self.targets]
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate circuit targets.')
        for target in self.targets:
            self.single_target(target)  # Existing alignment/reference validation.
        return self

    def single_target(self, target):
        return RoutingRequest(floors=self.floors, panel=self.panel, target=target,
                              installation_method=self.installation_method,
                              floor_passages_confirmed=self.floor_passages_confirmed,
                              connectors=self.connectors, obstacles=self.obstacles,
                              grid_step_meters=self.grid_step_meters,
                              alignment_confirmed=self.alignment_confirmed, purpose=self.purpose)


class CircuitBranch(Contract):
    floor_id: int
    symbol_id: str
    points: list[Point]
    segment_indices: list[int]
    horizontal_meters: Number
    vertical_meters: Number
    total_meters: Number


class CircuitTargetIssue(Contract):
    floor_id: int
    symbol_id: str
    reason: str


class CircuitSaveRequest(CircuitPlanningRequest):
    intent: Literal['save_planning_circuit']
    expected_route_version: Annotated[int, Field(strict=True, ge=0)]
    request_id: UUID


class CircuitPlanningResult(Contract):
    circuit_id: str
    installation_method: Literal['ceiling_service', 'underground']
    provenance: Literal['generated'] = 'generated'
    algorithm: Literal['greedy_shared_service_tree_v1', 'assigned_missing_device_astar_v1'] = 'greedy_shared_service_tree_v1'
    optimality: Literal['graph_heuristic_not_global_optimum'] = 'graph_heuristic_not_global_optimum'
    status: Literal['preview_not_saved'] = 'preview_not_saved'
    segments: list[Segment]
    branches: list[CircuitBranch]
    skipped_targets: list[CircuitTargetIssue] = []
    unresolved_targets: list[CircuitTargetIssue] = []
    # Unique physical path length, NOT a conductor count or material takeoff.
    horizontal_meters: Number
    vertical_meters: Number
    total_meters: Number


class SavedCircuitResult(CircuitPlanningResult):
    status: Literal['saved_planning'] = 'saved_planning'


def _nearest_path(graph, sources, targets):
    """Deterministic multi-source Dijkstra; every iteration is bounded by graph size."""
    if len(graph) > 40000:
        raise RoutingError('GRAPH_RESOURCE_LIMIT')
    if not sources.issubset(graph) or not targets.issubset(graph):
        raise RoutingError('NO_ROUTE')
    queue = [(0, node) for node in sorted(sources)]
    costs, parents = {node: 0 for node in sources}, {}
    # All initial costs are equal and sources are sorted: the list is a heap.
    while queue:
        cost, node = heappop(queue)
        if cost != costs[node]:
            continue
        if node in targets:
            path = [node]
            while node in parents:
                node = parents[node]
                path.append(node)
            return path[::-1]
        for neighbor, weight in graph[node]:
            if not math.isfinite(weight) or weight < 0:
                raise RoutingError('INVALID_GRAPH_WEIGHT')
            proposed = cost + weight
            if proposed < costs.get(neighbor, math.inf):
                costs[neighbor], parents[neighbor] = proposed, node
                heappush(queue, (proposed, neighbor))
    raise RoutingError('NO_ROUTE')


def plan_circuit(request: CircuitPlanningRequest, documents):
    validate_service_elevations(request, documents)
    configs = {config.floor_id: config for config in request.floors}
    panel_drop = attachment(request.panel, configs[request.panel.floor_id],
                            documents[request.panel.floor_id], request.obstacles, request.installation_method)
    target_drops = []
    for target in request.targets:
        validate_target(request.single_target(target), documents)
        target_drops.append(attachment(target, configs[target.floor_id],
                           documents[target.floor_id], request.obstacles, request.installation_method))
    graph, connectors, configs = service_graph(request, documents, (request.panel, *request.targets))
    root = (request.panel.floor_id, request.panel.x, request.panel.y)
    pending = {(target.floor_id, target.x, target.y) for target in request.targets}
    if root not in graph or not pending.issubset(graph):
        raise RoutingError('NO_ROUTE')
    tree, parents = {root}, {}
    while pending - tree:
        path = _nearest_path(graph, tree, pending - tree)
        for a, b in zip(path, path[1:]):
            parents[b] = a
            tree.add(b)

    segments, identities = [], {}

    def add(a, b, kind, connector=None):
        def key(point):
            return (point.floor_id, point.x, point.y, point.elevation_meters)
        identity = tuple(sorted((key(a), key(b))))
        if identity not in identities:
            identities[identity] = len(segments)
            segments.append(segment(a, b, kind, connector))
        return identities[identity]

    root_point = world_point(root, configs)
    # Split overlapping endpoint legs at explicit elevations and floor passages.
    # Exact endpoint-pair dedup alone would double-count a 3->2 run inside 3->1.
    levels = {}
    for endpoint, drop in ((request.panel, panel_drop), *zip(request.targets, target_drops)):
        if drop is not None:
            key = (drop.floor_id, drop.x, drop.y)
            levels.setdefault(key, set()).update((drop.elevation_meters,
                                                 configs[endpoint.floor_id].service_elevation_meters))
            if request.installation_method == 'underground':
                levels[key].add(documents[endpoint.floor_id].floor.elevation_meters)

    def vertical_path(a, b):
        key = (a.floor_id, a.x, a.y)
        low, high = sorted((a.elevation_meters, b.elevation_meters))
        middle = sorted((value for value in levels[key] if low < value < high),
                        reverse=a.elevation_meters > b.elevation_meters)
        points = [a, *(Point(floor_id=a.floor_id, x=a.x, y=a.y, elevation_meters=value)
                       for value in middle), b]
        return points, [add(first, last, vertical_kind(first, last, request.installation_method,
                           documents[first.floor_id].floor.elevation_meters))
                        for first, last in zip(points, points[1:])]

    panel_points, panel_indices = [], []
    if panel_drop is not None:
        panel_points, panel_indices = vertical_path(panel_drop, root_point)
    # Insertion order follows the deterministic rooted tree, not request order.
    edge_indices = {}
    for b, a in parents.items():
        edge_indices[(a, b)] = add(world_point(a, configs), world_point(b, configs),
                                  'riser' if a[0] != b[0] else request.installation_method, connectors.get((a, b)))

    branches = []
    for target, drop in zip(request.targets, target_drops):
        node = (target.floor_id, target.x, target.y)
        path = [node]
        while node in parents:
            node = parents[node]
            path.append(node)
        path.reverse()
        points = [world_point(node, configs) for node in path]
        indices = [edge_indices[(a, b)] for a, b in zip(path, path[1:])]
        if panel_indices:
            points = panel_points[:-1] + points
            indices = panel_indices + indices
        if drop is not None:
            drop_points, drop_indices = vertical_path(points[-1], drop)
            indices.extend(drop_indices)
            points.extend(drop_points[1:])
        horizontal = sum(segments[index].horizontal_meters for index in indices)
        vertical = sum(segments[index].vertical_meters for index in indices)
        branches.append(CircuitBranch(floor_id=target.floor_id, symbol_id=target.symbol_id,
                         points=points, segment_indices=indices, horizontal_meters=horizontal,
                         vertical_meters=vertical, total_meters=horizontal+vertical))
    if not segments:
        raise RoutingError('ZERO_LENGTH_ROUTE')
    horizontal = sum(item.horizontal_meters for item in segments)
    vertical = sum(item.vertical_meters for item in segments)
    return CircuitPlanningResult(circuit_id=request.circuit_id, installation_method=request.installation_method,
                                 segments=segments, branches=branches, horizontal_meters=horizontal,
                                 vertical_meters=vertical, total_meters=horizontal+vertical)
