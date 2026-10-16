from copy import deepcopy
import json
from types import SimpleNamespace as NS
import pytest
from tests.test_wiring_recovery import curved
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring, RecoveryLimits
from app.services.wiring_recovery_service import RecoveryCheckpointStore, recover_worker_wiring


def test_immutable_bound_checkpoints_resume_and_ignore_corrupt_or_foreign_source(tmp_path):
    image,payload=curved();limits=RecoveryLimits()
    store=RecoveryCheckpointStore(tmp_path,job_id=1,page_id=2,source_sha256='a'*64,payload=payload,limits=limits)
    states=[]
    result=recover_wiring(payload,image,checkpoint=lambda s:(states.append(deepcopy(s)),store.save(s)))
    files=list(store.directory.glob('*.json'));before={p:p.read_bytes() for p in files}
    assert store.load()['payload']['observed_routes']['recovery']['stop_reason']=='converged'
    resumed=recover_wiring(payload,image,resume=store.load())
    assert resumed.observed_routes.segments==result.observed_routes.segments
    assert all(p.read_bytes()==value for p,value in before.items())
    newest=store.reference;newest.write_text('{corrupt',encoding='utf-8')
    assert store.load() is not None  # earlier fully written checkpoint remains
    other=RecoveryCheckpointStore(tmp_path,job_id=1,page_id=2,source_sha256='b'*64,payload=payload,limits=limits)
    assert other.load() is None


def test_worker_cancel_keeps_recoverable_proposals_and_does_not_publish_review(tmp_path):
    image,payload=curved();calls=[]
    def heartbeat():
        calls.append(1)
        if len(calls)==3:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):
        recover_worker_wiring(payload,image,root=tmp_path,job_id=1,page_id=2,source_sha256='a'*64,settings=NS(),heartbeat=heartbeat)
    assert list(tmp_path.rglob('checkpoint-*.json'))
    result,parameters=recover_worker_wiring(payload,image,root=tmp_path,job_id=1,page_id=2,source_sha256='a'*64,settings=NS(),heartbeat=lambda:None)
    assert result.observed_routes.recovery.stop_reason=='converged'
    assert {p.name for p in parameters}>={'wiring-recovery-reference','wiring-recovery-sha256'}


def test_source_junction_adapts_to_proposal_without_changing_human_edits():
    from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
    from app.routing.endpoint_connections import apply_source_junctions
    image,payload=curved();raw=payload.model_dump(mode='json')
    raw['document_state']='partial'
    raw['observed_routes']=dict(state='partial',segments=[dict(id=f'segment-{i:04d}',points=points,evidence_refs=['region:region-0001'],ambiguity='ambiguous')
        for i,points in [(1,[dict(x=10,y=20),dict(x=40,y=20)]),(2,[dict(x=40,y=20),dict(x=40,y=70)])]],
        junctions=[dict(id='junction-0001',members=[dict(segment_id=f'segment-{i:04d}',point_index=index) for i,index in [(1,1),(2,0)]],
            evidence_kind='source_corner_contact',evidence_refs=['region:region-0001'],ambiguity='clear')])
    candidate=NS(payload=FloorPlanInterpretationPayload.model_validate(raw),provenance=NS(candidate_run_id='a'*32))
    doc={'observed_wiring':[dict(id=r.id,points=[p.model_dump() for p in r.points],disposition='unresolved') for r in candidate.payload.observed_routes.segments]}
    before=deepcopy(candidate.payload)
    result=apply_source_junctions(candidate,deepcopy(doc))
    assert all(w['disposition']=='unresolved' and w['junction_attachments'][0]['source_candidate_run_id']=='a'*32 for w in result['observed_wiring'])
    assert candidate.payload==before
    doc['observed_wiring'][0]['disposition']='corrected'
    assert apply_source_junctions(candidate,doc)==doc
