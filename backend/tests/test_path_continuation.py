from copy import deepcopy
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring,RecoveryLimits
from tests.test_automatic_wiring import example


def network():
    _,p=example();v=p.model_dump();v['document_state']='partial';image=np.full((300,400,3),255,np.uint8)
    v['source_plane'].update(width_pixels=400,height_pixels=300)
    v['regions'][0]['bounds'].update(x=0,y=0,width=400,height=300)
    prototype=deepcopy(v['symbols']['items'][0]);v['symbols']['items']=[]
    for i,(x,y) in enumerate(((100,80),(100,220),(300,80),(300,220)),1):
        s=deepcopy(prototype);s.update(id=f'symbol-{i:04d}',observed_label='Fluorescent fixture',
            center=dict(x=x,y=y),bounds=dict(x=x-6,y=y-10,width=12,height=20))
        v['symbols']['items'].append(s)
    segments=[]
    for i,x in enumerate((100,300),1):
        cv2.line(image,(x,80),(x,220),(0,0,0),2)
        segments.append(dict(id=f'segment-{i:04d}',line_style='solid',points=[dict(x=x,y=80),dict(x=x,y=220)],
            evidence_refs=['region:region-0001'],ambiguity='ambiguous'))
    cv2.line(image,(100,75),(300,75),(0,0,0),2)
    cv2.line(image,(100,225),(300,225),(0,0,0),2)
    v['observed_routes']=dict(state='partial',segments=segments,connections=[])
    p=with_device_contact_evidence(FloorPlanInterpretationPayload.model_validate(v),image)
    return image,p


def test_connected_devices_still_recover_missing_spans_on_both_sides():
    image,p=network();assert len(p.observed_routes.connections)==4
    result=recover_wiring(p,image)
    assert len(result.observed_routes.segments)>2
    added=[r for r in result.observed_routes.segments if r.id not in {s.id for s in p.observed_routes.segments}]
    assert any(abs(r.points[0].y-75)<3 and abs(r.points[-1].y-75)<3 for r in added)
    assert any(abs(r.points[0].y-225)<3 and abs(r.points[-1].y-225)<3 for r in added)
    assert all(len(r.points)<10 for r in result.observed_routes.segments)  # No flattened out-and-back network.
    assert result.observed_routes.recovery.stop_reason=='converged'


def test_time_slices_resume_the_same_work_cursor_and_geometry(monkeypatch):
    from app.ai.floor_plan_interpretation import wiring_recovery as w
    image,p=network();full=recover_wiring(p,image)
    tick=[0.]
    def clock():tick[0]+=.18;return tick[0]
    monkeypatch.setattr(w,'monotonic',clock)
    states=[];resume=None
    for _ in range(20):
        value=recover_wiring(p,image,limits=RecoveryLimits(maximum_seconds=1),resume=resume,
                             checkpoint=lambda s:states.append(deepcopy(s)))
        resume=states[-1]
        if value.observed_routes.recovery.limit_reason!='time_budget':break
    assert value.observed_routes.recovery.stop_reason=='converged'
    assert value.observed_routes.segments==full.observed_routes.segments
    assert value.observed_routes.connections==full.observed_routes.connections
    assert value.observed_routes.junctions==full.observed_routes.junctions


def test_continuous_grid_through_offset_fixture_bounds_is_not_a_port():
    from app.ai.floor_plan_interpretation.device_contact_evidence import fixture_boundary_ports
    image,p=network();image[:]=255
    cv2.line(image,(0,75),(399,75),(0,0,0),2)
    row=p.observed_routes.segments[0].model_copy(update={'points':(
        type(p.symbols.items[0].center)(x=100,y=75),type(p.symbols.items[0].center)(x=300,y=75))})
    trial=p.model_copy(update={'observed_routes':p.observed_routes.model_copy(update={'segments':(row,),'connections':()})})
    ink=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)<180
    assert fixture_boundary_ports(trial,ink.astype(np.uint8)*255)==set()


def test_integer_endpoint_projection_can_attach_without_numpy_cast_failure():
    from types import SimpleNamespace as NS
    from app.ai.floor_plan_interpretation.wiring_recovery import _source_attachment
    image=np.full((200,200,3),255,np.uint8)
    cv2.line(image,(20,100),(180,100),(0,0,0),3)
    cv2.line(image,(20,20),(20,100),(0,0,0),3)
    # Exact projection onto a clamped endpoint retains integer coordinates.
    route=NS(id='segment-0001',points=(NS(x=20,y=100),NS(x=180,y=100)))
    points=(NS(x=20,y=20),NS(x=20,y=100))
    result=_source_attachment(points,[route],image,endpoint_indices=(1,))
    assert result is not None and result[0]=='segment-0001'


def test_worker_time_slices_complete_the_same_deterministic_work(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    from app.ai.floor_plan_interpretation import wiring_recovery as w
    from app.services.wiring_recovery_service import recover_worker_wiring
    image,p=network();full=recover_wiring(p,image)
    tick=[0.]
    def clock():tick[0]+=.18;return tick[0]
    monkeypatch.setattr(w,'monotonic',clock)
    sliced,_=recover_worker_wiring(p,image,root=tmp_path,job_id=1,page_id=1,
        source_sha256='a'*64,settings=NS(wiring_recovery_maximum_seconds=1),heartbeat=lambda:None)
    assert sliced.observed_routes.recovery.stop_reason=='converged'
    assert sliced.observed_routes.segments==full.observed_routes.segments
    assert sliced.observed_routes.connections==full.observed_routes.connections
    assert sliced.observed_routes.junctions==full.observed_routes.junctions
