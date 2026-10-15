import cv2
import numpy as np
import pytest

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.fixture_wiring import fixture_axis_traces
from app.ai.floor_plan_interpretation.automatic_wiring import _regular_dash_evidence
from tests.test_automatic_wiring import example


def fixtures(*,scale=1):
    _,payload=example();image=np.full((400,640,3),255,np.uint8)
    value=payload.model_dump(mode='json')
    value['source_plane'].update(width_pixels=640,height_pixels=400)
    symbols=[]
    for identity,(x,y) in enumerate([(60,50),(63,150),(250,50),(253,150)],1):
        item=dict(value['symbols']['items'][0])
        item.update(id=f'symbol-{identity:04d}',observed_label='Fluorescent fixture',
                    center={'x':x,'y':y},bounds={'x':x-6,'y':y-10,'width':12,'height':20})
        symbols.append(item)
    value['symbols']['items']=symbols
    if scale!=1:
        image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
        value['source_plane'].update(width_pixels=image.shape[1],height_pixels=image.shape[0])
        for region in value['regions']:
            if region.get('bounds'):region['bounds']={k:v*scale for k,v in region['bounds'].items()}
        for item in value['symbols']['items']:
            item['center']={k:v*scale for k,v in item['center'].items()}
            item['bounds']={k:v*scale for k,v in item['bounds'].items()}
    return image,FloorPlanInterpretationPayload.model_validate(value)


@pytest.mark.parametrize('scale',[1,2,3])
def test_center_bias_does_not_hide_solid_ink_inside_shared_device_bounds(scale):
    image,payload=fixtures(scale=scale)
    cv2.line(image,(58*scale,50*scale),(58*scale,150*scale),(0,0,0),scale)
    rows,truncated=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert not truncated
    assert any(not dashed and abs(a[0]-58*scale)<=2*scale and a[0]==b[0]
               for a,b,_,dashed in rows)


def test_bounded_solid_search_never_bridges_an_intentional_source_gap():
    image,payload=fixtures()
    cv2.line(image,(58,50),(58,150),(0,0,0),1)
    image[88:105,50:70]=255
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert not rows


def test_parallel_line_outside_shared_glyph_bounds_is_not_a_wire():
    image,payload=fixtures()
    cv2.line(image,(46,50),(46,150),(0,0,0),1)
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert not rows


def test_long_fixture_tip_grid_does_not_supply_the_central_wire_port():
    image,payload=fixtures()
    value=payload.model_dump(mode='json')
    for item in value['symbols']['items']:
        item['bounds'].update(x=item['center']['x']-40,width=80)
    payload=FloorPlanInterpretationPayload.model_validate(value)
    cv2.line(image,(25,50),(25,150),(0,0,0),1)
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert not rows


@pytest.mark.parametrize('scale', [1, 2, 3])
def test_expanded_offset_requires_terminal_context_not_continuous_grid(scale):
    image,payload=fixtures(scale=scale)
    cv2.line(image,(57*scale,0),(57*scale,image.shape[0]-1),(0,0,0),scale)
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert not rows


def test_expanded_offset_accepts_a_source_turn_at_fixture_end():
    image,payload=fixtures()
    cv2.line(image,(58,50),(58,150),(0,0,0),1)
    cv2.line(image,(58,150),(100,150),(0,0,0),1)
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert any(not dashed and abs(a[0]-58)<=2 for a,b,_,dashed in rows)


def test_continuous_source_in_established_tight_band_keeps_existing_behavior():
    image,payload=fixtures()
    cv2.line(image,(62,0),(62,image.shape[0]-1),(0,0,0),1)
    rows,_=fixture_axis_traces(payload,image,np.full(image.shape[:2],255,np.uint8),dash_validator=_regular_dash_evidence)
    assert any(not dashed and abs(a[0]-62)<=2 for a,b,_,dashed in rows)
