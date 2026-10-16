"""Technical coverage, not independent drawing recognition measurements."""
import cv2
import numpy as np
import pytest
from tests.test_wiring_recovery import curved
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring,RecoveryLimits
from app.ai.floor_plan_interpretation.input_profile import inspect_input_pixels
from app.services.connectivity_summary_service import summarize_connectivity
from app.services.wiring_recovery_service import RecoveryCheckpointStore


def test_missing_bounds_and_empty_devices_are_not_successful_connectivity():
    image,payload=curved();raw=payload.model_dump(mode='json')
    raw['symbols']['items'][0]['bounds']=None
    result=recover_wiring(FloorPlanInterpretationPayload.model_validate(raw),image)
    assert result.observed_routes.recovery.devices[0].reason=='missing_symbol_bounds'
    assert result.observed_routes.recovery.stop_reason!='converged'
    raw['symbols']['items']=[];raw['symbols']['state']='empty'
    result=recover_wiring(FloorPlanInterpretationPayload.model_validate(raw),image)
    summary=summarize_connectivity([result.model_dump(mode='json')],expected_pages=1)
    assert summary.state=='unavailable' and summary.search_incomplete


def test_failed_methods_cannot_turn_into_no_wire_generated_eligibility(monkeypatch):
    from app.ai.floor_plan_interpretation import wiring_recovery
    image,payload=curved()
    monkeypatch.setattr(wiring_recovery,'local_paths',lambda *a:(_ for _ in ()).throw(MemoryError()))
    result=recover_wiring(payload,image)
    assert all(d.reason=='recovery_method_failed' for d in result.observed_routes.recovery.devices)
    summary=summarize_connectivity([result.model_dump(mode='json')],expected_pages=3)
    assert summary.unassessed_pages==2 and summary.search_incomplete and summary.state=='unresolved'


@pytest.mark.parametrize('scale,rotate',[(.5,False),(1,False),(2,False),(1,True),(2,True)])
def test_native_curve_at_multiple_resolutions_and_quarter_rotation(scale,rotate):
    image,payload=curved();raw=payload.model_dump(mode='json')
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    width,height=image.shape[1],image.shape[0]
    if rotate:image=np.rot90(image).copy()
    def point(p):
        x,y=p['x']*scale,p['y']*scale
        return dict(x=y,y=width-1-x) if rotate else dict(x=x,y=y)
    for symbol in raw['symbols']['items']:
        symbol['center']=point(symbol['center']);b=symbol['bounds']
        corners=[point(dict(x=x,y=y)) for x in (b['x'],b['x']+b['width']) for y in (b['y'],b['y']+b['height'])]
        xs=[p['x'] for p in corners];ys=[p['y'] for p in corners]
        symbol['bounds']=dict(x=min(xs),y=min(ys),width=max(xs)-min(xs),height=max(ys)-min(ys))
    raw['source_plane'].update(width_pixels=image.shape[1],height_pixels=image.shape[0])
    for r in raw['regions']:
        r['bounds']=dict(x=0,y=0,width=image.shape[1],height=image.shape[0])
    transformed=FloorPlanInterpretationPayload.model_validate(raw)
    result=recover_wiring(transformed,image)
    assert {d.state for d in result.observed_routes.recovery.devices}=={'observed_recovered'}
    assert result.source_plane==transformed.source_plane
    profile=inspect_input_pixels(image,result)
    assert profile['orientation_action']=='preserve_source_plane' and profile['physical_dpi'] is None


def test_checkpoint_invalidation_includes_configuration_version_and_base_geometry(tmp_path,monkeypatch):
    from app.services import wiring_recovery_service as service
    image,payload=curved();limits=RecoveryLimits()
    store=RecoveryCheckpointStore(tmp_path,job_id=1,page_id=1,source_sha256='a'*64,payload=payload,limits=limits)
    recover_wiring(payload,image,checkpoint=store.save)
    assert store.load()
    assert RecoveryCheckpointStore(tmp_path,job_id=1,page_id=1,source_sha256='a'*64,payload=payload,limits=RecoveryLimits(maximum_windows=2)).load() is None
    changed=payload.model_copy(update={'warnings':()})
    if changed==payload:
        raw=payload.model_dump(mode='json');raw['symbols']['items'][0]['center']['x']+=1
        changed=FloorPlanInterpretationPayload.model_validate(raw)
    assert RecoveryCheckpointStore(tmp_path,job_id=1,page_id=1,source_sha256='a'*64,payload=changed,limits=limits).load() is None
    monkeypatch.setattr(service,'VERSION','changed-version')
    assert RecoveryCheckpointStore(tmp_path,job_id=1,page_id=1,source_sha256='a'*64,payload=payload,limits=limits).load() is None


def test_legacy_responses_are_unchanged_and_truncated_search_never_claims_complete():
    assert summarize_connectivity([{}],expected_pages=1) is None
    image,payload=curved();result=recover_wiring(payload,image).model_dump(mode='json')
    result['observed_routes']['state']='partial';result['observed_routes']['truncated']=True
    summary=summarize_connectivity([result],expected_pages=1)
    assert summary.connected_devices==2 and summary.state=='unresolved' and summary.search_incomplete


def test_targeted_dash_method_recovers_repeated_strokes_without_turning_crossings_into_junctions():
    from tests.test_automatic_wiring import example
    image,payload=example();image[:]=255
    for x in range(68,252,14):cv2.line(image,(x,100),(min(x+8,252),100),(0,0,0),1)
    result=recover_wiring(payload,image)
    assert any(r.line_style=='dashed' for r in result.observed_routes.segments)
    assert len({c.to_ref for c in result.observed_routes.connections if c.ambiguity=='unambiguous'})==2
    assert not result.observed_routes.junctions


def test_descriptive_orientation_never_rotates_or_rescales_source_pixels():
    image,payload=curved();image[:]=255
    cv2.line(image,(30,20),(240,175),(0,0,0),2)
    before=image.copy();profile=inspect_input_pixels(image,payload)
    assert 30<profile['dominant_axis_degrees']<40
    assert np.array_equal(image,before)
