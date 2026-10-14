from copy import deepcopy
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import CandidateCollection,PixelPoint,WallCandidate,SourcePlane
from app.ai.floor_plan_interpretation.pdf_evidence import PrimitiveIndex
from app.ai.floor_plan_interpretation.pdf_wall_evidence import with_pdf_wall_evidence
from tests.test_automatic_wiring import example


def hatch_scene(count=13,filled=False):
    image,payload=example()
    image=np.full((800,1000,3),255,np.uint8)
    payload=payload.model_copy(update={'source_plane':SourcePlane(width_pixels=1000,height_pixels=800)})
    direction=np.array([1.,1.])/np.sqrt(2);normal=np.array([-direction[1],direction[0]])
    a=np.array([100.,50.]);b=np.array([200.,150.])
    rows=[]
    for i in range(-(count//2),count//2+1):
        first=a+normal*i*5;last=b+normal*i*5
        cv2.line(image,tuple(np.rint(first).astype(int)),tuple(np.rint(last).astype(int)),(0,0,0),1)
        rows.append(dict(id=len(rows)+1,type=2,bounds=[min(first[0],last[0]),min(first[1],last[1]),
            max(first[0],last[0]),max(first[1],last[1])],commands=[[2,*first,False],[0,*last,False]],
            stroke=True,fill_mode=0,dash_array=[],clip_paths=[],level=0,stroke_width=1,
            stroke_color=[0,0,0,255],transform=[1,0,0,1,0,0]))
    if filled:cv2.line(image,tuple(a.astype(int)),tuple(b.astype(int)),(0,0,0),8)
    wall=WallCandidate(id='wall-0001',start=PixelPoint(x=100,y=50),end=PixelPoint(x=200,y=150),
        estimated_thickness_pixels=8,evidence_refs=('region:region-0001',),ambiguity='ambiguous')
    payload=payload.model_copy(update={'walls':CandidateCollection(state='completed',items=(wall,))})
    return image,payload,PrimitiveIndex(dict(objects=rows))


def test_regular_exported_hatching_is_not_a_wall_and_retains_suppression_evidence():
    image,payload,index=hatch_scene();original=payload.model_dump_json();pixels=image.copy()
    result=with_pdf_wall_evidence(payload,image,index)
    assert result.walls.items==()
    assert any(w.code=='pdf_repeated_hatch_wall' and 'primitive_ids' in w.message for w in result.warnings)
    assert result.rooms.state=='unavailable'
    assert payload.model_dump_json()==original
    np.testing.assert_array_equal(image,pixels)


def test_single_angled_wall_separate_parallel_walls_and_filled_bands_are_preserved():
    for count,filled in [(1,False),(3,False),(13,True)]:
        image,payload,index=hatch_scene(count,filled)
        assert with_pdf_wall_evidence(payload,image,index).walls==payload.walls


def test_clipped_or_dashed_primitives_are_not_used_as_hatch_rejection_evidence():
    image,payload,index=hatch_scene()
    rows=deepcopy(index.objects)
    for row in rows:row['dash_array']=[3,2]
    assert with_pdf_wall_evidence(payload,image,PrimitiveIndex(dict(objects=rows))).walls==payload.walls
    for row in rows:row['dash_array']=[];row['clip_paths']=[[[2,0,0,False]]]
    assert with_pdf_wall_evidence(payload,image,PrimitiveIndex(dict(objects=rows))).walls==payload.walls
