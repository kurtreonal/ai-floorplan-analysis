import cv2
import numpy as np
import pytest
from types import SimpleNamespace
from copy import deepcopy

from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment, PixelPoint
from app.ai.floor_plan_interpretation.stroke_axis import refine_axis_trace, chain_exact_traces
from app.ai.floor_plan_interpretation.automatic_wiring import with_automatic_wiring
from tests.test_fixture_wiring import fixtures
from app.routing.endpoint_connections import apply_source_contacts
from app.schemas.demo_interpretation import DemoObservedWiringReview
from app.geometry.observed_connections import observed_connection_routes


def segment(identity, points, style='solid'):
    return ObservedRouteSegment(id=identity, points=[PixelPoint(x=x,y=y) for x,y in points],
        line_style=style, evidence_refs=('region:region-0001',), ambiguity='ambiguous')


def test_refine_own_band_does_not_jump_to_wider_nearby_ink():
    ink=np.zeros((100,200),np.uint8)
    cv2.line(ink,(20,50),(180,50),255,1)
    cv2.line(ink,(20,56),(180,56),255,5)
    a,b=refine_axis_trace((20,51),(180,51),ink,np.zeros_like(ink))
    assert a==(20,50) and b==(180,50)


def test_blank_and_ambiguous_bands_do_not_move_or_bridge():
    ink=np.zeros((100,200),np.uint8)
    a,b=(20,50),(180,50)
    assert refine_axis_trace(a,b,ink,np.zeros_like(ink))==(a,b)
    ink[49,20:181]=ink[51,20:181]=255
    assert refine_axis_trace(a,b,ink,np.zeros_like(ink))==(a,b)


def test_exact_l_chain_preserves_all_edges_provenance_and_repeats_deterministically():
    a=segment('segment-0001',[(10,10),(80,10)])
    b=segment('segment-0002',[(80,80),(80,10)])
    result=chain_exact_traces([a,b])
    assert len(result)==1 and len(result[0].points)==3
    assert result==chain_exact_traces([b,a])
    assert result[0].evidence_refs==a.evidence_refs and result[0].ambiguity=='ambiguous'


@pytest.mark.parametrize('other', [
    [(80,10),(80,80)], [(80,0),(80,80)]])
def test_t_or_x_crossing_prevents_flattening(other):
    rows=[segment('segment-0001',[(10,10),(80,10)]),
          segment('segment-0002',[(80,10),(140,10)]),segment('segment-0003',other)]
    assert len(chain_exact_traces(rows))==3


def test_gaps_styles_and_parallel_paths_are_not_joined():
    rows=[segment('segment-0001',[(10,10),(80,10)]),
          segment('segment-0002',[(81,10),(140,10)]),
          segment('segment-0003',[(10,12),(140,12)]),
          segment('segment-0004',[(80,10),(80,80)],'dashed')]
    assert len(chain_exact_traces(rows))==4


def test_three_supported_devices_form_one_logical_path_with_inline_contact():
    image,payload=fixtures()
    value=payload.model_dump(mode='json')
    value['regions'][0]['bounds'].update(width=640,height=400)
    for item,(x,y) in zip(value['symbols']['items'],[(60,50),(62,150),(61,250),(250,250)]):
        item.update(center=dict(x=x,y=y),bounds=dict(x=x-6,y=y-10,width=12,height=20))
    payload=type(payload).model_validate(value)
    cv2.line(image,(60,50),(60,250),(0,0,0),1)
    result=with_automatic_wiring(payload,image)
    assert len(result.observed_routes.segments)==1
    path=result.observed_routes.segments[0]
    assert len(path.points)==3
    assert {c.to_ref for c in result.observed_routes.connections}=={
        'symbol:symbol-0001','symbol:symbol-0002','symbol:symbol-0003'}
    middle=next(c for c in result.observed_routes.connections if c.to_ref=='symbol:symbol-0002')
    assert middle.evidence_kind=='inline_device' and middle.ambiguity=='unambiguous'
    assert result==with_automatic_wiring(payload,image)
    original=deepcopy(result.model_dump(mode='json'))
    candidate=SimpleNamespace(payload=result,provenance=SimpleNamespace(candidate_run_id='a'*32,
        inference_parameters=[SimpleNamespace(name='wiring-evidence-version',value='raw-source-device-port-evidence-v10')]))
    document=dict(symbols=[dict(id=s.id,center=s.center.model_dump(),disposition='unresolved',
                               mounting_height_meters=1.2) for s in result.symbols.items],
        observed_wiring=[dict(id=path.id,points=[p.model_dump() for p in path.points],
                             disposition='unresolved',completeness='partial',elevation_meters=3)])
    adapted=apply_source_contacts(candidate,document)
    wire=DemoObservedWiringReview.model_validate(adapted['observed_wiring'][0])
    assert DemoObservedWiringReview.model_validate_json(wire.model_dump_json())==wire
    assert len(wire.device_attachments)==3
    center_index=next(a.point_index for a in wire.device_attachments if a.symbol_id=='symbol-0002')
    # Only the small interval inside the glyph moves off the source axis.
    assert abs(wire.points[center_index-1].y-150)<8
    assert abs(wire.points[center_index+1].y-150)<8
    approved=wire.model_dump(mode='json')
    approved.update(disposition='accepted',completeness='complete')
    symbols={s['id']:s for s in document['symbols']}
    routes,details,version4=observed_connection_routes([approved],symbols,
        {identity:f'detected:{i}' for i,identity in enumerate(symbols,1)},
        floor_id=2,floor_elevation=0,scale=10,provenance='reviewed:synthetic')
    assert version4 and len(routes)==4  # One shared path, three measured drops.
    assert len(details[0]['device_connections'])==3
    assert all(route['points'][-1]['elevation_meters']==1.2 for route in routes[1:])
    assert result.model_dump(mode='json')==original
    assert document['observed_wiring'][0]['points']==[p.model_dump() for p in path.points]
