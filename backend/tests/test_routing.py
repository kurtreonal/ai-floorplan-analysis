import pytest
from pydantic import ValidationError

from app.routing.contracts import RoutingRequest
import json
from pathlib import Path
from app.geometry import canonical_geometry_from_dict
from app.routing.graph import floor_graph, RoutingError
from app.routing.astar import astar
from app.routing.engine import generate_route


def document():
    data = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/canonical_geometry_v1.json').read_text())
    data['walls'] = []
    return canonical_geometry_from_dict(data)


def request_data():
    return dict(
        floors=[dict(floor_id=2, expected_layout_version=1, service_elevation_meters=3, offset_x=0, offset_y=0)],
        panel=dict(floor_id=2, x=1, y=1, elevation_meters=3),
        target=dict(floor_id=2, symbol_id="detected:501", x=2.5, y=1.5, elevation_meters=3),
        grid_step_meters=1, alignment_confirmed=True,
    )


def test_contract_requires_explicit_alignment_and_finite_heights():
    data = request_data()
    assert RoutingRequest.model_validate(data).purpose == "planning"
    for field, value in [("alignment_confirmed", False), ("grid_step_meters", float("nan"))]:
        with pytest.raises(ValidationError):
            RoutingRequest.model_validate({**data, field: value})


def test_contract_rejects_duplicate_and_unknown_floor_references():
    data = request_data()
    with pytest.raises(ValidationError):
        RoutingRequest.model_validate({**data, "floors": data["floors"] * 2})
    with pytest.raises(ValidationError):
        RoutingRequest.model_validate({**data, "target": {**data["target"], "floor_id": 9}})


def test_graph_preserves_exact_anchors_and_is_deterministic():
    config = RoutingRequest.model_validate(request_data()).floors[0]
    graph = floor_graph(document(), config, [(0.17, 0.21)], 1)
    assert (0.17, 0.21) in graph
    assert graph == floor_graph(document(), config, [(0.17, 0.21)], 1)
    assert all(a[0] == b[0] or a[1] == b[1] for a, edges in graph.items() for b, _ in edges)


def test_graph_blocks_thin_obstacle_between_grid_nodes():
    from app.routing.contracts import Obstacle
    config = RoutingRequest.model_validate(request_data()).floors[0]
    obstacle = Obstacle(floor_id=2, min_x=0.4, max_x=0.6, min_y=-1, max_y=6, bottom=0, top=4)
    graph = floor_graph(document(), config, [], 1, [obstacle])
    assert not any(a[0] < .4 and b[0] > .6 for a, edges in graph.items() for b, _ in edges)


def test_graph_rejects_unbounded_work():
    config = RoutingRequest.model_validate(request_data()).floors[0]
    with pytest.raises(RoutingError, match='RESOURCE_LIMIT'):
        floor_graph(document(), config, [], 0.001)


def test_astar_known_shortest_path_and_disconnected_graph():
    graph = {'a': [('b', 10), ('c', 1)], 'c': [('b', 1)], 'b': [('d', 2)], 'd': [], 'e': []}
    assert astar(graph, 'a', 'd') == ['a', 'c', 'b', 'd']
    assert astar(graph, 'a', 'a') == ['a']
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        astar(graph, 'a', 'e')


def test_astar_detours_around_obstacle_without_diagonal_shortcut():
    from app.routing.contracts import Obstacle
    config = RoutingRequest.model_validate(request_data()).floors[0]
    obstacle = Obstacle(floor_id=2, min_x=1.4, max_x=1.6, min_y=0, max_y=2, bottom=0, top=4)
    graph = floor_graph(document(), config, [(1, 1), (2, 1)], 1, [obstacle])
    path = astar(graph, (1, 1), (2, 1), lambda a, b: abs(a[0]-b[0])+abs(a[1]-b[1]))
    assert max(p[1] for p in path) >= 3
    assert sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a, b in zip(path, path[1:])) == 5


def test_service_route_uses_explicit_elevation_and_saved_target():
    request = RoutingRequest.model_validate(request_data())
    route = generate_route(request, {2: document()})
    assert route.total_meters == 2
    assert route.vertical_meters == 0
    assert all(s.kind == 'ceiling_service' and s.start.elevation_meters == 3 for s in route.segments)
    assert route.provenance == 'generated'
    data = request_data()
    data['target']['x'] = 5
    with pytest.raises(RoutingError, match='SAVED_SYMBOL'):
        generate_route(RoutingRequest.model_validate(data), {2: document()})


def wall_document():
    data = document().to_dict()
    data['walls'] = [dict(id=1, source_candidate_id=None, processing_job_id=None, status='verified',
        start=dict(x=0,y=1.5), end=dict(x=5,y=1.5), length_meters=5, angle_degrees=0,
        height_meters=3, thickness_meters=.2)]
    return canonical_geometry_from_dict(data)


def test_wall_drop_contributes_to_backend_length():
    data = request_data()
    data['target'].update(elevation_meters=0, wall_id=1)
    route = generate_route(RoutingRequest.model_validate(data), {2: wall_document()})
    assert route.segments[-1].kind == 'wall_drop'
    assert route.vertical_meters == 3
    assert route.total_meters == 5


def test_vertical_endpoint_requires_real_wall_attachment():
    data = request_data()
    data['panel'].update(elevation_meters=0, wall_id=1)
    with pytest.raises(RoutingError, match='NOT_ON_WALL'):
        generate_route(RoutingRequest.model_validate(data), {2: wall_document()})


def multi_floor():
    data = request_data()
    data['floors'].append(dict(floor_id=3, expected_layout_version=1, service_elevation_meters=6, offset_x=1, offset_y=0))
    data['target'].update(floor_id=3, elevation_meters=6)
    data['connectors'] = [dict(id='riser-a', from_floor_id=2, to_floor_id=3, x=2, y=1)]
    second = document().to_dict()
    second['floor'].update(project_floor_id=3, elevation_meters=1.5)
    return data, {2: document(), 3: canonical_geometry_from_dict(second)}


def test_multifloor_requires_explicit_connector_and_counts_height():
    data, documents = multi_floor()
    route = generate_route(RoutingRequest.model_validate(data), documents)
    riser = next(s for s in route.segments if s.kind == 'riser')
    assert riser.connector_id == 'riser-a'
    assert (riser.start.floor_id, riser.end.floor_id) == (2, 3)
    assert riser.start.x == riser.end.x == 2
    assert route.vertical_meters == 3
    assert route.horizontal_meters == 3
    assert route.total_meters == 6
    data['connectors'] = []
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        generate_route(RoutingRequest.model_validate(data), documents)


def test_riser_obstacle_blocks_vertical_shortcut():
    data, documents = multi_floor()
    data['obstacles'] = [dict(floor_id=2, min_x=1.9, max_x=2.1, min_y=.9, max_y=1.1, bottom=4, top=5)]
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        generate_route(RoutingRequest.model_validate(data), documents)


def circuit_inputs():
    from app.routing.circuit import CircuitPlanningRequest
    data = request_data()
    geometry = document().to_dict()
    template = geometry['symbols'][0]
    positions = [(2.5, 1.5), (4, 1.5), (4, 3)]
    geometry['symbols'] = [{**template, 'id': f'detected:{501+i}', 'source_record_id': 501+i,
                            'position': {'x': x, 'y': y}} for i, (x, y) in enumerate(positions)]
    targets = [{**data['target'], 'symbol_id': item['id'], **item['position']} for item in geometry['symbols']]
    data.pop('target')
    return CircuitPlanningRequest(circuit_id='C-LGT', installation_method='ceiling_service',
                                  targets=targets, **data), {2: canonical_geometry_from_dict(geometry)}


def test_circuit_tree_shares_trunks_and_does_not_claim_global_optimality():
    from app.routing.circuit import plan_circuit
    request, documents = circuit_inputs()
    before = request.model_dump(), documents[2].to_dict()
    network = plan_circuit(request, documents)
    assert network.total_meters == 5
    assert [branch.total_meters for branch in network.branches] == [2, 3.5, 5]
    assert sum(branch.total_meters for branch in network.branches) > network.total_meters
    assert network.status == 'preview_not_saved'
    assert network.optimality == 'graph_heuristic_not_global_optimum'
    assert all(s.start.x == s.end.x or s.start.y == s.end.y for s in network.segments)
    assert plan_circuit(request, documents) == network
    assert (request.model_dump(), documents[2].to_dict()) == before
    for target, branch in zip(request.targets, network.branches):
        assert (branch.points[-1].x, branch.points[-1].y) == (target.x, target.y)


def test_circuit_requires_explicit_membership_method_and_supported_targets():
    from app.routing.circuit import CircuitPlanningRequest, plan_circuit
    request, documents = circuit_inputs()
    data = request.model_dump()
    for change in ({'targets': []}, {'targets': data['targets'] * 2},
                   {'installation_method': 'underground'}, {'circuit_id': ' '},
                   {'targets': [data['targets'][0]] * 33}, {'alignment_confirmed': False}):
        with pytest.raises(ValidationError):
            CircuitPlanningRequest.model_validate({**data, **change})
    data['targets'][0]['x'] = 3
    with pytest.raises(RoutingError, match='SAVED_SYMBOL'):
        plan_circuit(CircuitPlanningRequest.model_validate(data), documents)


def test_circuit_disconnection_returns_no_partial_network_or_diagonal_fallback():
    from app.routing.circuit import CircuitPlanningRequest, plan_circuit
    request, documents = circuit_inputs()
    data = request.model_dump()
    data['obstacles'] = [dict(floor_id=2, min_x=3.1, max_x=3.2, min_y=-1,
                             max_y=20, bottom=0, top=4)]
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        plan_circuit(CircuitPlanningRequest.model_validate(data), documents)


def test_circuit_counts_wall_drops_once_and_keeps_device_branch_lengths():
    from app.routing.circuit import CircuitPlanningRequest, plan_circuit
    request, documents = circuit_inputs()
    data = request.model_dump()
    geometry = documents[2].to_dict()
    geometry['walls'] = wall_document().to_dict()['walls']
    data['targets'] = [{**target, 'elevation_meters': 0, 'wall_id': 1} for target in data['targets'][:2]]
    network = plan_circuit(CircuitPlanningRequest.model_validate(data), {2: canonical_geometry_from_dict(geometry)})
    assert network.vertical_meters == 6
    assert network.horizontal_meters == 3.5
    assert network.total_meters == 9.5
    assert [branch.vertical_meters for branch in network.branches] == [3, 3]
    assert sum(s.kind == 'wall_drop' for s in network.segments) == 2


def test_circuit_shared_riser_preserves_explicit_offsets_and_connector_identity():
    from app.routing.circuit import CircuitPlanningRequest, plan_circuit
    data, documents = multi_floor()
    first_target = {**data['target'], 'floor_id': 2, 'elevation_meters': 3}
    data['targets'] = [first_target, data.pop('target')]
    network = plan_circuit(CircuitPlanningRequest(circuit_id='C-R', installation_method='ceiling_service', **data), documents)
    assert network.vertical_meters == 3
    assert sum(s.kind == 'riser' for s in network.segments) == 1
    riser = next(s for s in network.segments if s.kind == 'riser')
    assert riser.start.x == riser.end.x == 2
    assert riser.connector_id == 'riser-a'
    data['connectors'] = []
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        plan_circuit(CircuitPlanningRequest(circuit_id='C-R', installation_method='ceiling_service', **data), documents)


def test_circuit_search_is_bounded_and_rejects_invalid_edge_weights():
    from app.routing.circuit import _nearest_path
    a, b = (2, 0, 0), (2, 1, 0)
    for weight in (-1, float('nan')):
        with pytest.raises(RoutingError, match='INVALID_GRAPH_WEIGHT'):
            _nearest_path({a: [(b, weight)], b: []}, {a}, {b})
    with pytest.raises(RoutingError, match='GRAPH_RESOURCE_LIMIT'):
        _nearest_path({(2, i, 0): [] for i in range(40001)}, {a}, {b})


def test_circuit_overlapping_colocated_drops_are_split_without_double_counting():
    from app.routing.circuit import CircuitPlanningRequest, plan_circuit
    request, documents = circuit_inputs()
    data = request.model_dump()
    geometry = documents[2].to_dict()
    geometry['walls'] = wall_document().to_dict()['walls']
    geometry['symbols'][1]['position'] = geometry['symbols'][0]['position'].copy()
    data['targets'] = [{**target, **geometry['symbols'][0]['position'], 'elevation_meters': height, 'wall_id': 1}
                       for target, height in zip(data['targets'][:2], (0, 1))]
    network = plan_circuit(CircuitPlanningRequest.model_validate(data), {2: canonical_geometry_from_dict(geometry)})
    assert network.vertical_meters == 3  # union 3->0, not 3->0 plus 3->1
    assert [branch.vertical_meters for branch in network.branches] == [3, 2]
    assert len(set(network.branches[0].segment_indices) & set(network.branches[1].segment_indices)) > 0
