from copy import deepcopy
import cv2
import numpy as np
import pytest
from app.ai.floor_plan_interpretation.automatic_wiring import (
    with_automatic_wiring, with_validated_solid_context, _parallel_dash_boundaries,
    _source_dash_contrast,
)
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from tests.test_automatic_wiring import example


def test_unvalidated_second_port_does_not_make_furniture_an_observed_wire():
    image,payload=example()
    # The second loose box touches the line, but its central port is elsewhere.
    value=payload.model_dump();value['symbols']['items'][1]['center']['y']=106
    payload=FloorPlanInterpretationPayload.model_validate(value)
    result=with_automatic_wiring(payload,image)
    assert not result.observed_routes.segments and not result.observed_routes.connections
    assert any(w.code=='unsupported_solid_trace_context' for w in result.warnings)
    assert result.symbols==payload.symbols


def test_minority_fixture_hypotheses_do_not_discard_other_wire_styles(monkeypatch):
    image,payload=example();value=payload.model_dump(mode='json')
    for i in range(4):
        extra=deepcopy(value['symbols']['items'][0]);extra.update(id=f'symbol-{i+3:04d}',
            observed_label='Troffer lights',center={'x':25+i*60,'y':160},
            bounds={'x':20+i*60,'y':150,'width':10,'height':20})
        value['symbols']['items'].append(extra)
    payload=FloorPlanInterpretationPayload.model_validate(value)
    def prohibited(*args,**kwargs):raise AssertionError('Mixed drawing must retain general wire extraction.')
    monkeypatch.setattr('app.ai.floor_plan_interpretation.automatic_wiring.fixture_axis_traces',prohibited)
    result=with_automatic_wiring(payload,image)
    assert len(result.observed_routes.connections)==2


def test_dash_source_conflict_bypasses_mask_not_symbol_review_or_crossing_rules():
    image,payload=example();image[:]=255;value=payload.model_dump(mode='json')
    # Long false lamp box encloses four actual dashes between outlet proposals.
    value['symbols']['items'][0].update(center={'x':60,'y':100},bounds={'x':52,'y':92,'width':16,'height':16})
    value['symbols']['items'][1].update(center={'x':260,'y':100},bounds={'x':252,'y':92,'width':16,'height':16})
    extra=deepcopy(value['symbols']['items'][0]);extra.update(id='symbol-0003',
        observed_label='2 x 40 watts fluorescent lamp',center={'x':160,'y':100},
        bounds={'x':86,'y':92,'width':148,'height':16})
    value['symbols']['items'].append(extra)
    payload=FloorPlanInterpretationPayload.model_validate(value)
    for x in (68,100,132,164,196,228):
        cv2.line(image,(x,100),(252 if x==228 else x+22,100),(0,0,0),2)
    cv2.line(image,(144,30),(144,175),(0,0,0),1)  # A dimension crossing, NOT a junction.
    result=with_automatic_wiring(payload,image)
    assert result.symbols==payload.symbols
    assert any(w.code=='symbol_mask_dash_conflict' for w in result.warnings)
    assert {c.to_ref for c in result.observed_routes.connections}=={'symbol:symbol-0001','symbol:symbol-0002'}
    assert not result.observed_routes.junctions
    assert all(r.line_style=='dashed' for r in result.observed_routes.segments)


def test_ambiguous_identity_at_one_of_two_ports_keeps_source_wire():
    image,payload=example();value=payload.model_dump(mode='json')
    duplicate=deepcopy(value['symbols']['items'][0]);duplicate['id']='symbol-0003'
    value['symbols']['items'].append(duplicate)
    result=with_automatic_wiring(FloorPlanInterpretationPayload.model_validate(value),image)
    assert result.observed_routes.segments
    assert any(c.ambiguity=='ambiguous' for c in result.observed_routes.connections)
    # Two identities at ONE spatial port cannot substitute for a second port.
    route=result.observed_routes.segments[0]
    contacts=tuple(c for c in result.observed_routes.connections if c.to_ref!='symbol:symbol-0002')
    one_port=result.model_copy(update={'observed_routes':result.observed_routes.model_copy(update={
        'segments':(route,), 'connections':contacts})})
    assert not with_validated_solid_context(one_port,image).observed_routes.segments


@pytest.mark.parametrize('scale',[1,2,3])
@pytest.mark.parametrize('turn',[0,1])
def test_shared_column_gaps_reject_separate_structural_bands_only(scale,turn):
    ink=np.zeros((200*scale,320*scale),np.uint8)
    for y in (80,85):
        for x in (20,75,130,185):
            cv2.line(ink,(x*scale,y*scale),((x+40)*scale,y*scale),255,scale)
    a,b=(20*scale,80*scale),(225*scale,80*scale)
    if turn:
        ink=np.rot90(ink);a,b=(a[1],320*scale-1-a[0]),(b[1],320*scale-1-b[0])
    points=np.rint(np.linspace(a,b,int(np.linalg.norm(np.subtract(b,a)))+1)).astype(int)
    samples=ink[points[:,1],points[:,0]]>0
    assert _parallel_dash_boundaries(a,b,samples,ink)
    # A nearby continuous wall has different gaps and must not veto a wire.
    if turn:
        ink=np.ascontiguousarray(ink)
        cv2.line(ink,(85*scale,320*scale-1-19*scale),(85*scale,320*scale-1-226*scale),255,scale)
    else:
        cv2.line(ink,(19*scale,85*scale),(226*scale,85*scale),255,scale)
    assert not _parallel_dash_boundaries(a,b,samples,ink)


def test_raw_gray_contrast_distinguishes_faint_dashes_from_threshold_holes():
    samples=np.tile(np.r_[np.ones(12,bool),np.zeros(6,bool)],4)
    gray=np.full((20,len(samples)),255,np.uint8)
    gray[9:12,samples]=193
    assert _source_dash_contrast((0,10),(len(samples)-1,10),samples,gray)
    gray[9:12,:]=193
    assert not _source_dash_contrast((0,10),(len(samples)-1,10),samples,gray)


def test_window_hatching_between_matching_boundaries_is_structural_not_thick_wire():
    ink=np.zeros((100,320),np.uint8)
    for x in (20,75,130,185):
        ink[40:42,x:x+41]=255;ink[49:51,x:x+41]=255
        for tick in range(x,x+41,5):ink[42:49,tick:tick+3]=255
    a,b=(20,50),(225,50);samples=ink[50,20:226]>0
    assert _parallel_dash_boundaries(a,b,samples,ink)
    for x in (20,75,130,185):ink[42:49,x:x+41]=255
    assert not _parallel_dash_boundaries(a,b,samples,ink)
