import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.geometry import canonical_geometry_from_dict
from app.routing.circuit import CircuitPlanningRequest
from app.routing.graph import RoutingError
from app.routing.missing_devices import plan_missing_devices


def inputs():
    raw = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/canonical_geometry_v1.json').read_text())
    raw['walls'], raw['routes'] = [], []
    request = CircuitPlanningRequest(circuit_id='C-1', routing_mode='missing_devices', installation_method='ceiling_service',
        floors=[dict(floor_id=2, expected_layout_version=1, service_elevation_meters=3, offset_x=0, offset_y=0)],
        panel=dict(floor_id=2, x=1, y=1, elevation_meters=3),
        targets=[dict(floor_id=2, symbol_id=s['id'], **s['position'], elevation_meters=3) for s in raw['symbols']],
        grid_step_meters=.5, alignment_confirmed=True)
    return raw, request


def run(raw, request, extension=None, previous=None):
    return plan_missing_devices(request, {2: canonical_geometry_from_dict(raw)}, {2: extension}, previous, {'2': 5})


def test_missing_routes_use_astar_preserve_source_and_repeat_exactly():
    raw, request = inputs()
    before = deepcopy(raw)
    result = run(raw, request)
    assert result.algorithm == 'assigned_missing_device_astar_v2'
    assert len(result.branches) == 2
    assert result == run(raw, request)
    assert raw == before
    assert all(s.start.x == s.end.x or s.start.y == s.end.y for s in result.segments)
    identities = [tuple(sorted(((s.start.x, s.start.y, s.start.elevation_meters),
                                (s.end.x, s.end.y, s.end.elevation_meters)))) for s in result.segments]
    assert len(identities) == len(set(identities))
    assert result.total_meters == sum(s.horizontal_meters+s.vertical_meters for s in result.segments)


def connected_source(raw):
    point = {**raw['symbols'][0]['position'], 'project_floor_id': 2, 'elevation_meters': 3}
    raw['routes'] = [dict(id=1, points=[dict(point, x=1), point])]
    return SimpleNamespace(route_details=[SimpleNamespace(route_id=1, device_connections=[
        SimpleNamespace(symbol_id='detected:501', point_index=1,
                        anchor=dict(x=point['x'], y=point['y'], elevation_meters=3))])])


def test_explicit_source_connection_wins_without_attaching_nearby_devices():
    raw, request = inputs()
    extension = connected_source(raw)
    # Adjacent device is not served merely because it is close to the wire.
    raw['symbols'][1]['position'] = dict(x=2.51, y=1.51)
    target = request.targets[1].model_copy(update=raw['symbols'][1]['position'])
    request = request.model_copy(update={'targets': [request.targets[0], target]})
    result = run(raw, request, extension)
    assert [b.symbol_id for b in result.branches] == ['manual:601']
    assert result.skipped_targets[0].reason == 'EXISTING_CANONICAL_CONNECTION'
    assert result.skipped_targets[0].symbol_id == 'detected:501'


def test_literal_unbound_crossing_is_unresolved_not_a_junction_or_duplicate():
    raw, request = inputs()
    connected_source(raw)
    result = run(raw, request)
    assert result.unresolved_targets[0].reason == 'SOURCE_ATTACHMENT_REVIEW_REQUIRED'
    assert result.unresolved_targets[0].symbol_id == 'detected:501'
    assert [b.symbol_id for b in result.branches] == ['manual:601']


def test_no_path_target_does_not_block_other_valid_assigned_devices():
    raw, request = inputs()
    request = CircuitPlanningRequest.model_validate({**request.model_dump(), 'obstacles': [
        dict(floor_id=2, min_x=4, max_x=4.2, min_y=2.1, max_y=2.4, bottom=2, top=4)]})
    result = run(raw, request)
    assert [b.symbol_id for b in result.branches] == ['detected:501']
    assert [(i.symbol_id, i.reason) for i in result.unresolved_targets] == [('manual:601', 'NO_ROUTE')]


def test_explicit_mounting_produces_shared_3d_drop_and_measured_vertical_length():
    raw, request = inputs()
    raw['walls'] = [dict(id=7, source_candidate_id=None, processing_job_id=None, status='verified',
        start=dict(x=2.5, y=0), end=dict(x=2.5, y=3), length_meters=3, angle_degrees=90,
        thickness_meters=.2, height_meters=3)]
    request = request.model_copy(update={'targets': [request.targets[0].model_copy(update={'elevation_meters': -1.05, 'wall_id': 7})]})
    result = run(raw, request)
    end = result.branches[0].points[-1]
    assert (end.x, end.y, end.elevation_meters) == (2.5, 1.5, -1.05)
    assert result.vertical_meters == pytest.approx(4.05)
    assert any(s.kind == 'wall_drop' for s in result.segments)


def test_same_circuit_replay_retains_branches_without_duplicate_segments():
    raw, request = inputs()
    result = run(raw, request)
    stored = result.model_dump(mode='json')
    stored['status'] = 'saved_planning'
    previous = SimpleNamespace(configuration=request.model_dump(mode='json'), result=stored, layout_versions={'2': 5})
    assert run(raw, request, previous=previous) == result
    assert previous.result == stored
    for change in ({'circuit_id': 'another'}, {'grid_step_meters': 1}, {'targets': [request.targets[0]]}):
        with pytest.raises(RoutingError, match='EXISTING_ROUTE_REVIEW_REQUIRED'):
            run(raw, request.model_copy(update=change), previous=previous)
    with pytest.raises(RoutingError, match='EXISTING_ROUTE_REVIEW_REQUIRED'):
        run(raw, request, previous=replace_record(previous, layout_versions={'2': 4}))


def replace_record(record, **changes):
    return SimpleNamespace(**{**vars(record), **changes})


def test_missing_device_reuses_assigned_generated_tree_instead_of_panel_star():
    raw, request = inputs()
    # First route is a straight service run. The second has a one-metre branch
    # onto it, rather than another full independent route from the panel.
    raw['symbols'][0]['position'] = dict(x=4, y=1)
    raw['symbols'][1]['position'] = dict(x=3, y=2)
    targets = [target.model_copy(update=raw['symbols'][i]['position']) for i, target in enumerate(request.targets)]
    request = request.model_copy(update={'targets': targets})
    result = run(raw, request)
    assert result.total_meters == 4
    branches = {branch.symbol_id: branch for branch in result.branches}
    assert branches['manual:601'].total_meters == 1
    assert (branches['manual:601'].points[0].x, branches['manual:601'].points[0].y) == (3, 1)
    assert result == run(raw, request.model_copy(update={'targets': list(reversed(targets))}))


def test_old_saved_algorithm_is_readable_and_reused_without_rewriting_history():
    raw, request = inputs()
    result = run(raw, request)
    stored = result.model_dump(mode='json')
    stored.update(status='saved_planning', algorithm='assigned_missing_device_astar_v1')
    previous = SimpleNamespace(configuration=request.model_dump(mode='json'), result=stored, layout_versions={'2': 5})
    assert run(raw, request, previous=previous).segments == result.segments
    assert previous.result['algorithm'] == 'assigned_missing_device_astar_v1'


def test_assigned_device_on_generated_tree_has_persisted_binding_without_new_wire():
    raw, request = inputs()
    raw['symbols'][0]['position'] = dict(x=4, y=1)
    raw['symbols'][1]['position'] = dict(x=3, y=1)
    targets = [target.model_copy(update=raw['symbols'][i]['position']) for i, target in enumerate(request.targets)]
    request = request.model_copy(update={'targets': targets})
    result = run(raw, request)
    assert len(result.branches) == 2 and result.total_meters == 3
    branch = result.branches[1]
    assert branch.symbol_id == 'manual:601' and len(branch.points) == 1
    assert branch.segment_indices == [] and branch.total_meters == 0
    stored = result.model_dump(mode='json')
    stored['status'] = 'saved_planning'
    previous = SimpleNamespace(configuration=request.model_dump(mode='json'), result=stored, layout_versions={'2': 5})
    assert run(raw, request, previous=previous) == result


def observed_network(raw, request, *, points=None):
    raw['symbols'][0]['position'] = dict(x=3, y=2)
    target = request.targets[0].model_copy(update=raw['symbols'][0]['position'])
    request = CircuitPlanningRequest.model_validate({**request.model_dump(), 'targets': [target.model_dump()],
        'observed_route_assignments': [dict(floor_id=2, route_id=7)]})
    raw['routes'] = [dict(id=7, points=[dict(project_floor_id=2, x=x, y=y, elevation_meters=z)
                                      for x, y, z in (points or [(1, 1, 3), (4, 1, 3)])])]
    extension = SimpleNamespace(route_details=[SimpleNamespace(route_id=7, route_kind='observed', device_connections=[])])
    return request, extension


def test_explicit_reviewed_observed_network_reused_without_copying_or_recounting_it():
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    before = deepcopy(raw)
    result = run(raw, request, extension)
    assert result.algorithm == 'assigned_missing_device_astar_v3'
    assert result.total_meters == 1  # Original 3 m observed run is not generated/count again.
    assert result.branches[0].points[0].model_dump() == dict(floor_id=2, x=3, y=1, elevation_meters=3)
    assert result.reused_observed_routes == request.observed_route_assignments
    assert result.branches[0].observed_attachment.model_dump() == dict(floor_id=2, route_id=7, segment_index=0,
        anchor=dict(floor_id=2, x=3, y=1, elevation_meters=3))
    assert result == run(raw, request, extension)
    assert raw == before
    unassigned = request.model_copy(update={'observed_route_assignments': []})
    assert run(raw, unassigned, extension).total_meters == 3


@pytest.mark.parametrize('start,end', [((2, 0), (2, 2)), ((4.01, 1), (4.01, 2))])
def test_assigned_crossings_and_nearby_endpoints_do_not_create_network_junctions(start, end):
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    raw['routes'].append(dict(id=8, points=[dict(project_floor_id=2, x=x, y=y, elevation_meters=3) for x, y in (start, end)]))
    extension.route_details.append(SimpleNamespace(route_id=8, route_kind='observed', device_connections=[]))
    request = CircuitPlanningRequest.model_validate({**request.model_dump(), 'observed_route_assignments': [
        dict(floor_id=2, route_id=7), dict(floor_id=2, route_id=8)]})
    with pytest.raises(RoutingError, match='OBSERVED_NETWORK_PANEL_CONNECTION_REQUIRED'):
        run(raw, request, extension)


def test_shared_reviewed_endpoints_join_but_wrong_provenance_and_obstacles_are_refused():
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    raw['routes'].append(dict(id=8, points=[dict(project_floor_id=2, x=x, y=y, elevation_meters=3) for x, y in [(4, 1), (4, 2)]]))
    extension.route_details.append(SimpleNamespace(route_id=8, route_kind='observed', device_connections=[]))
    request = CircuitPlanningRequest.model_validate({**request.model_dump(), 'observed_route_assignments': [
        dict(floor_id=2, route_id=7), dict(floor_id=2, route_id=8)]})
    assert run(raw, request, extension).total_meters == 1
    extension.route_details[-1].route_kind = 'generated'
    with pytest.raises(RoutingError, match='OBSERVED_NETWORK_REFERENCE_REQUIRED'):
        run(raw, request, extension)
    extension.route_details[-1].route_kind = 'observed'
    blocked = CircuitPlanningRequest.model_validate({**request.model_dump(), 'obstacles': [
        dict(floor_id=2, min_x=2, max_x=2.1, min_y=.9, max_y=1.1, bottom=2, top=4)]})
    with pytest.raises(RoutingError, match='OBSERVED_NETWORK_OBSTACLE_CONFLICT'):
        run(raw, blocked, extension)


def test_observed_network_requires_stored_service_height_and_preserves_explicit_drop():
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    raw['walls'] = [dict(id=7, source_candidate_id=None, processing_job_id=None, status='verified',
        start=dict(x=3, y=0), end=dict(x=3, y=3), length_meters=3, angle_degrees=90,
        thickness_meters=.2, height_meters=3)]
    request = request.model_copy(update={'targets': [request.targets[0].model_copy(update={'elevation_meters': -.15, 'wall_id': 7})]})
    result = run(raw, request, extension)
    assert result.horizontal_meters == 1
    assert result.vertical_meters == pytest.approx(3.15)
    assert result.branches[0].points[-1].elevation_meters == -.15
    assert sum(s.kind == 'wall_drop' for s in result.segments) == 1
    for point in raw['routes'][0]['points']:
        point['elevation_meters'] = 2.9
    request = request.model_copy(update={'panel': request.panel.model_copy(update={'elevation_meters': 2.9})})
    with pytest.raises(RoutingError, match='OBSERVED_NETWORK_SERVICE_ELEVATION_REQUIRED'):
        run(raw, request, extension)


def test_saved_observed_network_assignment_is_pinned_and_retry_is_nonmutating():
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    result = run(raw, request, extension)
    stored = result.model_dump(mode='json'); stored['status'] = 'saved_planning'
    previous = SimpleNamespace(configuration=request.model_dump(mode='json'), result=stored, layout_versions={'2': 5})
    assert run(raw, request, extension, previous) == result
    with pytest.raises(RoutingError, match='EXISTING_ROUTE_REVIEW_REQUIRED'):
        run(raw, request.model_copy(update={'observed_route_assignments': []}), extension, previous)
    assert previous.result == stored


def test_observed_network_does_not_invent_a_service_rise_above_physical_panel():
    raw, request = inputs()
    request, extension = observed_network(raw, request, points=[(1, 1, 1), (1, 1, 2), (4, 1, 2), (4, 1, 3)])
    raw['walls'] = [dict(id=7, source_candidate_id=None, processing_job_id=None, status='verified',
        start=dict(x=1, y=0), end=dict(x=1, y=3), length_meters=3, angle_degrees=90,
        thickness_meters=.2, height_meters=3)]
    raw['symbols'][0]['position'] = dict(x=1.5, y=1.2)
    request = request.model_copy(update={
        'panel': request.panel.model_copy(update={'elevation_meters': 1, 'wall_id': 7}),
        'targets': [request.targets[0].model_copy(update=raw['symbols'][0]['position'])]})
    result = run(raw, request, extension)
    assert (result.branches[0].points[0].x, result.branches[0].points[0].y) == (4, 1)
    assert result.total_meters == pytest.approx(2.7)
    assert result.vertical_meters == 0
    assert result.branches[0].observed_attachment.route_id == 7
    assert result.branches[0].observed_attachment.segment_index == 2


@pytest.mark.parametrize('assignments,mode', [
    ([dict(floor_id=2, route_id=7)]*2, 'missing_devices'),
    ([dict(floor_id=99, route_id=7)], 'missing_devices'),
    ([dict(floor_id=2, route_id=7)], 'shared_circuit'),
])
def test_observed_assignments_reject_duplicate_foreign_floor_and_wrong_mode(assignments, mode):
    from pydantic import ValidationError
    _, request = inputs()
    with pytest.raises(ValidationError):
        CircuitPlanningRequest.model_validate({**request.model_dump(), 'routing_mode': mode, 'observed_route_assignments': assignments})


def test_observed_network_anchors_use_stored_floor_offsets_once():
    raw, request = inputs()
    request, extension = observed_network(raw, request)
    request = request.model_copy(update={'floors': [request.floors[0].model_copy(update={'offset_x': 10, 'offset_y': 20})]})
    result = run(raw, request, extension)
    assert result.total_meters == 1
    assert result.branches[0].observed_attachment.anchor.model_dump() == dict(floor_id=2, x=13, y=21, elevation_meters=3)
    assert (raw['routes'][0]['points'][0]['x'], raw['routes'][0]['points'][0]['y']) == (1, 1)
