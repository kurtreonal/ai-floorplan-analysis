from copy import deepcopy
from types import SimpleNamespace as NS

import numpy as np
import pytest

from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload, SourcePlane, CandidateWarning
from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence
from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion, restore_region_payload
from app.ai.floor_plan_interpretation.pdf_views import propose_pdf_views
from app.ai.floor_plan_interpretation.scoped_analysis import merge_view_payloads
from app.services import interpretation_processing_service as worker
from app.services.wiring_legend_service import annotate_wiring
from tests.test_device_contact_evidence import source
from tests.test_wiring_legend_service import catalog


def test_two_view_contacts_remain_separate_and_survive_json_reload():
    image,local=source(inline=True,crossing=True)
    local=with_device_contact_evidence(local,image)
    before=local.model_dump_json()
    plane=SourcePlane(width_pixels=800,height_pixels=400)
    first=restore_region_payload(local,region=DrawingRegion(x=0,y=0,width=320,height=200),source_plane=plane)
    second=restore_region_payload(local,region=DrawingRegion(x=400,y=100,width=320,height=200),source_plane=plane)
    result=merge_view_payloads([first,second])
    assert len(result.observed_routes.connections)==6
    assert len(result.symbols.items)==6
    assert len(result.observed_routes.segments)==2
    assert all(c.from_ref=='segment:segment-0001' and c.to_ref in
        {'symbol:symbol-0001','symbol:symbol-0002','symbol:symbol-0003'} for c in result.observed_routes.connections[:3])
    assert all(c.from_ref=='segment:segment-0002' and c.to_ref in
        {'symbol:symbol-0004','symbol:symbol-0005','symbol:symbol-0006'} for c in result.observed_routes.connections[3:])
    assert {r.id for r in result.regions}=={'region-0001','region-0002'}
    assert result.observed_routes.segments[1].evidence_refs==('region:region-0002',)
    assert FloorPlanInterpretationPayload.model_validate_json(result.model_dump_json())==result
    assert local.model_dump_json()==before


def test_scope_is_shared_by_geometry_symbols_and_postprocessing(monkeypatch):
    rgb=np.full((400,800,3),255,np.uint8)
    image,local=source()
    rgb[100:300,400:720]=image
    regions=[]
    monkeypatch.setattr(worker,'interpret_floor_plan_demo',lambda image,**kw: local)
    monkeypatch.setattr(worker.multiclass,'locate',lambda image: (regions.append(image.shape) or (),False))
    monkeypatch.setattr(worker.multiclass,'with_proposals',lambda p,*_:p)
    stages=[]
    for name in ('with_switch_gang_proposals','with_chromatic_wall_evidence','with_fixture_wall_conflicts','with_automatic_wiring'):
        def observe(p,*args,_name=name):
            stages.append((_name,p.regions[0].bounds.model_dump()))
            return p
        monkeypatch.setattr(worker,name,observe)
    before=rgb.copy()
    result=worker._interpret_cv_scope(rgb,region=DrawingRegion(x=400,y=100,width=320,height=200),
        experimental=False,trained=True,general=True,linked=False)
    assert regions==[(200,320,3)]
    assert len(stages)==4
    assert all(bounds==dict(x=400,y=100,width=320,height=200) for _,bounds in stages)
    assert all('region:region-0001' in s.evidence_refs for s in result.symbols.items)
    np.testing.assert_array_equal(rgb,before)


def test_pdf_legend_warning_disables_universal_dash_meaning_but_retains_explicit_selection():
    _,payload=source()
    payload=payload.model_copy(update={'warnings':payload.warnings+(CandidateWarning(
        code='drawing_legend_required',severity='warning',message='Review the drawing-specific legend.'),)})
    candidate=NS(payload=payload)
    review=dict(observed_wiring=[dict(id='segment-0001',line_style='dashed',points=[]),
        dict(id='manual-wiring-0001',line_style='solid',points=[],wiring_legend_id=11)])
    before=deepcopy(review)
    result=annotate_wiring(catalog(),candidate,review)
    assert result['observed_wiring'][0]['installation_method']=='unknown'
    assert result['observed_wiring'][1]['installation_method']=='concealed_in_ceiling'
    assert review==before


def view_evidence():
    texts=[dict(id=1,type=1,text='GROUND FLOOR',bounds=[100,650,210,670]),
           dict(id=2,type=1,text='POWER LAYOUT',bounds=[100,674,240,698]),
           dict(id=3,type=1,text='MEZZANINE',bounds=[620,650,730,670]),
           dict(id=4,type=1,text='POWER LAYOUT',bounds=[620,674,780,698])]
    banks=[dict(id=10,type=3,bounds=[60,220,400,230]),dict(id=11,type=3,bounds=[60,420,400,430]),
           dict(id=12,type=3,bounds=[590,220,930,230]),dict(id=13,type=3,bounds=[590,420,930,430])]
    divider=dict(id=20,type=2,stroke=True,dash_array=[],commands=[[2,500,0,False],[0,500,800,False]])
    return dict(source_plane=dict(width_pixels=1000,height_pixels=800),objects=texts+banks+[divider])


def test_caption_scopes_are_partial_and_not_filename_or_absolute_position_specific():
    example=view_evidence();before=deepcopy(example)
    views=propose_pdf_views(example)
    assert [v['label'] for v in views]==['GROUND FLOOR','MEZZANINE']
    assert all(v['state']=='proposed_partial' for v in views)
    assert views[0]['region'].x+views[0]['region'].width<views[1]['region'].x
    scaled=deepcopy(example)
    scaled['source_plane']=dict(width_pixels=2000,height_pixels=1600)
    for obj in scaled['objects']:
        if 'bounds' in obj:obj['bounds']=[v*2 for v in obj['bounds']]
        for command in obj.get('commands',[]):command[1]*=2;command[2]*=2
    enlarged=propose_pdf_views(scaled)
    assert [v['label'] for v in enlarged]==[v['label'] for v in views]
    for a,b in zip(views,enlarged):
        for key in ('x','y','width','height'):
            assert abs(b['region'].model_dump()[key]-a['region'].model_dump()[key]*2)<=2
    assert example==before


def test_missing_native_caption_or_visual_anchor_does_not_invent_regions():
    example=view_evidence()
    example['objects']=[o for o in example['objects'] if o['type']!=3]
    assert propose_pdf_views(example)==()
    example=view_evidence()
    example['objects'][0]['text']='UNRELATED TABLE'
    assert propose_pdf_views(example)==()
    example=view_evidence()
    example['objects'][-1]['commands'][0][1]=950
    example['objects'][-1]['commands'][1][1]=950
    assert propose_pdf_views(example)==() # same column cannot silently merge two floors


def test_geometry_failure_stays_visible_while_independent_layers_continue(monkeypatch):
    from app.ai.floor_plan_interpretation.demo_cv import DemoCVError
    image,_=source()
    monkeypatch.setattr(worker,'interpret_floor_plan_demo',lambda *_a,**_kw: (_ for _ in ()).throw(DemoCVError('INFERENCE_FAILED')))
    result=worker._interpret_cv_scope(image,region=None,experimental=False,trained=False,general=False,linked=False)
    assert result.walls.state=='failed' and result.rooms.state=='failed'
    assert result.document_state=='partial'
    assert any(w.code=='geometry_layer_failed' for w in result.warnings)


def test_wiring_failure_does_not_erase_geometry_or_claim_complete_success(monkeypatch):
    image,initial=source()
    monkeypatch.setattr(worker,'interpret_floor_plan_demo',lambda *_a,**_kw: initial)
    monkeypatch.setattr(worker,'with_automatic_wiring',lambda *_a: (_ for _ in ()).throw(RuntimeError('private internal detail')))
    result=worker._interpret_cv_scope(image,region=None,experimental=False,trained=False,general=False,linked=False)
    assert result.symbols==initial.symbols
    assert result.observed_routes.state=='failed'
    assert result.document_state=='partial'
    assert 'private internal detail' not in result.model_dump_json()
    assert any(w.code=='wiring_layer_failed' for w in result.warnings)


def test_all_failed_wiring_views_keep_failed_layer_status_on_merge():
    from app.ai.floor_plan_interpretation.scoped_analysis import failed_wiring_payload
    _,initial=source()
    result=merge_view_payloads([failed_wiring_payload(initial),failed_wiring_payload(initial)])
    assert result.observed_routes.state=='failed'
    assert result.observed_routes.segments==()


def test_multiview_publication_guard_is_public_conflict_not_an_unsaved_draft_rejection():
    from app.api.routes.demo_interpretation import _error
    from app.services.demo_interpretation_service import DemoInterpretationError
    error=_error(DemoInterpretationError('SOURCE_VIEW_ASSIGNMENT_REQUIRED'))
    assert error.status_code==409
    assert error.detail['error']['code']=='SOURCE_VIEW_ASSIGNMENT_REQUIRED'
    assert 'draft can still be saved' in error.detail['error']['message']
