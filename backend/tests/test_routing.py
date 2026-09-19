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
