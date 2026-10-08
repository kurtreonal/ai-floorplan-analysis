"""Run only through scripts/run_isolated_backend_tests.py; never the dev DB."""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.floor_plan_interpretation import CandidateHostProvenance, build_candidate_envelope
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.core.database import get_db, get_engine
from app.main import create_app
from app.models import (FloorPlan, FloorPlanSource, FloorPlanPage, ProcessingArtifact,
    ProcessingJob, InterpretationPageOutcome, FloorPlanInterpretationRun,
    FloorPlanInterpretationReview, LayoutVersion, Project, ProjectFloor, Role, User)
from app.models.processing_drawing_selection import ProcessingDrawingSelection
from tests.test_demo_interpretation_api import synthetic_plan
from tests.test_demo_processing_worker import floor_plan_png
from app.ai.floor_plan_interpretation import interpret_floor_plan_demo


@pytest.fixture
def drawing_context(tmp_path,monkeypatch):
    engine = get_engine()
    if engine.url.database != 'ved_electrical_verify' or engine.url.username != 'ved_test':
        pytest.fail('Run drawing selection tests through the isolated test runner.')
    ProcessingDrawingSelection.__table__.create(engine, checkfirst=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')
    marker = uuid4().hex
    roles = {r.name:r for r in session.scalars(select(Role)).all()}
    owner = User(oauth_provider=marker,oauth_subject='owner',role=roles['DESIGNER'])
    other = User(oauth_provider=marker,oauth_subject='other',role=roles['DESIGNER'])
    admin = User(oauth_provider=marker,oauth_subject='admin',role=roles['ADMIN'])
    project = Project(owner=owner,name='Drawing selection test')
    floor = ProjectFloor(project=project,name='Ground',sort_order=0)
    content = floor_plan_png()
    upload = tmp_path/'uploads'; processed = tmp_path/'processed'
    original = upload/'originals'/f'{marker}.png'
    artifact_file = processed/'normalized'/f'{marker}.png'
    for path in (original,artifact_file):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
    plan = FloorPlan(project_floor=floor,original_filename='synthetic.png',
        storage_path=f'originals/{marker}.png',mime_type='image/png',file_size=len(content),processing_status='processed')
    session.add_all([plan,other,admin]); session.flush()
    source = FloorPlanSource(floor_plan_id=plan.id,original_sha256=sha256(content).hexdigest())
    session.add(source); session.flush()
    pages = [FloorPlanPage(floor_plan_source_id=source.id,page_number=i) for i in (1,2,3)]
    prior = ProcessingJob(floor_plan_id=plan.id,job_type='floor_plan_analysis',status='completed',progress=100)
    session.add_all([*pages,prior]); session.flush()
    artifact = ProcessingArtifact(processing_job_id=prior.id,floor_plan_page_id=pages[1].id,
        artifact_kind='normalized_image',relative_path=f'normalized/{marker}.png',mime_type='image/png',
        byte_size=len(content),sha256=sha256(content).hexdigest(),pixel_width=400,pixel_height=300)
    session.add(artifact); session.flush()
    candidate = build_candidate_envelope(interpret_floor_plan_demo(synthetic_plan()),CandidateHostProvenance(
        candidate_run_id=marker,processing_job_id=prior.id,floor_plan_source_id=source.id,
        floor_plan_page_id=pages[1].id,source_artifact_id=artifact.id,source_page_number=2,
        source_sha256=source.original_sha256,source_artifact_sha256=artifact.sha256,
        expected_width_pixels=400,expected_height_pixels=300,model_release_id=detector.PROVIDER,
        base_model_revision='synthetic-test',adapter_revision=None,prompt_version='synthetic-test',
        runtime_version='synthetic-test',inference_parameters=(),created_at=datetime.now(UTC)))
    serialized = candidate.model_dump_json()
    run = FloorPlanInterpretationRun(candidate_run_id=marker,processing_job_id=prior.id,
        floor_plan_id=plan.id,floor_plan_page_id=pages[1].id,source_artifact_id=artifact.id,
        provider=detector.PROVIDER,candidate_sha256=sha256(serialized.encode()).hexdigest(),candidate_json=serialized)
    session.add(run); session.flush()
    review_json = '{"fixture":"immutable existing review"}'
    review = FloorPlanInterpretationReview(interpretation_run_id=run.id,revision_number=1,
        reviewed_by_user_id=owner.id,review_complete=False,approved_for_layout=False,
        review_json=review_json,review_sha256=sha256(review_json.encode()).hexdigest())
    geometry = json.loads((Path(__file__).resolve().parents[2]/'fixtures/canonical_geometry_v1.json').read_text())
    geometry.update(project_id=project.id,floor_plan_id=plan.id)
    geometry['floor']['project_floor_id'] = floor.id
    layout = LayoutVersion(project_id=project.id,project_floor_id=floor.id,floor_plan_id=plan.id,
        version_number=1,schema_version=1,is_current=True,geometry_document=geometry)
    session.add_all([review,layout]); session.commit()
    settings = Settings(_env_file=None,app_env='development',upload_dir=upload,processed_dir=processed,
        auto_start_interpretation_worker=False,auto_start_demo_worker=False)
    # Queue/auth/source tests must not require installed model checkpoint files.
    monkeypatch.setattr(detector,'verify_artifacts',lambda:{
        i:(f'Fixture {i}',f'drawing:L{i}') for i in range(56)})
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda:session
    app.dependency_overrides[get_current_user] = lambda:owner
    client = TestClient(app)
    data = dict(intent='process_drawing_region',candidate_run_id=marker,
        expected_source_artifact_sha256=artifact.sha256,region=dict(x=50,y=40,width=300,height=220),
        request_id=str(uuid4()))
    try:
        yield dict(client=client,url=f'/api/floor-plans/{plan.id}/process',data=data,session=session,
            app=app,owner=owner,other=other,admin=admin,plan=plan,run=run,review=review,layout=layout,
            original=original,artifact_file=artifact_file,prior=prior,pages=pages,artifact=artifact)
    finally:
        client.close(); session.close(); transaction.rollback(); connection.close()


def test_region_queue_selects_only_bound_page_and_preserves_existing_truth(drawing_context):
    c = drawing_context
    prior = (c['original'].read_bytes(),c['artifact_file'].read_bytes(),c['run'].candidate_json,
        c['run'].candidate_sha256,c['review'].review_json,c['review'].review_sha256,
        deepcopy(c['layout'].geometry_document),c['layout'].version_number)
    reply = c['client'].post(c['url'],json=c['data'])
    assert reply.status_code == 202,reply.text
    job_id = reply.json()['job_id']
    assert job_id != c['prior'].id
    rows = c['session'].scalars(select(InterpretationPageOutcome).where(
        InterpretationPageOutcome.processing_job_id==job_id).order_by(InterpretationPageOutcome.page_number)).all()
    assert [(r.page_number,r.selection_state,r.status) for r in rows] == [
        (1,'skipped','skipped'),(2,'selected','queued'),(3,'skipped','skipped')]
    selection = c['session'].get(ProcessingDrawingSelection,job_id)
    assert selection.source_run_id == c['run'].id
    assert selection.requested_by_user_id == c['owner'].id
    assert selection.source_artifact_sha256 == c['artifact'].sha256
    assert (selection.x_pixels,selection.y_pixels,selection.width_pixels,selection.height_pixels) == (50,40,300,220)
    assert len(c['session'].scalars(select(ProcessingDrawingSelection)).all()) == 1
    c['session'].expire_all()
    assert (c['original'].read_bytes(),c['artifact_file'].read_bytes(),c['run'].candidate_json,
        c['run'].candidate_sha256,c['review'].review_json,c['review'].review_sha256,
        c['layout'].geometry_document,c['layout'].version_number) == prior
    assert c['layout'].is_current is True
    assert c['prior'].status == 'completed'


def test_region_retry_reuses_job_after_completion_and_rejects_changed_payload(drawing_context):
    c = drawing_context
    first = c['client'].post(c['url'],json=c['data'])
    assert first.status_code == 202,first.text
    retry = c['client'].post(c['url'],json=c['data'])
    assert retry.status_code == 202,retry.text
    assert retry.json()['job_id'] == first.json()['job_id']
    job = c['session'].get(ProcessingJob,first.json()['job_id'])
    job.status='completed'; job.progress=100; c['session'].commit()
    retry = c['client'].post(c['url'],json=c['data'])
    assert retry.status_code == 202,retry.text
    assert retry.json()['job_id'] == job.id
    assert retry.json()['status'] == 'completed'
    changed = deepcopy(c['data']); changed['region']['width'] -= 1
    assert c['client'].post(c['url'],json=changed).status_code == 409
    assert len(c['session'].scalars(select(ProcessingDrawingSelection)).all()) == 1
    assert len(c['session'].scalars(select(ProcessingJob)).all()) == 2


@pytest.mark.parametrize('identity,status',[('other',404),('admin',403)])
def test_region_selection_requires_designer_owner(drawing_context,identity,status):
    c = drawing_context
    c['app'].dependency_overrides[get_current_user] = lambda:c[identity]
    assert c['client'].post(c['url'],json=c['data']).status_code == status
    assert not c['session'].scalars(select(ProcessingDrawingSelection)).all()


def test_region_selection_rejects_unknown_candidate_and_production(drawing_context):
    c = drawing_context
    unknown = deepcopy(c['data']); unknown['candidate_run_id']=uuid4().hex
    assert c['client'].post(c['url'],json=unknown).status_code == 404
    c['app'].state.settings = c['app'].state.settings.model_copy(update={'app_env':'production'})
    reply = c['client'].post(c['url'],json=c['data'])
    assert reply.status_code == 422,reply.text
    assert not c['session'].scalars(select(ProcessingDrawingSelection)).all()


def test_region_selection_rejects_existing_candidate_from_foreign_floor_plan(drawing_context):
    c = drawing_context
    project = Project(owner=c['other'],name='Foreign candidate isolation')
    floor = ProjectFloor(project=project,name='Foreign floor',sort_order=0)
    plan = FloorPlan(project_floor=floor,original_filename='foreign.png',storage_path='originals/foreign.png',
        mime_type='image/png',file_size=12,processing_status='processed')
    c['session'].add(plan); c['session'].commit()
    c['app'].dependency_overrides[get_current_user] = lambda:c['other']
    reply = c['client'].post(f'/api/floor-plans/{plan.id}/process',json=c['data'])
    assert reply.status_code == 404,reply.text
    assert not c['session'].scalars(select(ProcessingDrawingSelection)).all()


@pytest.mark.parametrize('change',[
    {'expected_source_artifact_sha256':'0'*64},
    {'region':dict(x=350,y=40,width=100,height=220)},
    {'region':dict(x=50,y=250,width=300,height=100)},
    {'region':dict(x=-1,y=40,width=300,height=220)},
    {'region':dict(x=50,y=40,width=0,height=220)},
    {'region':dict(x=True,y=40,width=300,height=220)},
    {'region':dict(x=50,y=40,width=300,height=220,unknown=1)},
    {'candidate_run_id':'g'*32}, {'request_id':'invalid'},
])
def test_region_selection_rejects_stale_source_and_invalid_bounds_before_queue(drawing_context,change):
    c = drawing_context
    data = deepcopy(c['data']); data.update(change)
    reply = c['client'].post(c['url'],json=data)
    assert reply.status_code in (409,422),reply.text
    assert not c['session'].scalars(select(ProcessingDrawingSelection)).all()
    assert len(c['session'].scalars(select(ProcessingJob)).all()) == 1
