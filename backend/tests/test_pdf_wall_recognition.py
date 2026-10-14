from copy import deepcopy
import math

import cv2
import numpy as np
import pytest

from app.ai.floor_plan_interpretation.candidate import (
    AffineTransform, CandidateCollection, CandidateWarning, EvidenceRegion, PixelBounds, PixelPoint, SourcePlane, WallCandidate,
)
from app.ai.floor_plan_interpretation.pdf_evidence import PrimitiveIndex
from app.ai.floor_plan_interpretation.pdf_wall_recognition import CONFIGURATION,with_pdf_wall_recognition
from tests.test_automatic_wiring import example


def scene(bands, angle=0, extra=()):
    image=np.full((800,1000,3),255,np.uint8)
    _,payload=example()
    payload=payload.model_copy(update={
        'source_plane':SourcePlane(width_pixels=1000,height_pixels=800),
        'walls':CandidateCollection(state='empty'),
        'regions':(EvidenceRegion(id='region-0001',kind='plan_region',bounds=PixelBounds(x=40,y=40,width=920,height=720),
            local_to_source=AffineTransform(a=1,b=0,c=0,d=1,e=0,f=0)),)})
    rows=[];theta=math.radians(angle);matrix=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
    def rotate(p):return (np.array(p)-[500,400])@matrix.T+[500,400]
    def stroke(a,b):
        a,b=rotate(a),rotate(b)
        rows.append(dict(id=len(rows)+1,type=2,bounds=[min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])],
            commands=[[2,*a,False],[0,*b,False]],stroke=True,fill_mode=0,dash_array=[],clip_paths=[],level=0,
            stroke_color=[0,0,0,255],stroke_width=.5))
        cv2.line(image,tuple(np.rint(a).astype(int)),tuple(np.rint(b).astype(int)),(0,0,0),1)
    for start,end,width,texture in bands:
        a,b=np.array(start,float),np.array(end,float);axis=(b-a)/np.linalg.norm(b-a);normal=np.array([-axis[1],axis[0]])
        stroke(a-normal*width/2,b-normal*width/2);stroke(a+normal*width/2,b+normal*width/2)
        if texture:
            for distance in np.arange(width,np.linalg.norm(b-a)-width,width*.6):
                p=a+axis*distance
                stroke(p-normal*width/2-axis*width*.25,p+normal*width/2+axis*width*.25)
    for a,b in extra:stroke(a,b)
    return image,payload,PrimitiveIndex(dict(objects=rows))


L_BANDS=[((180,220),(500,220),8,True),((500,220),(500,600),8,True)]


@pytest.mark.parametrize('angle',[0,25,-30])
def test_recovers_hatched_l_banks_at_actual_source_coordinates_without_axis_snapping(angle):
    image,payload,index=scene(L_BANDS,angle)
    original=payload.model_dump_json();pixels=image.copy();diagnostics=[]
    result=with_pdf_wall_recognition(payload,image,index,diagnostics)
    assert len(result.walls.items)==2
    assert all(w.ambiguity=='ambiguous' for w in result.walls.items)
    assert all(abs(w.estimated_thickness_pixels-8)<1e-6 for w in result.walls.items)
    assert all(w.code=='pdf_native_hatched_wall_band' and 'bank_ids' in w.message for w in result.warnings if w not in payload.warnings)
    assert result.rooms.state=='unavailable'
    assert payload.model_dump_json()==original
    np.testing.assert_array_equal(image,pixels)
    assert result.model_dump_json()==with_pdf_wall_recognition(payload,image,index).model_dump_json()


def test_blank_outlines_or_unconnected_furniture_do_not_acquire_wall_semantics():
    for bands in [[((180,220),(500,220),8,True)],
                  [((180,220),(500,220),8,False),((500,220),(500,600),8,False)]]:
        image,payload,index=scene(bands);diagnostics=[]
        assert with_pdf_wall_recognition(payload,image,index,diagnostics)==payload
        assert any(r['reason'] in ('no_supported_structural_contact','insufficient_confined_transverse_strokes') for r in diagnostics)


def test_native_opening_gaps_remain_open_and_nearby_walls_remain_separate():
    bands=[((180,250),(340,250),8,True),((420,250),(650,250),8,True),
           ((180,250),(180,600),8,True),((650,250),(650,600),8,True)]
    image,payload,index=scene(bands)
    result=with_pdf_wall_recognition(payload,image,index)
    horizontal=[w for w in result.walls.items if abs(w.start.y-w.end.y)<1e-6]
    assert len(horizontal)==2
    assert sorted((w.start.x,w.end.x) for w in horizontal)==[(180.,340.),(420.,650.)]
    vertical=[w for w in result.walls.items if abs(w.start.x-w.end.x)<1e-6]
    assert sorted(w.start.x for w in vertical)==[180.,650.]


def test_long_inner_frame_rails_and_unconfined_background_hatching_are_rejected():
    image,payload,index=scene(L_BANDS,extra=[((180,220),(500,220)),((500,220),(500,600))])
    diagnostics=[]
    assert with_pdf_wall_recognition(payload,image,index,diagnostics)==payload
    assert any(r['reason']=='sustained_inner_frame_bank' for r in diagnostics)
    # Hatch strokes which extend past the boundary bank are not wall texture.
    image,payload,index=scene([((180,220),(500,220),8,False),((500,220),(500,600),8,False)],
        extra=[((x,100),(x+200,350)) for x in range(100,500,12)])
    assert with_pdf_wall_recognition(payload,image,index)==payload


def test_duplicate_source_boundaries_do_not_duplicate_walls_and_saved_identity_is_kept():
    image,payload,index=scene(L_BANDS)
    index=PrimitiveIndex(dict(objects=[*index.objects,*deepcopy(index.objects)]))
    wall=WallCandidate(id='wall-0007',start=PixelPoint(x=180,y=220),end=PixelPoint(x=500,y=220),
        estimated_thickness_pixels=8,evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    payload=payload.model_copy(update={'walls':CandidateCollection(state='partial',items=(wall,))})
    result=with_pdf_wall_recognition(payload,image,index)
    assert len(result.walls.items)==2
    assert any(w.id=='wall-0007' for w in result.walls.items)


def test_clipped_dashed_curved_and_nested_paths_do_not_become_straight_banks():
    for property,value in [('clip_paths',[[[2,0,0,False]]]),('dash_array',[3,2]),('level',1)]:
        image,payload,index=scene(L_BANDS)
        rows=deepcopy(index.objects)
        for row in rows:row[property]=value
        assert with_pdf_wall_recognition(payload,image,PrimitiveIndex(dict(objects=rows)))==payload
    image,payload,index=scene(L_BANDS)
    rows=deepcopy(index.objects)
    for row in rows:row['commands'][1][0]=1
    assert with_pdf_wall_recognition(payload,image,PrimitiveIndex(dict(objects=rows)))==payload


def test_invalid_source_alignment_is_rejected():
    image,payload,index=scene(L_BANDS)
    with pytest.raises(ValueError,match='matching source pixels'):
        with_pdf_wall_recognition(payload,image[:400],index)


@pytest.mark.parametrize('bands',[
    [((180,300),(720,300),8,True),((500,300),(500,600),8,True)],
    [((180,300),(720,300),8,True),((500,180),(500,600),8,True)],
    [((180,250),(650,250),8,True),((180,280),(650,280),8,True),((650,250),(650,600),8,True)],
])
def test_source_supported_t_x_and_close_parallel_bands_keep_individual_geometry(bands):
    image,payload,index=scene(bands)
    result=with_pdf_wall_recognition(payload,image,index)
    assert len(result.walls.items)==len(bands)
    pairs=[(w.start.x,w.start.y,w.end.x,w.end.y) for w in result.walls.items]
    assert sorted(pairs)==sorted((*a,*b) for a,b,_,_ in bands)


def test_scaled_source_coordinates_yield_scaled_banks_and_widths():
    image,payload,index=scene(L_BANDS)
    baseline=with_pdf_wall_recognition(payload,image,index)
    rows=deepcopy(index.objects)
    for row in rows:
        row['bounds']=[v*2 for v in row['bounds']]
        for command in row['commands']:command[1]*=2;command[2]*=2
    region=payload.regions[0]
    payload=payload.model_copy(update={'source_plane':SourcePlane(width_pixels=2000,height_pixels=1600),
        'regions':(region.model_copy(update={'bounds':PixelBounds(x=80,y=80,width=1840,height=1440)}),)})
    result=with_pdf_wall_recognition(payload,cv2.resize(image,(2000,1600)),PrimitiveIndex(dict(objects=rows)))
    assert len(result.walls.items)==len(baseline.walls.items)
    for a,b in zip(baseline.walls.items,result.walls.items):
        np.testing.assert_allclose([b.start.x,b.start.y,b.end.x,b.end.y,b.estimated_thickness_pixels],
            np.array([a.start.x,a.start.y,a.end.x,a.end.y,a.estimated_thickness_pixels])*2)


def test_exhausted_spatial_reference_budget_keeps_previous_geometry(monkeypatch):
    image,payload,index=scene(L_BANDS);diagnostics=[]
    monkeypatch.setitem(CONFIGURATION,'maximum_spatial_references',1)
    assert with_pdf_wall_recognition(payload,image,index,diagnostics)==payload
    assert any(r['reason']=='spatial_reference_budget_exceeded' for r in diagnostics)


def test_short_cv_overshoot_is_refined_by_source_bank_and_keeps_id_order():
    image,payload,index=scene(L_BANDS)
    wall=WallCandidate(id='wall-0001',start=PixelPoint(x=168,y=218),end=PixelPoint(x=500,y=218),
        estimated_thickness_pixels=9,evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    unrelated=WallCandidate(id='wall-0002',start=PixelPoint(x=720,y=400),end=PixelPoint(x=720,y=550),
        estimated_thickness_pixels=8,evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    payload=payload.model_copy(update={'walls':CandidateCollection(state='partial',items=(wall,unrelated))})
    result=with_pdf_wall_recognition(payload,image,index)
    assert [w.id for w in result.walls.items]==['wall-0001','wall-0002','wall-0003']
    refined=result.walls.items[0]
    assert refined.start.x==180 and refined.start.y==220 and refined.end.x==500
    assert result.walls.items[1]==unrelated


def test_native_refinement_preserves_existing_warning_wall_reference():
    image,payload,index=scene(L_BANDS)
    walls=tuple(WallCandidate(id=f'wall-{i:04d}',start=PixelPoint(x=180,y=y),end=PixelPoint(x=500,y=y),
        estimated_thickness_pixels=8,evidence_refs=('region:region-0001',),ambiguity='ambiguous')
        for i,y in [(1,218),(2,222)])
    warning=CandidateWarning(code='wall_evidence_note',severity='info',message='Original source wall evidence.',entity_refs=('wall:wall-0002',))
    payload=payload.model_copy(update={'walls':CandidateCollection(state='partial',items=walls),'warnings':payload.warnings+(warning,)})
    result=with_pdf_wall_recognition(payload,image,index)
    assert warning in result.warnings
    assert len(result.walls.items)==2
    assert result.walls.items[0].id=='wall-0002'
    assert result.walls.items[0].start.y==220


def test_native_wall_evidence_references_are_remapped_when_source_views_merge():
    from app.ai.floor_plan_interpretation.scoped_analysis import merge_view_payloads
    image,payload,index=scene(L_BANDS)
    result=with_pdf_wall_recognition(payload,image,index)
    merged=merge_view_payloads([result,result])
    refs=[w.entity_refs for w in merged.warnings if w.code=='pdf_native_hatched_wall_band']
    assert refs==[(f'wall:{w.id}',) for w in merged.walls.items]
    assert all('region_id' not in w.message for w in merged.warnings if w.code=='pdf_native_hatched_wall_band')
