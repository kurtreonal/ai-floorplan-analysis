"""Integration checks must run through scripts/run_isolated_backend_tests.py."""
import json
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
