"""Integration checks must run through scripts/run_isolated_backend_tests.py."""
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import User, Role, Project, ProjectFloor, FloorPlan, LayoutVersion
from app.models.generated_route import GeneratedRouteVersion


@pytest.fixture
def context():
    engine = get_engine()
    if engine.url.database != 'ved_electrical_verify' or engine.url.username != 'ved_test':
        pytest.fail('Run routing integration tests through the isolated test runner.')
    GeneratedRouteVersion.__table__.create(engine, checkfirst=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
    marker = uuid4().hex
    designer_role = session.scalar(select(Role).where(Role.name == 'DESIGNER'))
    admin_role = session.scalar(select(Role).where(Role.name == 'ADMIN'))
    user = User(oauth_provider=marker, oauth_subject='owner', role=designer_role)
    other = User(oauth_provider=marker, oauth_subject='other', role=designer_role)
    admin = User(oauth_provider=marker, oauth_subject='admin', role=admin_role)
    project = Project(owner=user, name='routing test')
    floor = ProjectFloor(project=project, name='Lower Ground Floor', sort_order=0)
    plan = FloorPlan(project_floor=floor, original_filename='synthetic.png', storage_path='originals/synthetic.png',
                     mime_type='image/png', file_size=12, processing_status='processed')
    session.add_all([plan, other, admin])
    session.flush()
    geometry = json.loads((Path(__file__).resolve().parents[2]/'fixtures/canonical_geometry_v1.json').read_text())
    geometry.update(project_id=project.id, floor_plan_id=plan.id, walls=[])
    geometry['floor']['project_floor_id'] = floor.id
    snapshot = LayoutVersion(project_id=project.id, project_floor_id=floor.id, floor_plan_id=plan.id,
        version_number=1, schema_version=1, is_current=True, geometry_document=geometry)
    session.add(snapshot)
    session.commit()
    app = create_app(Settings(_env_file=None, auto_start_interpretation_worker=False))
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    payload = dict(floors=[dict(floor_id=floor.id, expected_layout_version=1, service_elevation_meters=3, offset_x=0, offset_y=0)],
        panel=dict(floor_id=floor.id, x=1, y=1, elevation_meters=3),
        target=dict(floor_id=floor.id, symbol_id='detected:501', x=2.5, y=1.5, elevation_meters=3),
        grid_step_meters=1, alignment_confirmed=True)
    try:
        yield client, f'/api/projects/{project.id}/routes', payload, session, snapshot, app, other, admin
    finally:
        client.close()
        session.close()
        transaction.rollback()
        connection.close()


def test_persist_reload_recalculate_and_stale_layout(context):
    client, url, payload, session, snapshot, *_ = context
    assert client.get(url).json() is None
    first = client.post(url, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()['result']['total_meters'] == 2
    assert client.get(url).json() == first.json()
    second = client.post(url, json=payload)
    assert second.status_code == 201
    assert second.json()['version_number'] == 2
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 2
    snapshot.is_current = None
    session.flush()
    session.add(LayoutVersion(project_id=snapshot.project_id, project_floor_id=snapshot.project_floor_id,
        floor_plan_id=snapshot.floor_plan_id, version_number=2, schema_version=1, is_current=True,
        geometry_document=snapshot.geometry_document))
    session.commit()
    assert client.get(url).json()['stale'] is True
    assert client.post(url, json=payload).status_code == 409


def test_access_control_and_target_tampering(context):
    client, url, payload, session, snapshot, app, other, admin = context
    payload['target']['x'] = 4
    assert client.post(url, json=payload).status_code == 422
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(url).status_code == 404
    assert client.post(url, json=payload).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.post(url, json=payload).status_code == 403


def test_component_quantities_pin_saved_layout_and_enforce_access(context):
    from app.services.material_quantity_service import retrieve_component_quantities
    from app.services.layout_service import LayoutServiceError

    _, _, _, session, snapshot, app, other, _ = context
    owner = app.dependency_overrides[get_current_user]()
    quantities = retrieve_component_quantities(session, current_user=owner,
        project_id=snapshot.project_id, project_floor_id=snapshot.project_floor_id)
    assert quantities.layout_version_id == snapshot.id
    assert quantities.version_number == snapshot.version_number
    assert sum(row.quantity for row in quantities.components) == 2
    with pytest.raises(LayoutServiceError):
        retrieve_component_quantities(session, current_user=other,
            project_id=snapshot.project_id, project_floor_id=snapshot.project_floor_id)


def test_material_lengths_require_current_persisted_route(context):
    from app.services.material_quantity_service import retrieve_route_material_lengths

    client, url, payload, session, snapshot, app, _, _ = context
    owner = app.dependency_overrides[get_current_user]()
    with pytest.raises(ValueError, match="saved generated route"):
        retrieve_route_material_lengths(session, current_user=owner, project_id=snapshot.project_id)
    saved = client.post(url, json=payload).json()
    measured = retrieve_route_material_lengths(session, current_user=owner,
        project_id=snapshot.project_id, conductor_count=3)
    assert measured["route_version_id"] == saved["id"]
    assert measured["lengths"].conduit_meters == 2
    assert measured["lengths"].wire_meters == 6
    snapshot.is_current = None
    session.flush()
    with pytest.raises(ValueError, match="stale"):
        retrieve_route_material_lengths(session, current_user=owner, project_id=snapshot.project_id)


def test_circuit_preview_pins_snapshot_and_cannot_replace_saved_route_or_quantities(context):
    client, url, payload, session, snapshot, *_ = context
    saved = client.post(url, json=payload).json()
    preview_request = {key: value for key, value in payload.items() if key != 'target'}
    preview_request.update(circuit_id='C-LGT', installation_method='ceiling_service', targets=[payload['target']])
    result = client.post(url, json=preview_request)
    assert result.status_code == 200, result.text
    preview = result.json()
    assert preview['result']['status'] == 'preview_not_saved'
    assert preview['result']['optimality'] == 'graph_heuristic_not_global_optimum'
    assert preview['result']['total_meters'] == 2
    assert preview['layout_versions'] == {str(snapshot.project_floor_id): snapshot.id}
    assert client.get(url).json() == saved
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1
    preview_request['floors'][0]['expected_layout_version'] = 2
    assert client.post(url, json=preview_request).status_code == 409


def test_missing_device_completion_preserves_routes_save_reload_retry_and_assignments(context):
    client, url, payload, session, snapshot, *_ = context
    original = deepcopy(snapshot.geometry_document)
    data = circuit_save_payload(payload)
    data['routing_mode'] = 'missing_devices'
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    saved = first.json()
    assert saved['result']['algorithm'] == 'assigned_missing_device_astar_v2'
    assert client.get(url).json() == saved
    assert client.post(url, json=data).json() == saved
    stale = client.post(url, json={**data, 'request_id': str(uuid4()), 'expected_route_version': 0})
    assert stale.status_code == 409, stale.text
    assert client.get(url).json() == saved
    additional = deepcopy(data)
    additional.update(request_id=str(uuid4()), expected_route_version=1)
    target = snapshot.geometry_document['symbols'][1]
    additional['targets'].append(dict(floor_id=snapshot.project_floor_id, symbol_id=target['id'],
                                      **target['position'], elevation_meters=3))
    completed = client.post(url, json=additional)
    assert completed.status_code == 201, completed.text
    complete = completed.json()
    assert len(complete['result']['branches']) == 2
    assert complete['result']['branches'][0]['points'][-1] == saved['result']['branches'][0]['points'][-1]
    assert client.get(url).json() == complete
    assert client.post(url, json=additional).json() == complete
    changed_circuit = {**additional, 'request_id': str(uuid4()), 'expected_route_version': 2, 'circuit_id': 'UNRELATED'}
    refused = client.post(url, json=changed_circuit)
    assert refused.status_code == 422
    assert refused.json()['detail']['error']['code'] == 'EXISTING_ROUTE_REVIEW_REQUIRED'
    assert client.get(url).json() == complete
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 2
    assert snapshot.geometry_document == original


def test_missing_device_binding_on_same_generated_tree_saves_and_reloads_without_new_segment(context):
    client, url, payload, session, snapshot, *_ = context
    original = deepcopy(snapshot.geometry_document)
    updated = deepcopy(original)
    updated['symbols'][1]['position'] = dict(x=2, y=1.5)
    snapshot.geometry_document = updated
    session.commit()
    data = circuit_save_payload(payload)
    data['routing_mode'] = 'missing_devices'
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    saved = first.json()
    target = updated['symbols'][1]
    additional = deepcopy(data)
    additional.update(request_id=str(uuid4()), expected_route_version=1)
    additional['targets'].append(dict(floor_id=snapshot.project_floor_id, symbol_id=target['id'],
                                     **target['position'], elevation_meters=3))
    reply = client.post(url, json=additional)
    assert reply.status_code == 201, reply.text
    complete = reply.json()
    binding = next(b for b in complete['result']['branches'] if b['symbol_id'] == target['id'])
    assert len(binding['points']) == 1 and binding['segment_indices'] == []
    assert complete['result']['total_meters'] == saved['result']['total_meters']
    assert client.get(url).json() == complete
    assert client.post(url, json=additional).json() == complete
    assert snapshot.geometry_document == updated


def test_missing_completion_reads_real_canonical_connections_without_mutating_them(context):
    from app.geometry import canonical_geometry_from_dict
    from app.geometry.canonical_extension import canonical_extension_from_dict
    from app.services.canonical_extension_storage import save_canonical_extension
    client, url, payload, session, snapshot, *_ = context
    raw = deepcopy(snapshot.geometry_document)
    floor_id = snapshot.project_floor_id
    target = payload['target']
    raw['routes'] = [dict(id=1, points=[
        dict(project_floor_id=floor_id, x=1, y=target['y'], elevation_meters=3),
        dict(project_floor_id=floor_id, x=target['x'], y=target['y'], elevation_meters=3)])]
    snapshot.geometry_document = raw
    session.commit()
    extension = dict(extension_schema_version=4, base_schema_version=1,
        source_plane_reference=dict(floor_plan_page_id=snapshot.floor_plan_id, source_artifact_id=103,
                                    width_pixels=640, height_pixels=480),
        openings=[], panels=[], symbol_details=[dict(symbol_id=target['symbol_id'], orientation_degrees=None,
            bounds=None, provenance='reviewed:synthetic', installation=dict(elevation_meters=3, wall_id=None))],
        route_details=[dict(route_id=1, route_kind='observed',
            provenance_ref='reviewed:synthetic', device_connections=[dict(symbol_id=target['symbol_id'], point_index=1,
                anchor=dict(x=target['x'], y=target['y'], elevation_meters=3))])])
    validated = canonical_extension_from_dict(extension, canonical_geometry_from_dict(raw))
    save_canonical_extension(snapshot.id, validated)
    request = circuit_save_payload(payload)
    for key in ('intent', 'expected_route_version', 'request_id'):
        request.pop(key)
    request['routing_mode'] = 'missing_devices'
    preview = client.post(url, json=request)
    assert preview.status_code == 200, preview.text
    result = preview.json()['result']
    assert result['branches'] == result['segments'] == []
    assert result['skipped_targets'] == [dict(floor_id=floor_id, symbol_id=target['symbol_id'], reason='EXISTING_CANONICAL_CONNECTION')]
    assert result['total_meters'] == 0
    assert snapshot.geometry_document == raw
    assert client.get(url).json() is None


def test_reviewed_observed_network_assignment_saves_reloads_and_retries_without_source_rewrite(context):
    from app.geometry import canonical_geometry_from_dict
    from app.geometry.canonical_extension import canonical_extension_from_dict
    from app.services.canonical_extension_storage import save_canonical_extension
    client, url, payload, session, snapshot, *_ = context
    raw = deepcopy(snapshot.geometry_document)
    floor_id = snapshot.project_floor_id
    raw['routes'] = [dict(id=7, points=[dict(project_floor_id=floor_id, x=x, y=1, elevation_meters=3) for x in [1, 3]])]
    snapshot.geometry_document = raw; session.commit()
    extension = canonical_extension_from_dict(dict(extension_schema_version=4, base_schema_version=1,
        source_plane_reference=dict(floor_plan_page_id=snapshot.floor_plan_id, source_artifact_id=103,
                                    width_pixels=640, height_pixels=480), openings=[], panels=[], symbol_details=[],
        route_details=[dict(route_id=7, route_kind='observed', provenance_ref='reviewed:synthetic', device_connections=[])]),
        canonical_geometry_from_dict(raw))
    source_file, source_hash = save_canonical_extension(snapshot.id, extension)
    source_bytes = source_file.read_bytes()
    data = circuit_save_payload(payload)
    data.update(routing_mode='missing_devices', observed_route_assignments=[dict(floor_id=floor_id, route_id=7)])
    reply = client.post(url, json=data)
    assert reply.status_code == 201, reply.text
    saved = reply.json()
    assert saved['result']['algorithm'] == 'assigned_missing_device_astar_v3'
    assert saved['result']['total_meters'] == .5
    assert saved['result']['reused_observed_routes'] == data['observed_route_assignments']
    assert saved['result']['branches'][0]['points'][0] == dict(floor_id=floor_id, x=2.5, y=1, elevation_meters=3)
    assert client.get(url).json() == saved
    assert client.post(url, json=data).json() == saved
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1
    assert snapshot.geometry_document == raw
    assert source_file.read_bytes() == source_bytes
    import hashlib
    assert hashlib.sha256(source_bytes).hexdigest() == source_hash
    changed = deepcopy(data); changed['observed_route_assignments'] = []
    assert client.post(url, json=changed).status_code == 409


def test_circuit_preview_enforces_owner_roles_and_explicit_supported_installation(context):
    client, url, payload, session, snapshot, app, other, admin = context
    data = {key: value for key, value in payload.items() if key != 'target'}
    data.update(circuit_id='C-LGT', installation_method='ceiling_service', targets=[payload['target']])
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.post(url, json=data).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.post(url, json=data).status_code == 403
    # Return the fixture owner without inventing any new permissions.
    owner = session.get(User, session.get(Project, snapshot.project_id).owner_id)
    app.dependency_overrides[get_current_user] = lambda: owner
    data['installation_method'] = 'underground'
    assert client.post(url, json=data).status_code == 422
    assert not session.scalars(select(GeneratedRouteVersion)).all()


def test_circuit_preview_uses_current_read_and_fences_layout_change_during_planning(context, monkeypatch):
    from app.services import routing_service
    client, url, payload, session, snapshot, *_ = context
    planner = routing_service.plan_circuit
    reader = routing_service.current_layout_ids
    reads = []

    def current_read(*args, **kwargs):
        reads.append(kwargs.get('lock', False))
        return reader(*args, **kwargs)

    def changed_after_planning(request, documents):
        result = planner(request, documents)
        snapshot.is_current = None
        session.flush()
        session.add(LayoutVersion(project_id=snapshot.project_id, project_floor_id=snapshot.project_floor_id,
            floor_plan_id=snapshot.floor_plan_id, version_number=2, schema_version=1, is_current=True,
            geometry_document=snapshot.geometry_document))
        session.commit()
        return result

    monkeypatch.setattr(routing_service, 'current_layout_ids', current_read)
    monkeypatch.setattr(routing_service, 'plan_circuit', changed_after_planning)
    data = {key: value for key, value in payload.items() if key != 'target'}
    data.update(circuit_id='C-LGT', installation_method='ceiling_service', targets=[payload['target']])
    reply = client.post(url, json=data)
    assert reply.status_code == 409
    assert reads == [True]
    assert not session.scalars(select(GeneratedRouteVersion)).all()


def circuit_save_payload(payload, *, expected_route_version=0, request_id=None):
    data = deepcopy({key: value for key, value in payload.items() if key != 'target'})
    data.update(circuit_id='C-LGT', installation_method='ceiling_service',
                targets=[deepcopy(payload['target'])], intent='save_planning_circuit',
                expected_route_version=expected_route_version, request_id=str(request_id or uuid4()))
    return data


def test_circuit_save_persists_creator_and_exact_reload_without_modifying_source(context):
    client, url, payload, session, snapshot, app, *_ = context
    owner = app.dependency_overrides[get_current_user]()
    plan = session.get(FloorPlan, snapshot.floor_plan_id)
    geometry_before = deepcopy(snapshot.geometry_document)
    source_before = (plan.storage_path, plan.original_filename, plan.file_size, plan.processing_status)
    data = circuit_save_payload(payload)
    reply = client.post(url, json=data)
    assert reply.status_code == 201, reply.text
    saved = reply.json()
    assert saved['result']['status'] == 'saved_planning'
    assert saved['version_number'] == 1
    assert saved['layout_versions'] == {str(snapshot.project_floor_id): snapshot.id}
    assert client.get(url).json() == saved
    rows = session.scalars(select(GeneratedRouteVersion)).all()
    assert len(rows) == 1
    assert rows[0].created_by_user_id == owner.id
    assert rows[0].result == saved['result']
    assert rows[0].configuration == saved['configuration']
    assert snapshot.geometry_document == geometry_before
    assert snapshot.is_current is True and snapshot.version_number == 1
    assert len(session.scalars(select(LayoutVersion)).all()) == 1
    assert (plan.storage_path, plan.original_filename, plan.file_size, plan.processing_status) == source_before
    preview = deepcopy(data)
    for field in ('intent', 'expected_route_version', 'request_id'):
        preview.pop(field)
    reply = client.post(url, json=preview)
    assert reply.status_code == 200, reply.text
    assert reply.json()['result']['status'] == 'preview_not_saved'
    assert client.get(url).json() == saved
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1


def test_circuit_save_normalized_retry_is_idempotent_after_latest_route_changes(context):
    client, url, payload, session, *_ = context
    request_id = uuid4()
    data = circuit_save_payload(payload, request_id=str(request_id).upper())
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    saved = first.json()
    data['request_id'] = request_id.hex
    retry = client.post(url, json=data)
    assert retry.status_code == 201, retry.text
    assert retry.json() == saved
    # A later unrelated route must not redirect the retry to the latest row.
    later = client.post(url, json=payload)
    assert later.status_code == 201, later.text
    assert later.json()['version_number'] == 2
    retry = client.post(url, json=data)
    assert retry.status_code == 201, retry.text
    assert retry.json() == saved
    assert client.get(url).json() == later.json()
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 2


def test_legacy_ceiling_retry_normalizes_absent_passage_default_without_rewriting(context):
    client, url, payload, session, *_ = context
    data = circuit_save_payload(payload)
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    row = session.get(GeneratedRouteVersion, first.json()['id'])
    legacy = deepcopy(row.configuration)
    legacy.pop('floor_passages_confirmed')
    row.configuration = legacy
    session.commit()
    retry = client.post(url, json=data)
    assert retry.status_code == 201, retry.text
    # The response schema supplies its default; stored historical JSON stays exact.
    assert retry.json()['configuration'] == {**legacy, 'floor_passages_confirmed': False}
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1
    assert row.configuration == legacy
    assert client.get(url).json() == retry.json()


def test_underground_planning_persist_reload_retry_and_preserve_canonical(context):
    client, url, payload, session, snapshot, *_ = context
    original = deepcopy(snapshot.geometry_document)
    data = circuit_save_payload(payload)
    floor_elevation = snapshot.geometry_document['floor']['elevation_meters']
    data.update(installation_method='underground', floor_passages_confirmed=True)
    data['floors'][0]['service_elevation_meters'] = floor_elevation - .4
    data['panel']['elevation_meters'] = floor_elevation
    data['targets'][0]['elevation_meters'] = floor_elevation
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    saved = first.json()
    assert saved['configuration']['floor_passages_confirmed'] is True
    assert saved['result']['installation_method'] == 'underground'
    assert {segment['kind'] for segment in saved['result']['segments']} == {'underground', 'underground_drop', 'underground_rise'}
    assert saved['result']['horizontal_meters'] == 2
    assert saved['result']['vertical_meters'] == pytest.approx(.8)
    assert saved['result']['total_meters'] == pytest.approx(2.8)
    assert client.get(url).json() == saved
    assert client.post(url, json=data).json() == saved
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1
    assert snapshot.geometry_document == original
    invalid = deepcopy(data)
    invalid.update(request_id=str(uuid4()), expected_route_version=1, floor_passages_confirmed=False)
    assert client.post(url, json=invalid).status_code == 422
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1


def test_circuit_save_changed_payload_same_request_id_conflicts_without_append(context):
    client, url, payload, session, *_ = context
    data = circuit_save_payload(payload)
    first = client.post(url, json=data)
    assert first.status_code == 201, first.text
    changed = deepcopy(data)
    changed['circuit_id'] = 'C-OTHER'
    conflict = client.post(url, json=changed)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()['detail']['error']['code'] == 'CIRCUIT_RETRY_CONFLICT'
    assert client.get(url).json() == first.json()
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1


def test_circuit_save_expected_route_version_fences_distinct_requests(context):
    client, url, payload, session, *_ = context
    first = client.post(url, json=circuit_save_payload(payload))
    assert first.status_code == 201, first.text
    stale = client.post(url, json=circuit_save_payload(payload, expected_route_version=0))
    assert stale.status_code == 409, stale.text
    assert stale.json()['detail']['error']['code'] == 'STALE_ROUTE_VERSION'
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1
    second = client.post(url, json=circuit_save_payload(payload, expected_route_version=1))
    assert second.status_code == 201, second.text
    assert second.json()['version_number'] == 2
    assert client.get(url).json() == second.json()
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 2


def test_circuit_save_enforces_existing_owner_and_role_access(context):
    client, url, payload, session, _, app, other, admin = context
    data = circuit_save_payload(payload)
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.post(url, json=data).status_code == 404
    assert client.get(url).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.post(url, json=data).status_code == 403
    assert not session.scalars(select(GeneratedRouteVersion)).all()


@pytest.mark.parametrize('field,value', [('expected_route_version', -1),
                                         ('expected_route_version', 1.5),
                                         ('request_id', 'not-a-uuid'),
                                         ('intent', 'approve_electrical_plan')])
def test_circuit_save_rejects_invalid_contract_before_append(context, field, value):
    client, url, payload, session, *_ = context
    data = circuit_save_payload(payload)
    data[field] = value
    assert client.post(url, json=data).status_code == 422
    assert not session.scalars(select(GeneratedRouteVersion)).all()


def test_circuit_save_fences_layout_changed_during_compute_without_append(context, monkeypatch):
    from app.services import routing_service
    client, url, payload, session, snapshot, *_ = context
    planner = routing_service.plan_circuit

    def changed_after_planning(request, documents):
        result = planner(request, documents)
        snapshot.is_current = None
        session.flush()
        session.add(LayoutVersion(project_id=snapshot.project_id, project_floor_id=snapshot.project_floor_id,
            floor_plan_id=snapshot.floor_plan_id, version_number=2, schema_version=1, is_current=True,
            geometry_document=deepcopy(snapshot.geometry_document)))
        session.commit()
        return result

    monkeypatch.setattr(routing_service, 'plan_circuit', changed_after_planning)
    reply = client.post(url, json=circuit_save_payload(payload))
    assert reply.status_code == 409, reply.text
    assert reply.json()['detail']['error']['code'] == 'STALE_LAYOUT_VERSION'
    assert not session.scalars(select(GeneratedRouteVersion)).all()


def test_saved_planning_circuit_blocks_estimation_options_and_material_measurement(context):
    from app.services.estimate_service import estimate_options
    from app.services.material_quantity_service import retrieve_route_material_lengths

    client, url, payload, session, snapshot, app, *_ = context
    owner = app.dependency_overrides[get_current_user]()
    saved = client.post(url, json=circuit_save_payload(payload))
    assert saved.status_code == 201, saved.text
    options = estimate_options(session, owner, snapshot.project_id)
    assert options['route_version_id'] == saved.json()['id']
    assert options['route_blocker'] == 'CIRCUIT_ESTIMATION_NOT_CONFIGURED'
    assert options['components'] == []
    assert options['stale'] is False
    with pytest.raises(ValueError, match='Circuit conductor and material semantics are not configured'):
        retrieve_route_material_lengths(session, current_user=owner,
            project_id=snapshot.project_id, conductor_count=3)
    assert client.get(url).json() == saved.json()
    assert len(session.scalars(select(GeneratedRouteVersion)).all()) == 1


def test_saved_planning_circuit_estimate_api_returns_meaningful_422_without_estimate(context):
    from app.api.routes.estimates import router as estimates_router
    from app.services.estimate_service import retrieve_estimates

    client, url, payload, session, snapshot, app, *_ = context
    # The fixture uses the default application profile; mount the existing router
    # only when estimation is absent, without changing application configuration.
    estimates_url = url.rsplit('/',1)[0]+'/estimates'
    if '/api/projects/{project_id}/estimates' not in app.openapi()['paths']:
        app.include_router(estimates_router)
    saved = client.post(url, json=circuit_save_payload(payload))
    assert saved.status_code == 201, saved.text
    reply = client.post(estimates_url, json=dict(request_id=str(uuid4()),
        route_version_id=saved.json()['id'], components=[], conduit_material_id=1,
        wire_material_id=2, conductor_count=3, mappings_confirmed=True))
    assert reply.status_code == 422, reply.text
    assert reply.json()['detail']['error']['code'] == 'CIRCUIT_ESTIMATION_NOT_CONFIGURED'
    owner = app.dependency_overrides[get_current_user]()
    assert retrieve_estimates(session,owner,snapshot.project_id) == []
    assert client.get(url).json() == saved.json()
