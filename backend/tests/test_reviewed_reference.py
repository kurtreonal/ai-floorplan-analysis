"""Reanalysis must not relabel a human reference as fresh AI/approved training."""
from copy import deepcopy
from types import SimpleNamespace as NS

from app.ai.floor_plan_interpretation.candidate import PixelPoint
from app.ai.floor_plan_interpretation.reviewed_reference import (
    has_manual_wiring_replacement, inherit_manual_reference,
)
from app.routing.draft_wiring import generate_draft_wiring


def candidate(source='a', region=(0, 0, 400, 300)):
    return NS(provenance=NS(source_sha256=source), payload=NS(
        source_plane={'width_pixels':400, 'height_pixels':300},
        regions=[NS(kind='plan_region', bounds=region)],
        walls=NS(items=[NS(id='wall-0007', start=PixelPoint(x=10,y=10),
                          end=PixelPoint(x=100,y=10))]),
        observed_routes=NS(segments=[NS(id='segment-0009', line_style='solid',
            points=[PixelPoint(x=20,y=20),PixelPoint(x=20,y=80)])])))


def reference():
    return dict(observed_wiring=[
        dict(id='segment-0001', disposition='rejected', points=[{'x':1,'y':1},{'x':2,'y':1}]),
        dict(id='manual-wiring-0001', disposition='added', completeness='partial',
             points=[{'x':20.123,'y':30.456},{'x':100.789,'y':30.456}],
             installation_method='concealed_in_ceiling', elevation_meters=None)],
        generated_wiring=[dict(id='manual-route-0001',disposition='rejected')],
        walls=[dict(id='wall-0001',disposition='rejected'),dict(id='manual-wall-0001',
            disposition='added', start={'x':10.1,'y':10.2},end={'x':10.1,'y':100.2})],
        review_complete=True, approved_for_layout=True, dataset_approval={'decision':'approved'})


def test_reanalysis_keeps_exact_manual_vectors_and_maps_only_new_candidate_tombstones():
    document=reference(); before=deepcopy(document)
    carried=inherit_manual_reference(candidate(),candidate(),document)
    assert carried['observed_wiring'][0]['id']=='segment-0009'
    assert carried['observed_wiring'][0]['disposition']=='rejected'
    assert carried['observed_wiring'][1]==document['observed_wiring'][1]
    assert carried['walls'][0]['id']=='wall-0007'
    assert carried['walls'][1]==document['walls'][1]
    assert carried['generated_wiring']==[]
    assert not {'review_complete','approved_for_layout','dataset_approval'} & carried.keys()
    carried['walls'][1]['start']['x']=12
    assert document==before


def test_changed_hash_plane_or_region_never_inherits_reference():
    assert inherit_manual_reference(candidate('b'),candidate(),reference())=={}
    altered=candidate(); altered.payload.source_plane['width_pixels']=401
    assert inherit_manual_reference(altered,candidate(),reference())=={}
    assert inherit_manual_reference(candidate(region=(0,0,200,300)),candidate(),reference())=={}


def test_partial_manual_edit_does_not_suppress_unreviewed_wiring_or_walls():
    document=reference()
    document['observed_wiring'][0]['disposition']='unresolved'
    document['walls'][0]['disposition']='accepted'
    assert not has_manual_wiring_replacement(document)
    assert inherit_manual_reference(candidate(),candidate(),document)=={}
    document=reference(); document['generated_wiring'][0]['disposition']='corrected'
    assert not has_manual_wiring_replacement(document)


def test_deleted_manual_references_do_not_reappear_and_router_does_not_reconnect_branches():
    document=reference()
    generated,notes=generate_draft_wiring(candidate(),document)
    assert generated==document['generated_wiring']
    assert 'replaces automatic' in notes[0]
    document['observed_wiring'][1]['disposition']='rejected'
    carried=inherit_manual_reference(candidate(),candidate(),document)
    assert carried['observed_wiring'][1]['disposition']=='rejected'
    assert generate_draft_wiring(candidate(),carried)[0]==[]


def test_ordinary_manual_only_drawing_keeps_automatic_routing_enabled():
    document=reference()
    document['observed_wiring']=document['observed_wiring'][1:]
    document['generated_wiring']=[]
    assert not has_manual_wiring_replacement(document)
