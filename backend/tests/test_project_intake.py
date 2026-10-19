"""Project intake uses only restricted MySQL fixtures; never alter application data."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_engine
from app.core.schema import ensure_project_intake_columns, DevelopmentSchemaInitializationError
from app.models import FloorPlan, Project, ProjectFloor
from tests.test_routing_api import context

FIELDS = ('contact_number', 'service_type', 'service_type_other', 'preferred_start_date', 'blueprint_availability')

@pytest.fixture(scope='module', autouse=True)
def schema():
    engine = get_engine()
    assert engine.url.database == 'ved_electrical_verify' and engine.url.username == 'ved_test'
    with patch('app.core.schema.get_settings', return_value=SimpleNamespace(app_env='development')):
        ensure_project_intake_columns(engine)
        assert ensure_project_intake_columns(engine) == ()
    columns = {item['name']: item for item in inspect(engine).get_columns('projects')}
    assert all(columns[name]['nullable'] for name in FIELDS)

def details():
    return dict(name='Synthetic intake project', client_name='Example client', location='Synthetic site',
        contact_number='+63 (02) 0012 ext 04', service_type='other', service_type_other='Client-described service',
        preferred_start_date='2027-01-05', blueprint_availability='later')

def test_create_without_blueprint_and_edit_persists_strings_dates(context):
    client, _, _, session, layout, *_ = context
    count = len(session.scalars(select(FloorPlan)).all())
    created = client.post('/api/projects', json=details())
    assert created.status_code == 201, created.text
    value = created.json(); url = '/api/projects/' + str(value['id'])
    assert value['contact_number'] == '+63 (02) 0012 ext 04'
    assert value['preferred_start_date'] == '2027-01-05'
    assert len(value['details_revision']) == 64
    assert len(session.scalars(select(FloorPlan)).all()) == count
    assert session.scalars(select(ProjectFloor).where(ProjectFloor.project_id == value['id'])).all() == []
    data = dict(contact_number='000123', service_type='maintenance_repair', blueprint_availability='available_now',
        expected_details_revision=value['details_revision'])
    saved = client.patch(url, json=data)
    assert saved.status_code == 200, saved.text
    saved = saved.json()
    assert saved['contact_number'] == '000123' and saved['service_type_other'] is None
    assert saved['preferred_start_date'] == '2027-01-05' and saved['details_revision'] != value['details_revision']
    assert client.get(url).json() == saved
    assert client.patch(url, json=data).json() == saved  # uncertain-save retry, not another update
    assert len(session.scalars(select(FloorPlan)).all()) == count
    assert client.get('/api/projects').json()[0]['id'] == value['id']
    assert session.get(Project, layout.project_id).name == 'routing test'

def test_legacy_nulls_and_stale_edits_never_overwrite_geometry(context):
    client, _, _, session, layout, *_ = context
    geometry = deepcopy(layout.geometry_document)
    url = f'/api/projects/{layout.project_id}'
    original = client.get(url).json()
    assert all(original[name] is None for name in FIELDS)
    first = client.patch(url, json=dict(client_name='First editor', expected_details_revision=original['details_revision']))
    assert first.status_code == 200
    rejected = client.patch(url, json=dict(client_name='Stale editor', expected_details_revision=original['details_revision']))
    assert rejected.status_code == 409
    assert client.get(url).json() == first.json()
    assert layout.geometry_document == geometry
    cleared = client.patch(url, json=dict(client_name=None, expected_details_revision=first.json()['details_revision']))
    assert cleared.status_code == 200 and cleared.json()['client_name'] is None

@pytest.mark.parametrize('defect', [dict(contact_number=12345),dict(contact_number='x'*65),dict(preferred_start_date='2027-01-01T00:00:00'),
    dict(preferred_start_date=1798761600),dict(preferred_start_date='2027-02-30'),dict(preferred_start_date='0001-01-01'),dict(service_type='other',service_type_other=''),
    dict(service_type='invented'),dict(blueprint_availability='yes'),dict(owner_id=1),dict(status='archived')])
def test_invalid_intake_never_creates_partial_projects(context, defect):
    client, _, _, session, *_ = context
    before = len(session.scalars(select(Project)).all())
    response = client.post('/api/projects', json=details() | defect)
    assert response.status_code == 422, response.text
    assert len(session.scalars(select(Project)).all()) == before

def test_edit_permissions_validation_and_concurrent_identity(context):
    client, _, _, _, layout, app, other, admin = context
    url = f'/api/projects/{layout.project_id}'
    original = client.get(url).json()
    payload = dict(name='Changed', expected_details_revision=original['details_revision'])
    for invalid in (dict(name=None),dict(name=' '),dict(service_type_other='orphan'),dict(expected_details_revision='x'),dict(owner_id=other.id)):
        assert client.patch(url, json=payload | invalid).status_code == 422
        assert client.get(url).json() == original
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.patch(url, json=payload).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.patch(url, json=payload).status_code == 403
    assert client.get(url).status_code == 200
    app.dependency_overrides.pop(get_current_user)
    assert client.patch(url, json=payload).status_code == 401

def test_schema_initializer_refuses_production():
    with patch('app.core.schema.get_settings', return_value=SimpleNamespace(app_env='production')):
        with pytest.raises(DevelopmentSchemaInitializationError):
            ensure_project_intake_columns(get_engine())

def test_schema_initializer_refuses_incompatible_existing_column():
    from sqlalchemy import String
    with patch('app.core.schema.inspect') as inspection:
        inspection.return_value.get_columns.return_value = [dict(name='contact_number',nullable=False,type=String(64))]
        with pytest.raises(DevelopmentSchemaInitializationError, match='incompatible definition'):
            ensure_project_intake_columns(get_engine())

def test_existing_unmapped_columns_are_not_populated(context):
    _, _, _, session, layout, *_ = context
    with Session(get_engine()) as unrelated:
        assert unrelated.get(Project, layout.project_id) is None  # fixture transaction is isolated
    assert all(getattr(session.get(Project, layout.project_id), name) is None for name in FIELDS)
