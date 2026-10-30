"""Preview/apply source-backed wiring repairs as a NEW saved draft revision.

No original candidate, source file, material choice or non-wiring geometry is
rewritten. --apply is explicit; expected job/revision provide concurrency checks.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.database import get_session_factory
from app.core.config import get_processed_directory
from app.models import User,ProcessingArtifact
from app.repositories.floor_plan_interpretation_repository import find_latest_for_floor_plan,find_latest_review
from app.ai.floor_plan_interpretation.automatic_wiring import with_automatic_wiring,with_fixture_wall_conflicts,EVIDENCE_VERSION
from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring,RecoveryLimits
from app.ai.floor_plan_interpretation.trace_cleanup import deduplicate_traces
from app.routing.endpoint_connections import apply_source_contacts
from app.routing.draft_wiring import draft_path
from app.geometry.wire_network import wire_networks
from app.schemas.demo_interpretation import DemoReviewRequest
from app.services.demo_interpretation_service import _candidate,append_interpretation_review
from app.services.activity_log import record

SCOPE=('circuit_id','elevation_meters','height_above_floor_meters','installation_method')
def active(w):return w.get('disposition')!='rejected' and not w.get('suppression_reason')
def scope(w):return tuple(w.get(k,'unknown' if k=='installation_method' else None) for k in SCOPE)
def same(a,b):return abs(a['x']-b['x'])<1e-6 and abs(a['y']-b['y'])<1e-6

def prune_junctions(doc):
    wires=doc['observed_wiring']+doc['generated_wiring'];members={}
    for wire in wires:
        if active(wire):
            for a in wire.get('junction_attachments',[]):members.setdefault(a['junction_id'],set()).add(wire['id'])
    for wire in wires:wire['junction_attachments']=[a for a in wire.get('junction_attachments',[]) if len(members.get(a['junction_id'],()))>1]

def prepare(candidate,document,fresh):
    doc=deepcopy(document);notes=[];old={w.id:w for w in candidate.payload.observed_routes.segments};raw={w.id:w for w in fresh.observed_routes.segments}
    wires={w['id']:w for w in doc['observed_wiring']};symbols={s['id']:s for s in doc['symbols']}
    def covered(a,b,target):
        start=np.array([a['x'],a['y']]);delta=np.array([b['x']-a['x'],b['y']-a['y']]);length=float(np.linalg.norm(delta));axis=delta/length;normal=np.array([-axis[1],axis[0]]);spans=[]
        for c,d in zip(target['points'],target['points'][1:]):
            ends=np.array([[c['x'],c['y']],[d['x'],d['y']]])-start
            if max(abs(ends@normal))<.01:spans.append(sorted(ends@axis))
        end=0
        for lo,hi in sorted(spans):
            if hi<end:continue
            if lo>end+.01:return False
            end=max(end,float(hi))
            if end>=length-.01:return True
        return False
    for identity in set(old)-{w.id for w in deduplicate_traces(candidate.payload).observed_routes.segments}:
        wire=wires.get(identity)
        if not wire or not active(wire):continue
        target=next((w for w in wires.values() if w['id']!=identity and active(w) and scope(w)==scope(wire) and all(covered(a,b,w) for a,b in zip(wire['points'],wire['points'][1:]))),None)
        if target:wire['disposition']='rejected';notes.append(f"Removed duplicate {identity}; retained {target['id']}.")
    prune_junctions(doc)
    def key(c):return (c.to_ref,round(c.path_anchor.x,6),round(c.path_anchor.y,6))
    old_ports={identity:{key(c) for c in candidate.payload.observed_routes.connections if c.from_ref=='segment:'+identity and c.evidence_kind and c.path_anchor} for identity in old}
    mapping={};repaired=set()
    for identity,wire in wires.items():
        if not active(wire) or identity not in old or wire.get('path_origin')=='manual':continue
        matches=[r for r in fresh.observed_routes.segments if old_ports[identity] and old_ports[identity]&{key(c) for c in fresh.observed_routes.connections if c.from_ref=='segment:'+r.id and c.evidence_kind and c.path_anchor}]
        if len(matches)!=1:continue
        source=matches[0];mapping[source.id]=identity
        occupied={a['point_index'] for a in wire.get('device_attachments',[])}|{a['point_index'] for a in wire.get('junction_attachments',[])}
        # Only endpoint tails without device/junction bindings are replaced.
        for index in (0,len(wire['points'])-1):
            if index in occupied:continue
            side=0 if index==0 else -1;before=old[identity].points[side].model_dump()
            if not same(wire['points'][index],before):continue
            anchors=[(i,j) for i,p in enumerate(wire['points']) for j,q in enumerate(source.points) if same(p,q.model_dump()) and i!=index]
            if not anchors:continue
            i,j=min(anchors,key=lambda ij:abs(ij[0]-index))
            segment=[p.model_dump() for p in (source.points[:j] if index==0 else source.points[j+1:])]
            if not segment:continue
            points=segment+wire['points'][i:] if index==0 else wire['points'][:i+1]+segment
            offset=len(segment)-i if index==0 else 0
            for field in ('device_attachments','junction_attachments'):
                for a in wire.get(field,[]):a['point_index']+=offset
            wire.update(points=points,disposition='corrected',auto_connect_disabled_endpoints=[]);wire.pop('vertex_ids',None);repaired.add(source.id)
            notes.append(f'Repaired free source endpoint on {identity}.');break
    used={a['junction_id'] for w in doc['observed_wiring']+doc['generated_wiring'] for a in w.get('junction_attachments',[])}
    def junction(members):
        number=next(n for n in range(1,10000) if f'junction-{n:04d}' not in used);identity=f'junction-{number:04d}';used.add(identity)
        for wire,index in members:wire['junction_attachments']=[*wire.get('junction_attachments',[]),dict(junction_id=identity,point_index=index)]
    for item in fresh.observed_routes.junctions:
        if len(item.members)!=2 or not all(m.segment_id in repaired for m in item.members):continue
        members=[]
        for member in item.members:
            wire=wires[mapping[member.segment_id]];point=raw[member.segment_id].points[member.point_index].model_dump();indices=[i for i,p in enumerate(wire['points']) if same(p,point)]
            if len(indices)!=1:break
            members.append((wire,indices[0]))
        if len(members)==2 and scope(members[0][0])==scope(members[1][0]):junction(members);notes.append('Joined pixel-supported source corner.')
    # Adapt the NEW source curves in memory. Saved bindings below are explicit
    # repair decisions; the old candidate's evidence record stays immutable.
    evidence=candidate.model_copy(update={'payload':fresh})
    adapted=apply_source_contacts(evidence,dict(symbols=doc['symbols'],observed_wiring=[dict(id=r.id,disposition='unresolved',points=[p.model_dump() for p in r.points]) for r in fresh.observed_routes.segments]))
    paths={w['id']:w for w in adapted['observed_wiring']}
    links=[]
    for marker in fresh.observed_routes.connections:
        if not marker.route_node_id or marker.evidence_kind is not None:continue
        home=marker.to_ref.split(':',1)[1];leader=paths[marker.from_ref.split(':',1)[1]]
        lower_contacts=[c for c in fresh.observed_routes.connections if c.from_ref==marker.from_ref and c.evidence_kind]
        if len(lower_contacts)!=1:continue
        lower=lower_contacts[0].to_ref.split(':',1)[1]
        for pair in fresh.observed_routes.segments:
            contacts={c.to_ref.split(':',1)[1] for c in fresh.observed_routes.connections if c.from_ref=='segment:'+pair.id and c.evidence_kind and c.route_node_id}
            if lower not in contacts or len(contacts)!=2:continue
            upper=next(iter(contacts-{lower}));manual=next((w for w in wires.values() if active(w) and w.get('path_origin')=='manual' and {a['symbol_id'] for a in w.get('device_attachments',[])}==contacts),None)
            if manual is None:continue
            points=deepcopy(paths[pair.id]['points']);lead=deepcopy(leader['points'])
            if not same(points[0],symbols[upper]['center']):points.reverse()
            if not same(lead[0],symbols[lower]['center']):lead.reverse()
            if not same(points[-1],lead[0]):continue
            points+=lead[1:]
            bindings=[]
            for a in manual.get('device_attachments',[]):
                indices=[i for i,p in enumerate(points) if same(p,symbols[a['symbol_id']]['center'])]
                if len(indices)!=1:raise ValueError('Device moved or has ambiguous repair anchors')
                bindings.append({**a,'point_index':indices[0]})
            manual.update(points=points,device_attachments=bindings,junction_attachments=[],auto_connect_disabled_endpoints=[],disposition='added',completeness='partial');manual.pop('vertex_ids',None)
            links.append((home,manual));notes.append(f"Repaired paired-outlet source curves on {manual['id']}.");break
    if len(links)!=2:raise ValueError('Expected two source-supported paired-outlet repairs; no draft will be saved')
    # Coalesce only the ordinary power-box route nodes established by v18 ink
    # evidence. Preserve real/custom terminals and differing circuit/height scopes.
    for symbol_id in {c.to_ref.split(':',1)[1] for c in fresh.observed_routes.connections if c.route_node_id and c.evidence_kind}:
        contacts=[(w,a) for w in wires.values() if active(w) for a in w.get('device_attachments',[]) if a['symbol_id']==symbol_id]
        if len(contacts)<2 or len({scope(w) for w,_ in contacts})!=1:continue
        if any(a.get('terminal_id') and not a['terminal_id'].startswith(('observed-port.','source-node.')) and a['terminal_id']!='design-anchor' for _,a in contacts):continue
        for wire,attachment in contacts:
            index=wire['device_attachments'].index(attachment);wire['device_attachments'][index]=dict(symbol_id=symbol_id,point_index=attachment['point_index'],terminal_id=f'source-node.{symbol_id}')
    walls=[w for w in doc['walls'] if w['disposition']!='rejected'];bands=[((w['start']['x'],w['start']['y']),(w['end']['x'],w['end']['y']),max(2,float(w.get('estimated_thickness_pixels') or 6)/2)) for w in walls]
    for home,manual in links:
        proposal=next((w for w in doc['generated_wiring'] if w.get('source_device_id')==home and w.get('target_kind')=='device'),None)
        if proposal is None:raise ValueError('No saved panel target exists for this homerun')
        panel=symbols[proposal['target_id']];start=manual['points'][-1];goal=panel['center'];region=next(r.bounds for r in fresh.regions if r.kind=='plan_region' and r.bounds.x<=start['x']<=r.bounds.x+r.bounds.width and r.bounds.y<=start['y']<=r.bounds.y+r.bounds.height)
        points=draft_path((start['x'],start['y']),(goal['x'],goal['y']),(region.x,region.y,region.x+region.width,region.y+region.height),bands,endpoint_clearances=(12,40))
        proposal.update(points=[dict(x=x,y=y) for x,y in points],disposition='added',assignment_state='unresolved',completeness='partial',junction_attachments=[],auto_connect_disabled_endpoints=[],device_attachments=[dict(symbol_id=panel['id'],point_index=len(points)-1,terminal_id=f"panel-route.{proposal['id']}")])
        for key in (*SCOPE,'line_style','wiring_legend_id','wiring_legend_name','conductor_count'):
            if key in manual:proposal[key]=manual[key]
        for key in ('suppression_reason','vertex_ids'):proposal.pop(key,None)
        junction([(manual,len(manual['points'])-1),(proposal,0)]);notes.append(f"Restored A* panel continuation for {home} using source leader endpoint.")
    prune_junctions(doc);wire_networks(doc['observed_wiring']+doc['generated_wiring'])
    doc['review_complete']=False;doc['approved_for_layout']=False;doc['dataset_approval']=None
    doc['evidence_notes']=(doc.get('evidence_notes','')+'\nSource-backed wiring repairs applied with '+EVIDENCE_VERSION+'. Earlier scan and draft retained; generated panel routes remain planning proposals.')[-1000:]
    return doc,notes

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--floor-plan-id',type=int,required=True);parser.add_argument('--job-id',type=int,required=True);parser.add_argument('--revision',type=int,required=True);parser.add_argument('--user-id',type=int,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    with get_session_factory()() as db:
        run=find_latest_for_floor_plan(db,floor_plan_id=args.floor_plan_id);review=find_latest_review(db,interpretation_run_id=run.id)
        if run.processing_job_id!=args.job_id or review.revision_number!=args.revision:raise ValueError('Saved draft changed; refresh the expected job/revision')
        candidate=_candidate(run);original=json.loads(review.review_json);source=db.get(ProcessingArtifact,run.source_artifact_id);path=get_processed_directory()/source.relative_path
        if hashlib.sha256(path.read_bytes()).hexdigest()!=candidate.provenance.source_sha256:raise ValueError('Source image checksum mismatch')
        image=cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB)
        payload=candidate.payload.model_copy(update={'observed_routes':candidate.payload.observed_routes.model_copy(update={'segments':(),'connections':(),'junctions':(),'recovery':None}),'warnings':tuple(w for w in candidate.payload.warnings if not any(ref.startswith(('segment:','connection:','junction:')) for ref in w.entity_refs))})
        fresh=with_automatic_wiring(with_fixture_wall_conflicts(payload),image);fresh=recover_wiring(fresh,image,limits=RecoveryLimits(maximum_windows=64,maximum_seconds=90))
        repaired,notes=prepare(candidate,original,fresh)
        submission={**repaired,'candidate_run_id':run.candidate_run_id,'expected_revision_number':args.revision}
        submission['symbols']=[{k:v for k,v in s.items() if k not in ('class_id','class_name')} for s in repaired['symbols']]
        request=DemoReviewRequest.model_validate_json(json.dumps(submission))
        for field in ('walls','rooms','symbols','openings','panels','scale_evidence','wall_height_meters','wall_thickness_meters'):
            if repaired.get(field)!=original.get(field):raise ValueError(f'Unrelated {field} changed')
        result=dict(version=EVIDENCE_VERSION,job_id=args.job_id,previous_revision=args.revision,source_sha256=candidate.provenance.source_sha256,notes=notes,review=repaired,applied=False)
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        if args.apply:
            db.rollback()
            record(db,db.get(User,args.user_id),'WIRING_REPAIR_REQUESTED','review',review.id,'Applied source-backed v18 wiring corrections as a new draft; original evidence and previous revision retained.')
            saved=append_interpretation_review(db,current_user=db.get(User,args.user_id),floor_plan_id=args.floor_plan_id,payload=request)
            result.update(applied=True,review_id=saved.review.id,revision_number=saved.review.revision_number);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='review'},indent=2))

if __name__=='__main__':main()
