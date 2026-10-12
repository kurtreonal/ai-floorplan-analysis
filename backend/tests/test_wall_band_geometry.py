import math
import cv2
import numpy as np
import pytest
from app.ai.wall_detection.band_geometry import refine_filled_bands
from app.ai.wall_detection.detector import _consolidate_wall_segments
from app.ai.floor_plan_interpretation.preparation import fuse_detected_walls,WallCandidateObservation
from app.ai.floor_plan_interpretation.candidate import AffineTransform

@pytest.mark.parametrize('scale,angle',[(1,0),(2,0),(1,27),(2,27)])
def test_filled_corner_does_not_create_diagonal_wall_and_true_angled_wall_survives(scale,angle):
    matrix=cv2.getRotationMatrix2D((0,0),angle,scale);matrix[:,2]+=[100,220]
    def p(x,y):return matrix@np.array([x,y,1.])
    mask=np.zeros((800,900),np.uint8)
    rows=[]
    for a,b,width in [((20,100),(250,100),10),((250,100),(250,300),10),((60,240),(150,310),8)]:
        first,last=p(*a),p(*b)
        cv2.line(mask,tuple(np.rint(first).astype(int)),tuple(np.rint(last).astype(int)),255,width*scale)
        rows.append((*first,*last,width*scale))
    square=np.rint([p(x,y) for x,y in [(225,75),(275,75),(275,125),(225,125)]]).astype(int)
    cv2.fillPoly(mask,[square],255)
    rows.append((*p(230,120),*p(270,80),30*scale))
    before=mask.copy();result=refine_filled_bands(rows,mask)
    assert len(result)==3
    np.testing.assert_array_equal(before,mask)
    assert any(math.dist(s[:2],p(60,240))<2 for s in result)

def test_parallel_walls_and_white_doorway_are_not_merged_by_tolerance():
    mask=np.zeros((150,220),np.uint8)
    cv2.line(mask,(20,50),(180,50),255,2)
    cv2.line(mask,(20,55),(180,55),255,2)
    rows=[(20,50,180,50,2.,160.),(20,55,180,55,2.,160.)]
    assert len(_consolidate_wall_segments(rows,220,150,6,evidence_mask=mask))==2
    mask[:]=0;cv2.line(mask,(20,80),(90,80),255,4);cv2.line(mask,(95,80),(180,80),255,4)
    mask[:,91:95]=0 # explicit white opening; OpenCV round line caps extend by two pixels
    rows=[(20,80,90,80,4.,70.),(95,80,180,80,4.,85.)]
    assert len(_consolidate_wall_segments(rows,220,150,6,evidence_mask=mask))==2

def test_supported_fragments_and_duplicate_spans_are_consolidated():
    mask=np.zeros((150,220),np.uint8);cv2.line(mask,(20,80),(180,80),255,8)
    rows=[(20,80,90,80,8.,70.),(85,81,180,81,8.,95.),(30,79,80,79,8.,50.)]
    result=_consolidate_wall_segments(rows,220,150,6,evidence_mask=mask)
    assert len(result)==1
    assert math.dist(result[0][:2],(20,80))<2 and math.dist(result[0][2:4],(180,80))<2

def test_thin_dimension_tail_is_trimmed_without_erasing_a_short_thin_partition():
    mask=np.zeros((200,200),np.uint8)
    cv2.line(mask,(60,20),(60,60),255,1)
    cv2.line(mask,(60,60),(60,180),255,10)
    cv2.line(mask,(130,80),(160,80),255,2)
    result=refine_filled_bands([(60,40,60,180,10.),(130,80,160,80,2.)],mask)
    assert result[0][1]>=55
    assert math.dist(result[1][:2],(130,80))<2 and math.dist(result[1][2:4],(160,80))<2

def test_overlapping_tiles_fuse_only_actual_common_source_span_not_nearby_walls_or_gaps():
    observations=[WallCandidateObservation('region-0001',(20,50),(120,50)),
                  WallCandidateObservation('region-0002',(0,50),(100,50)),
                  WallCandidateObservation('region-0002',(0,53),(100,53)),
                  WallCandidateObservation('region-0002',(101,50),(120,50))]
    transforms={'region-0001':AffineTransform(a=2,b=0,c=0,d=2,e=0,f=0),
                'region-0002':AffineTransform(a=2,b=0,c=0,d=2,e=200,f=0)}
    result=fuse_detected_walls(observations,transforms)
    assert len(result)==3
    assert result[0].start.x==40 and result[0].end.x==400
    assert result[0].evidence_refs==('region:region-0001','region:region-0002')
    assert result[1].start.y==106
    assert result[2].start.x==402
