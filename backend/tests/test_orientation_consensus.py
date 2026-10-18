"""Geometry/selection contracts, not an independent recognition accuracy set."""
import numpy as np
import pytest
from app.ai.floor_plan_interpretation.orientation_consensus import (
    locate_orientation_consensus, restore_box, restore_prediction,
)


@pytest.mark.parametrize('turn,box', [(0,(10,20,30,40)),(1,(20,170,40,190)),
                                    (2,(170,60,190,80)),(3,(60,10,80,30))])
def test_inverse_turn_restores_continuous_image_edge_boxes(turn,box):
    assert restore_box(box,200,100,turn)==(10,20,30,40)
    row={'bbox':box,'tile_origin':(0,0),'class_id':1,'score':.8,
         'localization_observations':({'bbox':box,'class_id':1,'score':.8},),
         'equivalent_observations':({'bbox':box,'class_id':2,'score':.7},)}
    restored=restore_prediction(row,200,100,turn)
    assert restored['bbox']==(10,20,30,40)
    assert restored['localization_observations'][0]['bbox']==restored['bbox']
    assert restored['equivalent_observations'][0]['bbox']==restored['bbox']
    assert row['bbox']==box  # Immutable diagnostic evidence.
    assert all(v>=0 for v in restored['tile_origin'])  # Padded edge tiles stay inside the source.


def test_corroborated_view_wins_over_many_unrelated_high_score_guesses():
    rgb=np.arange(100*200*3,dtype=np.uint8).reshape(100,200,3)
    source=((10,20,30,40),(80,50,100,70))
    turns=[(0,200,100),(3,100,200),(2,200,100),(1,100,200)]
    calls=[]
    def infer(image):
        k=len(calls);calls.append(image.copy())
        if k==0:
            return tuple({'bbox':(i*3,1,i*3+2,3),'class_id':9,'score':.99}
                         for i in range(25)),False
        inverse,w,h=turns[k]
        return tuple({'bbox':restore_box(b,w,h,inverse),'class_id':1,'score':.9 if k==3 else .8}
                     for b in source),False
    diagnostics={}
    rows,truncated=locate_orientation_consensus(rgb,infer,{1:'outlet',9:'other'},diagnostics=diagnostics)
    assert len(calls)==4 and all(np.array_equal(im,np.rot90(rgb,k)) for k,im in enumerate(calls))
    assert diagnostics['selected_turn']==3
    assert tuple(p['bbox'] for p in rows)==source
    assert not truncated and all(p['inference_rotation_ccw']==270 for p in rows)


def test_inconclusive_and_capped_views_are_explicit_not_arbitrary_new_devices():
    calls=[]
    def infer(image):
        calls.append(1)
        return ({'bbox':(1,2,3,4),'class_id':len(calls),'score':.9},),len(calls)==3
    rows,truncated=locate_orientation_consensus(np.zeros((20,40,3),np.uint8),infer,{})
    assert rows[0]['class_id']==1 and truncated


def test_sparse_agreement_cannot_replace_native_with_mostly_unsupported_marks():
    # Even the highest absolute agreement is inconclusive if most candidates
    # in that view have no corroboration. This guards dense noisy scans.
    calls=[]
    def infer(image):
        k=len(calls);calls.append(k)
        rows=[{'bbox':(5,5,15,15),'class_id':k*100+i,'score':.8} for i in range(20)]
        # Central rotation-symmetric boxes/classes agree in every view.
        rows[:2]=[{'bbox':(10+i,10+i,30-i,30-i),'class_id':i,'score':.9} for i in range(2)]
        return tuple(rows),False
    details={}
    rows,_=locate_orientation_consensus(np.zeros((40,40,3),np.uint8),infer,{},diagnostics=details)
    assert not details['orientation_resolved'] and details['selected_turn']==0
    assert rows[2]['class_id']==2
