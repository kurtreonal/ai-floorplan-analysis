"""Synthetic, transaction-isolated lifecycle checks. No real upload is removed."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from tests.test_routing_api import context
from tests.test_estimates import estimate_context, source_schema
from app.api.dependencies import get_current_user
from app.models import (FloorPlan, FloorPlanLifecycleEvent, LayoutVersion, ProcessingJob,
                        ProcessingJobAttempt, ProcessingJobCancellation)
from app.repositories.floor_plan_lifecycle_repository import lock_active_plan
from app.repositories.layout_version_repository import list_current_versions
from app.repositories.routing_repository import current_layout_ids
from app.services.processing_execution_service import (ProcessingExecutionError,
    claim_processing_job, finish_processing_attempt, heartbeat_processing_attempt)


@pytest.fixture(autouse=True)
def lifecycle_schema():
    from app.core.database import get_engine
    engine = get_engine()
    assert engine.url.database == 'ved_electrical_verify' and engine.url.username == 'ved_test'
    FloorPlanLifecycleEvent.__table__.create(engine, checkfirst=True)


def urls(snapshot):
    base = f'/api/projects/{snapshot.project_id}'
    return base, f'{base}/floor-plans/{snapshot.floor_plan_id}'


def request(revision=0):
    return dict(expected_revision=revision, request_id=str(uuid4()))


def test_remove_restore_preserves_plan_floor_layout_and_other_upload(context, tmp_path):
    client, _, _, session, snapshot, *_ = context
    base, url = urls(snapshot)
    plan = session.get(FloorPlan, snapshot.floor_plan_id)
    original = tmp_path / 'original.png'
    original.write_bytes(b'original source unchanged')
    before = (plan.storage_path, snapshot.geometry_document, snapshot.is_current)
    sibling = FloorPlan(project_floor_id=snapshot.project_floor_id, original_filename='other.png',
        storage_path='originals/other.png', mime_type='image/png', file_size=3)
    session.add(sibling)
    session.commit()
    info = client.get(url + '/lifecycle').json()
    assert info['saved_layouts'] == 1 and info['revision'] == 0
    change = request()
    result = client.request('DELETE', url, json=change)
    assert result.status_code == 200, result.text
    assert result.json()['removed'] is True
    assert client.request('DELETE', url, json=change).json() == result.json()
    assert [p['id'] for p in client.get(base + '/floor-plans').json()] == [sibling.id]
    assert client.get(base + '/floor-plan-trash').json()[0]['id'] == plan.id
    session.expire_all()
    assert session.get(FloorPlan, plan.id).storage_path == before[0]
    assert session.get(LayoutVersion, snapshot.id).geometry_document == before[1]
    assert session.get(LayoutVersion, snapshot.id).is_current == before[2]
    assert original.read_bytes() == b'original source unchanged'
    assert list_current_versions(session, project_floor_id=snapshot.project_floor_id) == ()
    assert current_layout_ids(session, snapshot.project_id, [snapshot.project_floor_id]) == {}
    assert lock_active_plan(session, plan.id) is None
    restored = client.post(url + '/restore', json=request(1))
    assert restored.status_code == 200 and restored.json()['revision'] == 2
    assert {p['id'] for p in client.get(base + '/floor-plans').json()} == {plan.id, sibling.id}
    assert len(list_current_versions(session, project_floor_id=snapshot.project_floor_id)) == 1
    assert client.get(base + '/floor-plan-trash').json() == []
    # Old requests cannot undo a later restore (ABA protection).
    assert client.request('DELETE', url, json=change).status_code == 409
    assert session.scalar(select(func.count()).select_from(FloorPlanLifecycleEvent)) == 2


def test_owner_admin_validation_and_stale_preconditions(context):
    client, _, _, session, snapshot, app, other, admin = context
    _, url = urls(snapshot)
    assert client.request('DELETE', url, json=request(10)).status_code == 409
    assert client.request('DELETE', url, json={}).status_code == 422
    assert client.request('DELETE', url, json=request() | {'expected_revision': True}).status_code == 422
    assert client.post(url + '/restore', json=request()).status_code == 409
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(url + '/lifecycle').status_code == 404
    assert client.request('DELETE', url, json=request()).status_code == 404
    assert client.post(url + '/restore', json=request()).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.get(url + '/lifecycle').status_code == 200
    assert client.request('DELETE', url, json=request()).status_code == 403
    assert client.post(url + '/restore', json=request()).status_code == 403
    assert session.scalar(select(func.count()).select_from(FloorPlanLifecycleEvent)) == 0


def test_removal_cancels_and_fences_active_and_queued_jobs_without_resurrection(context):
    client, _, _, session, snapshot, *_ = context
    _, url = urls(snapshot)
    job = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='queued')
    queued = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='queued')
    completed = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='completed')
    session.add_all([job, queued, completed])
    session.commit()
    claim = claim_processing_job(session, job_id=job.id, worker_identity='synthetic-worker', lease_seconds=300)
    assert client.request('DELETE', url, json=request()).status_code == 200
    session.expire_all()
    assert session.get(ProcessingJob, job.id).status == 'cancelled'
    assert session.get(ProcessingJob, queued.id).status == 'cancelled'
    assert session.get(ProcessingJob, completed.id).status == 'completed'
    attempt = session.get(ProcessingJobAttempt, claim.attempt_id)
    assert attempt.status == 'cancelled' and attempt.active_marker is None
    assert session.scalar(select(func.count()).select_from(ProcessingJobCancellation)) == 2
    with pytest.raises(ProcessingExecutionError):
        heartbeat_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity='synthetic-worker',
            stage='persistence', lease_seconds=300)
    with pytest.raises(ProcessingExecutionError):
        finish_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity='synthetic-worker', outcome='succeeded')
    with pytest.raises(ProcessingExecutionError):
        claim_processing_job(session, job_id=queued.id, worker_identity='late-worker', lease_seconds=300)
    # Removed plans cannot start a new analysis; no actual detector runs here.
    assert client.post(f'/api/floor-plans/{snapshot.floor_plan_id}/process').status_code == 404
    assert client.post(url + '/restore', json=request(1)).status_code == 200
    assert session.get(ProcessingJob, job.id).status == 'cancelled'
    assert session.get(ProcessingJob, queued.id).status == 'cancelled'


def test_candidate_and_artifact_publication_rejected_after_removal(context):
    from types import SimpleNamespace
    from app.models import FloorPlanInterpretationRun, ProcessingArtifact
    from app.services.interpretation_processing_service import _persist_fenced_run, InterpretationProcessingError
    from app.services.processing_artifact_service import register_processing_artifact, ProcessingArtifactError
    client, _, _, session, snapshot, *_ = context
    _, url = urls(snapshot)
    job = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='queued')
    session.add(job)
    session.commit()
    claim = claim_processing_job(session, job_id=job.id, worker_identity='synthetic-worker', lease_seconds=300)
    assert client.request('DELETE', url, json=request()).status_code == 200
    run = SimpleNamespace(floor_plan_page_id=1)
    with pytest.raises(InterpretationProcessingError):
        _persist_fenced_run(session, claim=claim, worker_identity='synthetic-worker', run=run)
    with pytest.raises(ProcessingArtifactError):
        register_processing_artifact(session, processing_job=job, floor_plan_id=snapshot.floor_plan_id,
            page_number=1, artifact_kind='normalized_image', processed_directory=None,
            relative_path='must-not-register.png', mime_type='image/png')
    assert session.scalar(select(func.count()).select_from(FloorPlanInterpretationRun)) == 0
    assert session.scalar(select(func.count()).select_from(ProcessingArtifact)) == 0
    assert client.post(url + '/restore', json=request(1)).status_code == 200
    # Restore opens the plan, not an old worker's cancelled job/publication channel.
    with pytest.raises(InterpretationProcessingError):
        _persist_fenced_run(session, claim=claim, worker_identity='synthetic-worker', run=run)
    with pytest.raises(ProcessingArtifactError):
        register_processing_artifact(session, processing_job=job, floor_plan_id=snapshot.floor_plan_id,
            page_number=1, artifact_kind='normalized_image', processed_directory=None,
            relative_path='must-not-register-after-restore.png', mime_type='image/png')


def test_job_completion_racing_removal_is_serialized():
    """Real separate MySQL transactions; no detector or reviewed user data."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from app.core.database import get_engine
    from app.models import Project, ProjectFloor, Role, User
    from app.repositories.processing_execution_repository import lock_processing_job
    from app.schemas.floor_plan_lifecycle import FloorPlanLifecycleRequest
    from app.services.floor_plan_lifecycle_service import change_plan_state
    engine = get_engine()
    assert engine.url.database == 'ved_electrical_verify' and engine.url.username == 'ved_test'
    with Session(engine, expire_on_commit=False) as session:
        role = session.scalar(select(Role).where(Role.name == 'DESIGNER'))
        user = User(oauth_provider='plan-lifecycle-race', oauth_subject=uuid4().hex, role=role)
        project = Project(owner=user, name='Synthetic lifecycle race')
        floor = ProjectFloor(project=project, name='Synthetic')
        plan = FloorPlan(project_floor=floor, original_filename='synthetic.png', storage_path='originals/synthetic.png',
                         mime_type='image/png', file_size=1)
        session.add(plan)
        session.flush()
        job = ProcessingJob(floor_plan_id=plan.id, job_type='floor_plan_analysis', status='queued')
        session.add(job)
        session.commit()
        ids = (user.id, project.id, floor.id, plan.id, job.id)
        claim = claim_processing_job(session, job_id=job.id, worker_identity='race-worker', lease_seconds=300)
    held, release, removing = Event(), Event(), Event()
    def finish():
        with Session(engine) as session:
            lock_processing_job(session, job_id=ids[4])
            held.set()
            assert release.wait(10)
            finish_processing_attempt(session, attempt_id=claim.attempt_id, worker_identity='race-worker', outcome='succeeded')
    def remove():
        with Session(engine) as session:
            owner = session.get(User, ids[0])
            removing.set()
            return change_plan_state(session, current_user=owner, project_id=ids[1], floor_plan_id=ids[3],
                request=FloorPlanLifecycleRequest(**request()), remove=True)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            published = pool.submit(finish)
            assert held.wait(10)
            removed = pool.submit(remove)
            assert removing.wait(10)
            release.set()
            published.result(timeout=15)
            assert removed.result(timeout=15).removed
        with Session(engine) as session:
            assert session.get(ProcessingJob, ids[4]).status == 'completed'
            assert latest_event_for_test(session, ids[3]).action == 'removed'
    finally:
        release.set()
        with Session(engine) as session:
            assert session.get(User, ids[0]).oauth_provider == 'plan-lifecycle-race'
            session.execute(delete(FloorPlanLifecycleEvent).where(FloorPlanLifecycleEvent.floor_plan_id == ids[3]))
            session.execute(delete(ProcessingJobCancellation).where(ProcessingJobCancellation.processing_job_id == ids[4]))
            session.execute(delete(ProcessingJobAttempt).where(ProcessingJobAttempt.processing_job_id == ids[4]))
            session.execute(delete(ProcessingJob).where(ProcessingJob.id == ids[4]))
            session.execute(delete(FloorPlan).where(FloorPlan.id == ids[3]))
            session.execute(delete(ProjectFloor).where(ProjectFloor.id == ids[2]))
            session.execute(delete(Project).where(Project.id == ids[1]))
            session.execute(delete(User).where(User.id == ids[0]))
            session.commit()


def latest_event_for_test(session, plan_id):
    return session.scalar(select(FloorPlanLifecycleEvent).where(FloorPlanLifecycleEvent.floor_plan_id == plan_id))


def test_removal_between_claim_and_page_initialization_cannot_revive_page(context, monkeypatch):
    from app.core.config import Settings
    from app.models import InterpretationPageOutcome
    from app.services import interpretation_processing_service as service
    client, _, _, session, snapshot, *_ = context
    _, url = urls(snapshot)
    job = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='queued')
    session.add(job)
    session.commit()
    original_claim = service.claim_processing_job
    def claim_then_remove(*args, **kwargs):
        claim = original_claim(*args, **kwargs)
        assert client.request('DELETE', url, json=request()).status_code == 200
        return claim
    monkeypatch.setattr(service, 'claim_processing_job', claim_then_remove)
    with pytest.raises(service.InterpretationProcessingError):
        service.process_interpretation_job(session, job_id=job.id, worker_identity='late-initializer',
            settings=Settings(_env_file=None, auto_start_interpretation_worker=False))
    assert session.get(ProcessingJob, job.id).status == 'cancelled'
    assert session.scalar(select(func.count()).select_from(InterpretationPageOutcome)) == 0


def test_failed_removal_rolls_back_cancellation_and_history(context, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    client, _, _, session, snapshot, *_ = context
    _, url = urls(snapshot)
    job = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='queued')
    session.add(job)
    session.commit()
    add = session.add
    def fail_history(value, *args, **kwargs):
        if isinstance(value, FloorPlanLifecycleEvent):
            raise SQLAlchemyError('synthetic private failure')
        return add(value, *args, **kwargs)
    monkeypatch.setattr(session, 'add', fail_history)
    result = client.request('DELETE', url, json=request())
    assert result.status_code == 503 and 'synthetic private failure' not in result.text
    assert session.get(ProcessingJob, job.id).status == 'queued'
    assert session.scalar(select(func.count()).select_from(FloorPlanLifecycleEvent)) == 0
    assert session.scalar(select(func.count()).select_from(ProcessingJobCancellation)) == 0


def test_saved_estimate_remains_readable_and_route_becomes_stale_until_restore(estimate_context):
    ctx, payload, _ = estimate_context
    client, route_url, _, session, snapshot, *_ = ctx
    base, url = urls(snapshot)
    estimates = f'{base}/estimates'
    created = client.post(estimates, json=payload)
    assert created.status_code == 201, created.text
    saved = created.json()
    before_route = client.get(route_url).json()
    assert not before_route['stale']
    assert client.request('DELETE', url, json=request()).status_code == 200
    assert client.get(f'{estimates}/{saved["id"]}').json() == saved
    assert client.get(estimates).json() == [saved]
    assert client.get(route_url).json()['stale']
    assert client.post(url + '/restore', json=request(1)).status_code == 200
    assert client.get(f'{estimates}/{saved["id"]}').json() == saved
    assert client.get(route_url).json() == before_route


def test_candidate_and_review_history_survive_removal_and_restore(context):
    from hashlib import sha256
    from app.models import (FloorPlanSource, FloorPlanPage, ProcessingArtifact,
        FloorPlanInterpretationRun, FloorPlanInterpretationReview)
    client, _, _, session, snapshot, app, *_ = context
    _, url = urls(snapshot)
    owner = app.dependency_overrides[get_current_user]()
    job = ProcessingJob(floor_plan_id=snapshot.floor_plan_id, job_type='floor_plan_analysis', status='completed')
    source = FloorPlanSource(floor_plan_id=snapshot.floor_plan_id, original_sha256='a'*64)
    session.add_all([job, source])
    session.flush()
    page = FloorPlanPage(floor_plan_source_id=source.id, page_number=1)
    session.add(page)
    session.flush()
    artifact = ProcessingArtifact(processing_job_id=job.id, floor_plan_page_id=page.id,
        artifact_kind='normalized_image', relative_path=uuid4().hex+'.png', mime_type='image/png',
        byte_size=12, sha256='b'*64, pixel_width=100, pixel_height=80)
    session.add(artifact)
    session.flush()
    document = '{"synthetic_preservation_test": true}'
    digest = sha256(document.encode()).hexdigest()
    run = FloorPlanInterpretationRun(candidate_run_id=uuid4().hex, processing_job_id=job.id,
        floor_plan_id=snapshot.floor_plan_id, floor_plan_page_id=page.id, source_artifact_id=artifact.id,
        provider='synthetic-history', candidate_sha256=digest, candidate_json=document)
    session.add(run)
    session.flush()
    review = FloorPlanInterpretationReview(interpretation_run_id=run.id, revision_number=1,
        reviewed_by_user_id=owner.id, review_complete=True, approved_for_layout=False,
        review_sha256=digest, review_json=document)
    session.add(review)
    session.commit()
    assert client.get(url+'/lifecycle').json()['saved_reviews'] == 1
    for method, target, revision in [('DELETE', url, 0), ('POST', url+'/restore', 1)]:
        assert client.request(method, target, json=request(revision)).status_code == 200
        session.expire_all()
        assert session.get(FloorPlanInterpretationRun, run.id).candidate_json == document
        assert session.get(FloorPlanInterpretationReview, review.id).review_json == document
        assert session.get(ProcessingJob, job.id).status == 'completed'
