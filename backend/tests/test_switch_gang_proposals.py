import numpy as np
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.ai.floor_plan_interpretation.switch_semantics import with_switch_gang_proposals


def payload(name,text=None):
    value=interpret_floor_plan_demo(np.full((200,200,3),255,np.uint8),selected_drawing=True).model_dump()
    value['document_state']='partial'
    value['symbols']=dict(state='partial',truncated=False,items=[dict(id='symbol-0001',
        observed_label=name,mapping_state='unknown',catalog_class_id=None,center=dict(x=80,y=80),
        bounds=dict(x=60,y=60,width=40,height=40),orientation_degrees=None,
        evidence_refs=('region:region-0001',),ambiguity='ambiguous')])
    if text:value['ocr']=dict(state='partial',truncated=False,items=[dict(id='ocr-0001',
        region_id='region-0001',text=text,normalized_text=text.lower(),bounds=dict(x=65,y=65,width=15,height=15))])
    return FloorPlanInterpretationPayload.model_validate(value)


def test_only_identified_unknown_gang_switch_gets_provisional_default():
    before=payload('Gang switch');raw=before.model_dump_json()
    result=with_switch_gang_proposals(before);s=result.symbols.items[0]
    assert s.observed_label=='Gang switch' and getattr(s,'training_legend',None) is None
    assert s.gang_count_proposal.count==1 and s.gang_count_proposal.basis=='user_requested_default'
    assert s.gang_count_proposal.provisional is True and s.mapping_state=='unknown'
    assert result.warnings[-1].code=='switch_gang_provisional_default'
    assert before.model_dump_json()==raw
    assert with_switch_gang_proposals(result)==result
    assert FloorPlanInterpretationPayload.model_validate_json(result.model_dump_json())==result
    for label in ('Circuit homerun','Unknown symbol','Three way switch','Fan control switch'):
        assert with_switch_gang_proposals(payload(label)).symbols.items[0].gang_count_proposal is None


def test_readable_counts_win_without_rewriting_original_prediction():
    for label,count in [('Two gang device switch',2),('Three gang device switch',3)]:
        s=with_switch_gang_proposals(payload(label)).symbols.items[0]
        assert s.gang_count_proposal.count==count and s.observed_label==label
    s=with_switch_gang_proposals(payload('Gang switch','S3')).symbols.items[0]
    assert s.gang_count_proposal.count==3 and s.gang_count_proposal.basis=='source_text'
    s=with_switch_gang_proposals(payload('Gang switch','SYM_3')).symbols.items[0]
    assert s.gang_count_proposal.count==1 and s.gang_count_proposal.basis=='user_requested_default'


def test_absent_optional_extension_preserves_historical_shape():
    old=payload('Unknown symbol').symbols.items[0]
    assert 'gang_count_proposal' not in old.model_dump()
