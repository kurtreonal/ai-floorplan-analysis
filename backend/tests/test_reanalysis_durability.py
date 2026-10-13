from copy import deepcopy

import numpy as np

from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo, preprocessing_configuration
from app.ai.floor_plan_interpretation.reviewed_reference import inherit_review_draft
from app.ai.floor_plan_interpretation.candidate import CandidateHostProvenance, build_candidate_envelope
from datetime import UTC, datetime


def candidate():
    return build_candidate_envelope(interpret_floor_plan_demo(np.full((100, 100, 3), 255, np.uint8)),
        CandidateHostProvenance(candidate_run_id='a'*32, processing_job_id=1,
            floor_plan_source_id=1, floor_plan_page_id=1, source_artifact_id=1,
            source_page_number=1, source_sha256='a'*64, source_artifact_sha256='b'*64,
            expected_width_pixels=100, expected_height_pixels=100,
            model_release_id='test', base_model_revision='test', adapter_revision=None,
            prompt_version='test', runtime_version='test', inference_parameters=(), created_at=datetime.now(UTC)))


def test_partial_manual_corrections_survive_without_any_new_observations():
    c = candidate()
    document = {'walls': [{'id':'manual-wall-0001', 'disposition':'added',
        'start':{'x':10,'y':10},'end':{'x':10,'y':90}}], 'rooms': [],
        'symbols': [{'id':'manual-symbol-0001','disposition':'added','center':{'x':20,'y':20},
                     'symbol_legend_id':2,'custom_unit_price':99}],
        'observed_wiring':[{'id':'manual-wiring-0001','disposition':'added',
            'points':[{'x':20,'y':20},{'x':80,'y':20}], 'completeness':'partial',
            'device_attachments':[{'symbol_id':'manual-symbol-0001','point_index':0}]}],
        'review_complete':True,'approved_for_layout':True,'dataset_approval':{'decision':'approved'}}
    before = deepcopy(document)
    result = inherit_review_draft(c, c, document)
    assert result['walls'] == document['walls']
    assert result['symbols'] == document['symbols']
    assert result['observed_wiring'] == document['observed_wiring']
    assert not {'review_complete','approved_for_layout','dataset_approval'} & result.keys()
    assert document == before


def test_preprocessing_configuration_is_explicit_and_repeatable():
    a = preprocessing_configuration(1340,3264)
    assert a == preprocessing_configuration(1340,3264)
    assert a['resize'] == 'none' and a['block_size'] == 121
    assert a['walls']['structural_mode'] is True

def test_unchanged_unapproved_wall_snapshots_do_not_duplicate_new_proposals_but_real_edits_survive():
    c=candidate()
    from app.ai.floor_plan_interpretation.candidate import WallCandidate,CandidateCollection,PixelPoint
    old=c.model_copy(update={'payload':c.payload.model_copy(update={'walls':CandidateCollection(state='partial',items=(
        WallCandidate(id='wall-0001',start=PixelPoint(x=10,y=10),end=PixelPoint(x=90,y=10),evidence_refs=('region:region-0001',),ambiguity='ambiguous'),),truncated=False)})})
    fresh=old.model_copy(update={'payload':old.payload.model_copy(update={'walls':CandidateCollection(state='partial',items=(
        old.payload.walls.items[0].model_copy(update={'start':PixelPoint(x=10,y=11),'end':PixelPoint(x=90,y=11)}),),truncated=False)})})
    saved={'walls':[dict(id='wall-0001',disposition='accepted',start=dict(x=10,y=10),end=dict(x=90,y=10))],
           'rooms':[],'symbols':[],'observed_wiring':[],'review_complete':False,'approved_for_layout':False}
    assert len(inherit_review_draft(fresh,old,saved)['walls'])==1
    assert inherit_review_draft(fresh,old,saved)['walls'][0]['start']['y']==11
    edited=deepcopy(saved);edited['walls'][0]['start']['y']=12
    result=inherit_review_draft(fresh,old,edited)['walls']
    assert len(result)==2 and result[1]['start']['y']==12
    approved={**saved,'approved_for_layout':True}
    assert len(inherit_review_draft(fresh,old,approved)['walls'])==2
    assert saved['walls'][0]['start']['y']==10
