"""Explicit underground planning on the same metric routing and saved contracts."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.geometry import canonical_geometry_from_dict
from app.routing.circuit import (CircuitPlanningRequest, CircuitSaveRequest,
                                 SavedCircuitResult, plan_circuit)
from app.routing.contracts import RoutingRequest, RouteResult
from app.routing.engine import generate_route
from app.routing.graph import RoutingError, floor_graph


def geometry():
    data = json.loads((Path(__file__).resolve().parents[2]
                       / 'fixtures/canonical_geometry_v1.json').read_text())
    data['floor']['elevation_meters'] = 0
    data['walls'] = [dict(id=1, source_candidate_id=None, processing_job_id=None,
                         status='verified', start=dict(x=0, y=1.5),
                         end=dict(x=6.4, y=1.5), length_meters=6.4,
                         angle_degrees=0, height_meters=3, thickness_meters=.2)]
    data['symbols'] = [data['symbols'][0]]
    return canonical_geometry_from_dict(data)


def inputs():
    return dict(
        installation_method='underground', floor_passages_confirmed=True,
        floors=[dict(floor_id=2, expected_layout_version=1,
                     service_elevation_meters=-.5, offset_x=0, offset_y=0)],
        panel=dict(floor_id=2, x=1, y=1.5, elevation_meters=1.5, wall_id=1),
        target=dict(floor_id=2, symbol_id='detected:501', x=2.5, y=1.5,
                    elevation_meters=1, wall_id=1),
        grid_step_meters=1, alignment_confirmed=True)


@pytest.mark.parametrize('flag', [False, None, 'true', 1])
def test_underground_requires_explicit_boolean_passage_input(flag):
    with pytest.raises(ValidationError):
        RoutingRequest.model_validate({**inputs(), 'floor_passages_confirmed': flag})
    data = inputs()
    del data['floor_passages_confirmed']
    with pytest.raises(ValidationError, match='passage confirmation'):
        RoutingRequest.model_validate(data)


def test_underground_rejects_multifloor_and_implicit_risers():
    data = inputs()
    data['floors'].append({**data['floors'][0], 'floor_id': 3})
    with pytest.raises(ValidationError, match='one floor'):
        RoutingRequest.model_validate(data)
    data = inputs()
    data['connectors'] = [dict(id='unused', from_floor_id=2, to_floor_id=3, x=1, y=1)]
    with pytest.raises(ValidationError, match='no inter-floor connectors'):
        RoutingRequest.model_validate(data)


@pytest.mark.parametrize('elevation', [0, .001, 3])
def test_depth_is_strictly_below_saved_floor_and_graph_has_same_guard(elevation):
    data = inputs()
    data['floors'][0]['service_elevation_meters'] = elevation
    request = RoutingRequest.model_validate(data)
    with pytest.raises(RoutingError, match='INVALID_UNDERGROUND_ELEVATION'):
        generate_route(request, {2: geometry()})
    with pytest.raises(RoutingError, match='INVALID_UNDERGROUND_ELEVATION'):
        floor_graph(geometry(), request.floors[0], [], 1, installation_method='underground')


def test_underground_splits_wall_and_below_floor_legs_and_counts_each_once():
    request = RoutingRequest.model_validate(inputs())
    document = geometry()
    before = request.model_dump(), document.to_dict()
    route = generate_route(request, {2: document})
    assert route.horizontal_meters == 1.5
    assert route.vertical_meters == 3.5
    assert route.total_meters == 5
    assert [s.kind for s in route.segments if s.vertical_meters] == [
        'wall_drop', 'underground_drop', 'underground_rise', 'wall_rise']
    assert all(s.start.elevation_meters == s.end.elevation_meters == -.5
               for s in route.segments if s.horizontal_meters)
    assert all(s.start.x == s.end.x or s.start.y == s.end.y for s in route.segments)
    assert all(s.start.elevation_meters == s.end.elevation_meters or not s.horizontal_meters
               for s in route.segments)
    assert (request.model_dump(), document.to_dict()) == before
    assert RouteResult.model_validate_json(route.model_dump_json()) == route


@pytest.mark.parametrize('change,error', [
    ({'wall_id': None}, 'WALL_ATTACHMENT_REQUIRED'),
    ({'y': 1}, 'ENDPOINT_NOT_ON_WALL'),
    ({'elevation_meters': 3.1}, 'ENDPOINT_OUTSIDE_WALL_HEIGHT')])
def test_above_floor_endpoint_requires_verified_wall_and_valid_height(change, error):
    data = inputs()
    data['panel'].update(change)
    with pytest.raises(RoutingError, match=error):
        generate_route(RoutingRequest.model_validate(data), {2: geometry()})


def test_unreviewed_wall_geometry_still_blocks_underground_planning():
    data = geometry().to_dict()
    data['walls'][0]['status'] = 'detected'
    with pytest.raises(RoutingError, match='WALL_ATTACHMENT_REQUIRED'):
        generate_route(RoutingRequest.model_validate(inputs()),
                       {2: canonical_geometry_from_dict(data)})


def test_below_floor_endpoints_do_not_invent_wall_attachments():
    data = inputs()
    data['panel'].update(elevation_meters=-.25, wall_id=None)
    data['target'].update(elevation_meters=-.5, wall_id=None)
    route = generate_route(RoutingRequest.model_validate(data), {2: geometry()})
    assert route.vertical_meters == .25
    assert {s.kind for s in route.segments} == {'underground_drop', 'underground'}


def test_closed_obstacle_at_lower_plane_prevents_crossing():
    data = inputs()
    data['obstacles'] = [dict(floor_id=2, min_x=1.7, max_x=1.8, min_y=-1,
                             max_y=6, bottom=-.5, top=-.4)]
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        generate_route(RoutingRequest.model_validate(data), {2: geometry()})


@pytest.mark.parametrize('bottom,top', [(-.5, -.4), (0, .1), (1.5, 1.6)])
def test_vertical_passage_obstacles_are_closed_across_full_endpoint_span(bottom, top):
    data = inputs()
    data['obstacles'] = [dict(floor_id=2, min_x=.9, max_x=1.1, min_y=1.4,
                             max_y=1.6, bottom=bottom, top=top)]
    with pytest.raises(RoutingError, match='NO_ROUTE'):
        generate_route(RoutingRequest.model_validate(data), {2: geometry()})


def test_ceiling_default_retains_legacy_service_and_wall_kinds():
    data = inputs()
    del data['installation_method']
    del data['floor_passages_confirmed']
    data['floors'][0]['service_elevation_meters'] = 3
    request = RoutingRequest.model_validate(data)
    route = generate_route(request, {2: geometry()})
    assert request.installation_method == 'ceiling_service'
    assert request.floor_passages_confirmed is False
    assert route.horizontal_meters == 1.5
    assert route.vertical_meters == 3.5
    assert {s.kind for s in route.segments} == {'wall_rise', 'wall_drop', 'ceiling_service'}


def test_underground_uses_actual_floor_elevation_and_explicit_project_offsets():
    data = inputs()
    data['floors'][0].update(service_elevation_meters=2.5, offset_x=7, offset_y=-2)
    data['panel']['elevation_meters'] += 3
    data['target']['elevation_meters'] += 3
    document = geometry().to_dict()
    document['floor']['elevation_meters'] = 3
    route = generate_route(RoutingRequest.model_validate(data),
                           {2: canonical_geometry_from_dict(document)})
    assert route.horizontal_meters == 1.5
    assert route.vertical_meters == 3.5
    assert (route.points[0].x, route.points[0].y) == (8, -.5)
    assert (route.points[-1].x, route.points[-1].y) == (9.5, -.5)
    assert 3 in {point.elevation_meters for point in route.points}
    assert all(segment.start.elevation_meters == segment.end.elevation_meters == 2.5
               for segment in route.segments if segment.horizontal_meters)


def circuit_inputs():
    data = inputs()
    first = data.pop('target')
    data.update(circuit_id='C-UG', targets=[first, {**first, 'symbol_id': 'detected:502',
                                                 'elevation_meters': 2}])
    document = geometry().to_dict()
    document['symbols'].append({**document['symbols'][0], 'id': 'detected:502',
                                'source_record_id': 502})
    return data, {2: canonical_geometry_from_dict(document)}


def test_circuit_shared_vertical_union_is_split_at_floor_and_all_endpoints():
    data, documents = circuit_inputs()
    request = CircuitPlanningRequest.model_validate(data)
    before = request.model_dump(), documents[2].to_dict()
    network = plan_circuit(request, documents)
    assert network.installation_method == 'underground'
    assert network.horizontal_meters == 1.5
    assert network.vertical_meters == 4.5  # panel 2 + target union 2.5
    assert network.total_meters == 6
    assert [branch.vertical_meters for branch in network.branches] == [3.5, 4.5]
    assert {s.kind for s in network.segments} == {
        'wall_drop', 'wall_rise', 'underground_drop', 'underground_rise', 'underground'}
    assert len(set(network.branches[0].segment_indices) & set(network.branches[1].segment_indices)) > 0
    for segment in network.segments:
        if segment.kind.startswith('underground_'):
            assert max(segment.start.elevation_meters, segment.end.elevation_meters) <= 0
        if segment.kind.startswith('wall_'):
            assert min(segment.start.elevation_meters, segment.end.elevation_meters) >= 0
    assert (request.model_dump(), documents[2].to_dict()) == before
    single = request.single_target(request.targets[0])
    assert single.installation_method == 'underground'
    assert single.floor_passages_confirmed is True


def test_existing_saved_circuit_json_round_trip_preserves_method_and_passage_input():
    data, documents = circuit_inputs()
    request = CircuitSaveRequest.model_validate({**data, 'intent': 'save_planning_circuit',
        'expected_route_version': 0, 'request_id': '9ad0ccbf-cc25-4f81-86fc-476e4bec0c63'})
    assert CircuitSaveRequest.model_validate_json(request.model_dump_json()) == request
    result = plan_circuit(request, documents).model_dump()
    result['status'] = 'saved_planning'
    saved = SavedCircuitResult.model_validate(result)
    assert SavedCircuitResult.model_validate_json(saved.model_dump_json()) == saved
    assert saved.provenance == 'generated'


def test_circuit_underground_guard_applies_to_each_target():
    data, documents = circuit_inputs()
    data['targets'][1]['wall_id'] = None
    with pytest.raises(RoutingError, match='WALL_ATTACHMENT_REQUIRED'):
        plan_circuit(CircuitPlanningRequest.model_validate(data), documents)
    with pytest.raises(ValidationError, match='passage confirmation'):
        CircuitPlanningRequest.model_validate({**data, 'floor_passages_confirmed': False})
