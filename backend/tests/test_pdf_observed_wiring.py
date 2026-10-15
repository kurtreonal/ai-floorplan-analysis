import cv2
import numpy as np
import pytest

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.pdf_evidence import PrimitiveIndex
from app.ai.floor_plan_interpretation.pdf_observed_wiring import with_pdf_observed_wiring,native_periodic_traces
import app.ai.floor_plan_interpretation.pdf_observed_wiring as module
from tests.test_automatic_wiring import example


def scene(*,marker=True,uniform=False,missing=False,scale=1):
    image,payload=example()
    image[:]=255
    objects=[]
    def obj(points,*,fill=False,closed=False):
        bounds=[min(p[0] for p in points),min(p[1] for p in points),
                max(p[0] for p in points),max(p[1] for p in points)]
        objects.append(dict(id=len(objects)+1,type=2,bounds=bounds,commands=[
            [2 if i==0 else 0,*p,closed and i==len(points)-1] for i,p in enumerate(points)],
            stroke=True,fill_mode=2 if fill else 0,stroke_width=1,
            stroke_color=[0,0,0,255],fill_color=[0,0,0,255],
            transform=[1,0,0,1,0,0],clip_paths=[],level=0,dash_array=[]))
        if fill:cv2.fillPoly(image,[np.array(points,dtype=np.int32)],(0,0,0))
        else:cv2.polylines(image,[np.array(points,dtype=np.int32)],closed,(0,0,0),1)
    if marker:
        obj([(51,92),(67,92),(67,108),(51,108),(51,92)],closed=True)
        obj([(51,92),(51,108),(67,108),(51,92)],fill=True,closed=True)
    cursor=70
    for i,length in enumerate([24,4,24,4,24,4,24]):
        length=12 if uniform else length
        obj([(cursor,100),(cursor+length,100)])
        cursor+=length+(16 if missing and i==3 else 4)
    # Unrelated crossing stroke cannot create a graph edge.
    obj([(140,50),(140,150)])
    if scale!=1:
        image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
        value=payload.model_dump()
        value['source_plane']=dict(width_pixels=image.shape[1],height_pixels=image.shape[0])
        for region in value['regions']:
            if region['bounds']:
                region['bounds']={k:v*scale for k,v in region['bounds'].items()}
        payload=FloorPlanInterpretationPayload.model_validate(value)
        for row in objects:
            row['bounds']=[p*scale for p in row['bounds']]
            row['commands']=[[p[0],p[1]*scale,p[2]*scale,p[3]] for p in row['commands']]
            row['transform']=[scale,0,0,scale,0,0]
    return image,payload,objects


def test_native_dash_dot_preserves_ink_and_proposes_source_supported_endpoint_contact():
    image,payload,objects=scene();before=payload.model_dump_json();pixels=image.copy()
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    assert len(result.observed_routes.segments)==1
    route=result.observed_routes.segments[0]
    assert route.line_style=='dashed' and route.route_kind=='observed'
    assert route.points[0].x==70 and route.points[-1].x==202
    assert len(result.observed_routes.connections)==1
    connection=result.observed_routes.connections[0]
    assert connection.from_ref==f'segment:{route.id}'
    assert connection.to_ref=='symbol:symbol-0001'
    assert connection.evidence_kind=='symbol_occlusion'
    assert connection.path_anchor==route.points[0]
    assert route.ambiguity=='ambiguous'
    assert any(w.code=='pdf_periodic_observed_trace' and 'primitive_ids' in w.message for w in result.warnings)
    assert payload.model_dump_json()==before
    np.testing.assert_array_equal(image,pixels)
    assert FloorPlanInterpretationPayload.model_validate_json(result.model_dump_json())==result
    assert with_pdf_observed_wiring(result,image,PrimitiveIndex(dict(objects=objects)))==result


def test_uniform_architecture_dashes_missing_context_and_irregular_gaps_not_wiring():
    for options in [dict(marker=False),dict(uniform=True),dict(missing=True)]:
        image,payload,objects=scene(**options)
        assert not with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects))).observed_routes.segments


def test_source_coordinates_scale_and_nonblack_strokes_are_checked():
    for scale in (1,2,3):
        image,payload,objects=scene(scale=scale)
        result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
        assert result.observed_routes.segments[0].points[0].x==70*scale
    image,payload,objects=scene()
    for row in objects:row['stroke_color']=[255,255,255,255];row['fill_color']=[255,255,255,255]
    assert native_periodic_traces(objects,coordinate_tolerance=.5)==[]


def test_clipped_form_primitives_or_raster_absence_cannot_supply_trace_evidence():
    for key,value in [('clip_paths',[[[2,0,0,False]]]),('level',1)]:
        image,payload,objects=scene()
        for row in objects:row[key]=value
        assert with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))==payload
    image,payload,objects=scene();image[:]=255
    assert with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))==payload


def test_rotated_periodic_paths_preserve_exact_source_positions():
    image,payload,objects=scene()
    matrix=cv2.getRotationMatrix2D((160,100),25,1)
    image=cv2.warpAffine(image,matrix,(320,200),borderValue=(255,255,255))
    for row in objects:
        row['commands']=[[c[0],*(matrix@np.array([c[1],c[2],1])),c[3]] for c in row['commands']]
        points=np.array([c[1:3] for c in row['commands']])
        row['bounds']=[*points.min(axis=0),*points.max(axis=0)]
        row['transform']=[matrix[0,0],matrix[1,0],matrix[0,1],matrix[1,1],0,0]
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    assert len(result.observed_routes.segments)==1
    expected=matrix@np.array([70,100,1])
    actual=result.observed_routes.segments[0].points[0]
    np.testing.assert_allclose([actual.x,actual.y],expected,atol=1e-7)


def test_matching_source_frame_is_required():
    image,payload,objects=scene()
    with pytest.raises(ValueError,match='matching source RGB'):
        with_pdf_observed_wiring(payload,image[:-1],PrimitiveIndex(dict(objects=objects)))


def curve_scene(*, marker=True, pen_width=1, closed=False, periodic=True):
    image,payload,objects=scene(marker=marker,uniform=not periodic)
    points=np.array([[59,92],[59,50],[104,50],[130,65]],float)
    t=np.linspace(0,1,250)[:,None]
    ink=(1-t)**3*points[0]+3*(1-t)**2*t*points[1]+3*(1-t)*t**2*points[2]+t**3*points[3]
    cv2.polylines(image,[np.rint(ink).astype(np.int32)],False,(0,0,0),1)
    objects.append(dict(id=100,type=2,bounds=[59,50,130,92],
        commands=[[2,*points[0],False],*[ [1,*p,closed and i==2] for i,p in enumerate(points[1:])]],
        stroke=True,fill_mode=0,stroke_width=pen_width,stroke_color=[0,0,0,255],
        transform=[1,0,0,1,0,0],clip_paths=[],level=0,dash_array=[]))
    return image,payload,objects,ink


def test_observed_curve_preserves_source_bend_and_uses_its_evidenced_terminal():
    image,payload,objects,ink=curve_scene()
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    curves=[s for s in result.observed_routes.segments if s.line_style=='solid']
    assert len(curves)==1 and 3<len(curves[0].points)<=128
    points=np.array([[p.x,p.y] for p in curves[0].points])
    np.testing.assert_allclose(points[[0,-1]],[[59,92],[130,65]])
    # Dense independent cubic samples stay within the stated source-pixel bound.
    distances=[]
    for point in ink:
        delta=points[1:]-points[:-1]
        fraction=np.clip(((point-points[:-1])*delta).sum(axis=1)/(delta*delta).sum(axis=1),0,1)
        nearest=points[:-1]+fraction[:,None]*delta
        distances.append(np.linalg.norm(nearest-point,axis=1).min())
    assert max(distances)<=.5
    contacts=[c for c in result.observed_routes.connections if c.from_ref==f'segment:{curves[0].id}']
    assert len(contacts)==1 and contacts[0].to_ref=='symbol:symbol-0001'
    assert contacts[0].path_anchor.model_dump()==dict(x=59.,y=92.)
    assert contacts[0].evidence_kind=='symbol_occlusion'
    assert any(w.code=='pdf_native_open_curve_trace' and '100' in w.message for w in result.warnings)
    assert with_pdf_observed_wiring(result,image,PrimitiveIndex(dict(objects=objects)))==result
    assert FloorPlanInterpretationPayload.model_validate_json(result.model_dump_json())==result


def test_native_endpoint_duplicate_ports_remain_ambiguous_not_nearest_wins():
    image,payload,objects=scene()
    value=payload.model_dump()
    extra=dict(value['symbols']['items'][0]);extra['id']='symbol-0003'
    value['symbols']['items']=list(value['symbols']['items'])+[extra]
    payload=FloorPlanInterpretationPayload.model_validate(value)
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    assert len(result.observed_routes.connections)==2
    assert {c.to_ref for c in result.observed_routes.connections}=={'symbol:symbol-0001','symbol:symbol-0003'}
    assert all(c.ambiguity=='ambiguous' for c in result.observed_routes.connections)
    assert any(w.code=='ambiguous_device_contacts' for w in result.warnings)
    assert with_pdf_observed_wiring(result,image,PrimitiveIndex(dict(objects=objects)))==result


def test_native_inline_port_has_two_source_approaches_without_crossing_junction():
    image,payload,objects=scene()
    value=payload.model_dump()
    extra=dict(value['symbols']['items'][0])
    extra.update(id='symbol-0003',center={'x':120,'y':100},
                 bounds={'x':115,'y':94,'width':10,'height':12})
    value['symbols']['items']=list(value['symbols']['items'])+[extra]
    cv2.rectangle(image,(115,94),(125,106),(0,0,0),1)
    payload=FloorPlanInterpretationPayload.model_validate(value)
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    inline=[c for c in result.observed_routes.connections if c.to_ref=='symbol:symbol-0003']
    assert len(inline)==1 and inline[0].evidence_kind=='inline_device'
    assert all(c.to_ref.startswith('symbol:') for c in result.observed_routes.connections)


def test_native_noop_does_not_recompute_or_replace_existing_contacts(monkeypatch):
    image,payload,objects=scene()
    index=PrimitiveIndex(dict(objects=objects))
    result=with_pdf_observed_wiring(payload,image,index)
    def forbidden(*args,**kwargs):
        raise AssertionError('No newly observed routes: preserve the existing proposal.')
    monkeypatch.setattr(module,'with_device_contact_evidence',forbidden)
    assert with_pdf_observed_wiring(result,image,index)==result


@pytest.mark.parametrize('options',[dict(marker=False),dict(pen_width=.1),dict(closed=True),dict(periodic=False)])
def test_open_architectural_arcs_without_matching_source_terminal_context_are_not_wires(options):
    image,payload,objects,_=curve_scene(**options)
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    assert not any(s.line_style=='solid' for s in result.observed_routes.segments)


@pytest.mark.parametrize('limit,value',[('MAXIMUM_OBJECTS_PER_VIEW',1),('MAXIMUM_LINES_PER_VIEW',1),
                                      ('MAXIMUM_CONTEXT_POLYGONS',0),('MAXIMUM_TRACES',0)])
def test_budget_exhaustion_is_explicit_partial_not_silent_complete(monkeypatch,limit,value):
    image,payload,objects=scene()
    monkeypatch.setattr(module,limit,value)
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    assert result.document_state=='partial'
    assert result.observed_routes.state=='partial' and result.observed_routes.truncated
    assert any(w.code=='pdf_native_wiring_budget' for w in result.warnings)


def test_native_route_evidence_references_survive_source_view_fusion():
    from app.ai.floor_plan_interpretation.scoped_analysis import merge_view_payloads
    image,payload,objects,_=curve_scene()
    result=with_pdf_observed_wiring(payload,image,PrimitiveIndex(dict(objects=objects)))
    merged=merge_view_payloads([result,result])
    refs=[w.entity_refs for w in merged.warnings if w.code in ('pdf_periodic_observed_trace','pdf_native_open_curve_trace')]
    assert refs==[(f'segment:{s.id}',) for s in merged.observed_routes.segments]
    assert all('segment_id' not in w.message for w in merged.warnings if w.entity_refs)
