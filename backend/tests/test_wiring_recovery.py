from copy import deepcopy
import cv2
import numpy as np
import pytest
from tests.test_automatic_wiring import example
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring, RecoveryLimits


def curved():
    image,payload=example();image[:]=255
    cv2.polylines(image,[np.array([(68,100),(100,100),(120,120),(120,150),(200,150),(220,130),(220,100),(252,100)])],False,(0,0,0),2)
    return image,payload


def test_local_source_curve_recovers_unique_devices_without_replacing_original_geometry():
    image,payload=curved();before=deepcopy(payload.model_dump())
    result=recover_wiring(payload,image)
    assert result.observed_routes.segments
    assert {d.state for d in result.observed_routes.recovery.devices}=={'observed_recovered'}
    assert result.observed_routes.recovery.passes[0].added_contacts==2
    assert result.observed_routes.recovery.stop_reason=='converged'
    assert payload.model_dump()==before
    assert not result.generated_routes if hasattr(result,'generated_routes') else True
    assert result.walls==payload.walls and result.symbols==payload.symbols


def test_blank_floor_is_not_declared_proof_of_absent_wiring_and_nearby_device_not_connected():
    image,payload=example();image[:]=255
    blank=recover_wiring(payload,image)
    assert not blank.observed_routes.segments
    assert {d.state for d in blank.observed_routes.recovery.devices}=={'no_usable_observed_path'}
    cv2.line(image,(68,100),(230,100),(0,0,0),2)
    result=recover_wiring(payload,image)
    assert not result.observed_routes.connections
    assert result.observed_routes.recovery.stop_reason=='methods_exhausted'


def test_cancellation_retains_window_checkpoint_and_resume_does_not_duplicate_paths():
    image,payload=curved();states=[];calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if calls==4: raise InterruptedError('cancel')
    with pytest.raises(InterruptedError): recover_wiring(payload,image,check=cancel,checkpoint=lambda s:states.append(deepcopy(s)))
    resumed=recover_wiring(payload,image,resume=states[-1])
    completed=recover_wiring(payload,image)
    assert resumed.observed_routes.segments==completed.observed_routes.segments
    assert resumed.observed_routes.connections==completed.observed_routes.connections
    again=recover_wiring(completed,image)
    assert again.observed_routes.segments==completed.observed_routes.segments


def test_resource_limit_is_visible_and_does_not_turn_into_generated_wiring():
    image,payload=example();image[:]=255
    result=recover_wiring(payload,image,limits=RecoveryLimits(maximum_windows=1))
    assert result.observed_routes.recovery.stop_reason=='resource_limit'
    assert all(d.reason=='resource_limit' for d in result.observed_routes.recovery.devices)
    assert not result.observed_routes.segments


def test_failed_alternative_keeps_existing_source_and_reports_failure(monkeypatch):
    from app.ai.floor_plan_interpretation import wiring_recovery
    image,payload=curved()
    def exhausted(*args):raise MemoryError()
    monkeypatch.setattr(wiring_recovery,'local_paths',exhausted)
    result=recover_wiring(payload,image)
    assert not result.observed_routes.segments
    assert sum(p.failed_windows for p in result.observed_routes.recovery.passes)==4


def test_automatic_attachment_rejects_unmarked_crossing_but_keeps_supported_t_and_parallel_gap():
    from app.ai.floor_plan_interpretation.wiring_recovery import _source_attachment
    from app.ai.floor_plan_interpretation.candidate import PixelPoint,ObservedRouteSegment
    image=np.full((200,200,3),255,np.uint8)
    cv2.line(image,(20,100),(180,100),(0,0,0),3)
    cv2.line(image,(100,20),(100,180),(0,0,0),3)
    route=ObservedRouteSegment(id='segment-0001',points=(PixelPoint(x=20,y=100),PixelPoint(x=180,y=100)),
        evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    branch=(PixelPoint(x=100,y=20),PixelPoint(x=100,y=100))
    assert _source_attachment(branch,[route],image) is None
    image[103:]=255
    assert _source_attachment(branch,[route],image) is not None
    separated=(PixelPoint(x=20,y=95),PixelPoint(x=180,y=95))
    assert _source_attachment(separated,[route],image) is None


def test_native_band_duplicates_are_rejected_without_merging_separate_parallel_wires():
    from app.ai.floor_plan_interpretation.wiring_recovery import _duplicate
    from app.ai.floor_plan_interpretation.candidate import PixelPoint,ObservedRouteSegment
    image=np.full((100,160,3),255,np.uint8)
    cv2.line(image,(20,50),(140,50),(0,0,0),1)
    old=ObservedRouteSegment(id='segment-0001',points=(PixelPoint(x=20,y=52),PixelPoint(x=140,y=52)),
        evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    points=(PixelPoint(x=20,y=50),PixelPoint(x=140,y=50))
    assert _duplicate(points,[old],image)  # Unsupported nearby axis is NOT a second conductor.
    cv2.line(image,(20,52),(140,52),(0,0,0),1)
    assert not _duplicate(points,[old],image)  # Distinct dark strokes with a visible white separation.
