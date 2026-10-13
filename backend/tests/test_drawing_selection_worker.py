"""Selected-region worker integration: isolated runner only, no real model."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest
from sqlalchemy import select

from app.ai.floor_plan_interpretation import multiclass_symbol_detector as detector
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationCandidate
from app.ai.floor_plan_interpretation.experimental_symbol_detector import ExperimentalDetectorUnavailable
from app.models import (FloorPlanInterpretationRun, InterpretationPageOutcome, ProcessingArtifact,
    ProcessingJob, ProcessingJobAttempt, FloorPlanInterpretationReview, LayoutVersion)
from app.models.processing_drawing_selection import ProcessingDrawingSelection
from app.services import interpretation_processing_service as service
from app.services.interpretation_job_configuration_service import requested_configuration
from tests.test_drawing_selection_api import drawing_context


def enqueue(c, *, demo=False):
    response = c['client'].post(c['url'],json=c['data'])
    assert response.status_code == 202,response.text
    job_id = response.json()['job_id']
    if demo:
        provider,release,digest = requested_configuration(c['app'].state.settings)
        assert provider == 'demo_cv_baseline'
        for page in c['session'].scalars(select(InterpretationPageOutcome).where(
                InterpretationPageOutcome.processing_job_id==job_id)):
            page.provider=provider; page.model_release_id=release; page.configuration_sha256=digest
        c['session'].commit()
    return job_id


def process(c, job_id):
    return service.process_interpretation_job(c['session'],job_id=job_id,
        worker_identity='drawing-selection-test-worker',settings=c['app'].state.settings)


def source_rgb(c):
    with Image.open(BytesIO(c['artifact_file'].read_bytes())) as image:
        return np.array(image.convert('RGB'))


def assert_persisted_source_identity(c,job_id,run):
    candidate = FloorPlanInterpretationCandidate.model_validate_json(run.candidate_json)
    artifact = c['session'].get(ProcessingArtifact,run.source_artifact_id)
    assert artifact.id != c['artifact'].id
    assert artifact.processing_job_id == job_id
    assert artifact.relative_path != c['artifact'].relative_path
    assert artifact.sha256 == c['artifact'].sha256
    assert (artifact.pixel_width,artifact.pixel_height) == (400,300)
    cloned = c['app'].state.settings.processed_dir/artifact.relative_path
    assert cloned.read_bytes() == c['artifact_file'].read_bytes()
    assert candidate.provenance.source_artifact_id == artifact.id
    assert candidate.provenance.source_artifact_sha256 == artifact.sha256
    assert candidate.provenance.processing_job_id == job_id
    assert candidate.provenance.source_page_number == 2
    assert candidate.provenance.floor_plan_page_id == c['pages'][1].id
    assert (candidate.payload.source_plane.width_pixels,candidate.payload.source_plane.height_pixels) == (400,300)
    assert candidate.payload.document_state == 'partial'
    assert any(w.code=='explicit_drawing_region' for w in candidate.payload.warnings)
    names = [p.name for p in candidate.provenance.inference_parameters]
    assert names == sorted(names)
    parameters = {p.name:p.value for p in candidate.provenance.inference_parameters}
    selection = c['session'].get(ProcessingDrawingSelection,job_id)
    assert parameters['drawing-selection-sha256'] == selection.selection_sha256
    assert parameters['source-selection-run-id'] == str(c['run'].id)
    assert json.loads(parameters['drawing-region']) == c['data']['region']
    assert c['session'].get(ProcessingJob,job_id).status == 'completed'
    pages = c['session'].scalars(select(InterpretationPageOutcome).where(
        InterpretationPageOutcome.processing_job_id==job_id).order_by(InterpretationPageOutcome.page_number)).all()
    assert [(p.page_number,p.status) for p in pages] == [(1,'skipped'),(2,'completed'),(3,'skipped')]
    assert sha256(run.candidate_json.encode()).hexdigest() == run.candidate_sha256
    return candidate


def test_selected_multiclass_worker_observes_only_crop_and_restores_raw_coordinates(drawing_context,monkeypatch):
    c = drawing_context
    before = (c['original'].read_bytes(),c['artifact_file'].read_bytes(),c['run'].candidate_json,
        c['review'].review_json,deepcopy(c['layout'].geometry_document))
    job_id = enqueue(c)
    expected = source_rgb(c)[40:260,50:350]
    row = dict(class_id=0,bbox=(10,20,30,40),score=.8,tile_origin=(0,0))
    before_row = deepcopy(row)
    observed = []

    def locate(rgb):
        observed.append(rgb.copy())
        np.testing.assert_array_equal(rgb,expected)
        return (row,),False

    monkeypatch.setattr(detector,'locate',locate)
    run = process(c,job_id)
    assert len(observed) == 1
    candidate = assert_persisted_source_identity(c,job_id,run)
    symbols = candidate.payload.symbols.items
    assert len(symbols) == 1
    bounds = symbols[0].bounds
    assert (bounds.x,bounds.y,bounds.width,bounds.height) == (60,60,20,20)
    assert symbols[0].mapping_state == 'unknown'
    assert symbols[0].catalog_class_id is None
    assert row == before_row
    assert (c['original'].read_bytes(),c['artifact_file'].read_bytes(),c['run'].candidate_json,
        c['review'].review_json,c['layout'].geometry_document) == before


def test_selected_demo_worker_uses_crop_with_full_source_plane(drawing_context,monkeypatch):
    c = drawing_context
    job_id = enqueue(c,demo=True)
    expected = source_rgb(c)[40:260,50:350]
    # Observe the actual region interpreter boundary rather than faking output.
    original = service.interpret_floor_plan_demo
    observed = []

    def interpret(rgb, **kwargs):
        observed.append(rgb.copy())
        np.testing.assert_array_equal(rgb,expected)
        assert kwargs == {'selected_drawing': True}
        return original(rgb, **kwargs)

    monkeypatch.setattr(service,'interpret_floor_plan_demo',interpret)
    monkeypatch.setattr(detector,'locate',lambda *_:pytest.fail('Demo selection must not invoke model inference.'))
    run = process(c,job_id)
    assert len(observed) == 1
    candidate = assert_persisted_source_identity(c,job_id,run)
    assert run.provider == 'demo_cv_baseline'
    assert {p.name:p.value for p in candidate.provenance.inference_parameters}[
        'geometry-evidence-version'] == service.CV_EVIDENCE_VERSION
    for wall in candidate.payload.walls.items:
        assert 50<=wall.start.x<=350 and 40<=wall.start.y<=260
        assert 50<=wall.end.x<=350 and 40<=wall.end.y<=260


def test_selected_worker_retry_reuses_cloned_artifact_identity(drawing_context,monkeypatch):
    c = drawing_context
    job_id = enqueue(c)
    calls = []

    def interrupted_then_successful(rgb):
        calls.append(rgb.shape)
        if len(calls)==1:
            raise ExperimentalDetectorUnavailable('SYMBOL_INFERENCE_FAILED')
        return (),False

    monkeypatch.setattr(detector,'locate',interrupted_then_successful)
    with pytest.raises(service.InterpretationProcessingError):
        process(c,job_id)
    first = c['session'].scalars(select(ProcessingArtifact).where(
        ProcessingArtifact.processing_job_id==job_id)).all()
    assert len(first)==1
    artifact_id,path,digest = first[0].id,first[0].relative_path,first[0].sha256
    run = process(c,job_id)
    assert_persisted_source_identity(c,job_id,run)
    artifacts = c['session'].scalars(select(ProcessingArtifact).where(
        ProcessingArtifact.processing_job_id==job_id)).all()
    assert [(a.id,a.relative_path,a.sha256) for a in artifacts] == [(artifact_id,path,digest)]
    attempts = c['session'].scalars(select(ProcessingJobAttempt).where(
        ProcessingJobAttempt.processing_job_id==job_id).order_by(ProcessingJobAttempt.attempt_number)).all()
    assert [a.status for a in attempts] == ['failed','succeeded']


@pytest.mark.parametrize('tamper',['selection','candidate','artifact'])
def test_selected_worker_rejects_tampered_binding_without_candidate(drawing_context,monkeypatch,tamper):
    c = drawing_context
    job_id = enqueue(c)
    if tamper=='selection':
        c['session'].get(ProcessingDrawingSelection,job_id).x_pixels += 1
    elif tamper=='candidate':
        c['run'].candidate_json += ' '
    else:
        c['artifact_file'].write_bytes(c['artifact_file'].read_bytes()+b'tampered')
    c['session'].commit()
    monkeypatch.setattr(detector,'locate',lambda *_:pytest.fail('Invalid source must fail before inference.'))
    with pytest.raises(service.InterpretationProcessingError) as error:
        process(c,job_id)
    assert error.value.code == 'DRAWING_SELECTION_SOURCE_CONFLICT'
    assert not c['session'].scalars(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.processing_job_id==job_id)).all()


def test_selected_worker_rejects_unsupported_provider_before_inference(drawing_context,monkeypatch):
    c = drawing_context
    job_id = enqueue(c)
    monkeypatch.setattr(service,'pin_job_configuration',lambda *_args,**_kwargs:
        SimpleNamespace(provider='local_vlm_gateway'))
    monkeypatch.setattr(service,'_configured_local_gateway',lambda *_:
        pytest.fail('Selected drawings must not call unsupported runtime providers.'))
    monkeypatch.setattr(detector,'locate',lambda *_:pytest.fail('Unsupported provider must fail before inference.'))
    with pytest.raises(service.InterpretationProcessingError) as error:
        process(c,job_id)
    assert error.value.code == 'DRAWING_SELECTION_PROVIDER_CONFLICT'
    assert not c['session'].scalars(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.processing_job_id==job_id)).all()


def test_selected_worker_cooperative_cancel_fences_candidate_publication(drawing_context,monkeypatch):
    from app.services.processing_execution_service import request_processing_cancellation

    c = drawing_context
    job_id = enqueue(c)

    def cancel_after_inference(rgb):
        request_processing_cancellation(c['session'],current_user=c['owner'],job_id=job_id)
        return (),False

    monkeypatch.setattr(detector,'locate',cancel_after_inference)
    with pytest.raises(service.InterpretationProcessingError) as error:
        process(c,job_id)
    assert error.value.code == 'PROCESSING_CANCELLED'
    c['session'].expire_all()
    assert c['session'].get(ProcessingJob,job_id).status == 'cancelled'
    page = c['session'].scalar(select(InterpretationPageOutcome).where(
        InterpretationPageOutcome.processing_job_id==job_id,
        InterpretationPageOutcome.selection_state=='selected'))
    assert (page.status,page.candidate_run_id) == ('cancelled',None)
    attempt = c['session'].scalar(select(ProcessingJobAttempt).where(
        ProcessingJobAttempt.processing_job_id==job_id))
    assert attempt.status == 'cancelled'
    assert not c['session'].scalars(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.processing_job_id==job_id)).all()


def test_selected_worker_rejects_settings_switched_to_production_before_inference(drawing_context,monkeypatch):
    c = drawing_context
    # A demo pin isolates the selected-source development guard from the
    # separate pre-existing multiclass development-only configuration guard.
    job_id = enqueue(c,demo=True)
    c['app'].state.settings = c['app'].state.settings.model_copy(update={'app_env':'production'})
    monkeypatch.setattr(service,'interpret_floor_plan_demo',lambda *_:
        pytest.fail('Production settings must reject selection before inference.'))
    with pytest.raises(service.InterpretationProcessingError) as error:
        process(c,job_id)
    assert error.value.code == 'DRAWING_SELECTION_DEVELOPMENT_ONLY'
    assert not c['session'].scalars(select(FloorPlanInterpretationRun).where(
        FloorPlanInterpretationRun.processing_job_id==job_id)).all()


def test_selected_candidate_draft_edits_reload_without_replacing_historical_run_or_layout(drawing_context,monkeypatch):
    from app.services.demo_interpretation_service import retrieve_interpretation

    c = drawing_context
    historical = (c['run'].candidate_json,c['run'].candidate_sha256,c['review'].review_json,
        c['review'].review_sha256,deepcopy(c['layout'].geometry_document),c['original'].read_bytes())
    job_id = enqueue(c)
    rows = (dict(class_id=0,bbox=(10,20,30,40),score=.8,tile_origin=(0,0)),
            dict(class_id=0,bbox=(100,110,120,130),score=.7,tile_origin=(0,0)))
    monkeypatch.setattr(detector,'locate',lambda _rgb:(rows,False))
    run = process(c,job_id)
    new_candidate_bytes = run.candidate_json
    candidate = FloorPlanInterpretationCandidate.model_validate_json(new_candidate_bytes)
    first,second = candidate.payload.symbols.items
    path = f'/api/floor-plans/{c["plan"].id}/interpretation'
    scoped = f'{path}?processing_job_id={job_id}'
    initial = c['client'].get(scoped)
    assert initial.status_code == 200,initial.text
    assert initial.json()['processing_job_id'] == job_id
    assert initial.json()['candidate_run_id'] == run.candidate_run_id
    assert initial.json()['review'] is None
    # The old fixture review intentionally has no HTTP response schema. Read its
    # exact stored service record to prove historical job selection independently.
    old = retrieve_interpretation(c['session'],current_user=c['owner'],floor_plan_id=c['plan'].id,
                                 processing_job_id=c['prior'].id)
    assert old.run.id == c['run'].id
    assert old.candidate.model_dump_json() == historical[0]
    assert old.review.id == c['review'].id
    # Runtime wiring views are additive; immutable persisted review bytes below
    # remain the historical authority, not the derived empty wiring arrays.
    assert old.review_document == {**json.loads(historical[2]),'observed_wiring':[],'generated_wiring':[]}
    data = dict(candidate_run_id=run.candidate_run_id,expected_revision_number=None,
        review_complete=False,approved_for_layout=False,wall_thickness_meters=None,wall_height_meters=None,
        evidence_notes='Incomplete selected drawing draft; no approval or mapping implied.',
        walls=[],rooms=[],symbols=[
            dict(id=first.id,disposition='accepted',center=first.center.model_dump(),symbol_legend_id=None),
            dict(id=second.id,disposition='unresolved',center=second.center.model_dump(),symbol_legend_id=None)])
    first_save = c['client'].post(f'{path}/reviews',json=data)
    assert first_save.status_code == 201,first_save.text
    assert first_save.json()['review']['revision_number'] == 1
    first_revision = c['session'].scalar(select(FloorPlanInterpretationReview).where(
        FloorPlanInterpretationReview.interpretation_run_id==run.id))
    first_review_bytes = (first_revision.review_json,first_revision.review_sha256)
    data['expected_revision_number'] = 1
    data['symbols'][0].update(disposition='corrected',center=dict(x=85,y=95))
    data['symbols'][1]['disposition'] = 'rejected'
    data['symbols'].append(dict(id='manual-symbol-0001',disposition='added',
                                center=dict(x=200,y=180),symbol_legend_id=None))
    second_save = c['client'].post(f'{path}/reviews',json=data)
    assert second_save.status_code == 201,second_save.text
    reloaded = c['client'].get(scoped)
    assert reloaded.status_code == 200,reloaded.text
    result = reloaded.json()
    assert result['candidate_run_id'] == run.candidate_run_id
    assert result['processing_job_id'] == job_id
    assert result['review']['revision_number'] == 2
    assert result['review']['review_complete'] is False
    assert result['review']['approved_for_layout'] is False
    assert result['review']['wall_thickness_meters'] is None
    assert result['review']['wall_height_meters'] is None
    symbols = {symbol['id']:symbol for symbol in result['review']['symbols']}
    assert (symbols[first.id]['disposition'],symbols[first.id]['center']) == ('corrected',dict(x=85,y=95))
    assert symbols[second.id]['disposition'] == 'rejected'
    assert (symbols['manual-symbol-0001']['disposition'],symbols['manual-symbol-0001']['center']) == (
        'added',dict(x=200,y=180))
    assert all(symbol['symbol_legend_id'] is None for symbol in symbols.values())
    assert c['client'].get(path).json() == result
    c['session'].expire_all()
    revisions = c['session'].scalars(select(FloorPlanInterpretationReview).where(
        FloorPlanInterpretationReview.interpretation_run_id==run.id).order_by(
        FloorPlanInterpretationReview.revision_number)).all()
    assert [revision.revision_number for revision in revisions] == [1,2]
    assert (revisions[0].review_json,revisions[0].review_sha256) == first_review_bytes
    assert all(sha256(revision.review_json.encode()).hexdigest()==revision.review_sha256 for revision in revisions)
    assert run.candidate_json == new_candidate_bytes
    old = retrieve_interpretation(c['session'],current_user=c['owner'],floor_plan_id=c['plan'].id,
                                 processing_job_id=c['prior'].id)
    assert (old.run.candidate_json,old.run.candidate_sha256,old.review.review_json,
        old.review.review_sha256,c['layout'].geometry_document,c['original'].read_bytes()) == historical
    assert c['layout'].is_current is True
    assert len(c['session'].scalars(select(LayoutVersion)).all()) == 1
