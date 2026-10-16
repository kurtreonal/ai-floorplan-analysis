from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from tests.test_draft_wiring import candidate
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.routing.draft_wiring import generate_draft_wiring
from app.services.draft_bom_service import document_takeoff,price_rows


def source():
    raw=candidate().payload.model_dump(mode='json')
    raw['symbols']['items'][0]['observed_label']='Panelboard'
    raw['observed_routes']['recovery']=dict(stop_reason='methods_exhausted',passes=[],devices=[
        dict(symbol_id=s['id'],state='no_usable_observed_path',reason='no_supported_path_after_search') for s in raw['symbols']['items']])
    return NS(payload=FloorPlanInterpretationPayload.model_validate(raw))


def test_no_wire_drawing_gets_unassigned_geometric_alternative_not_electrical_attachment_or_measured_quantity():
    c=source();before=deepcopy(c.payload)
    wires,notes=generate_draft_wiring(c)
    assert len(wires)==1 and wires[0]['assignment_state']=='unresolved'
    assert wires[0]['elevation_meters'] is None and 'circuit_id' not in wires[0] and not wires[0].get('device_attachments')
    assert any('not an optimized multi-device' in n for n in notes)
    review={'generated_wiring':wires}
    rows=document_takeoff(review,scale=10,floor_elevation=0)
    assert rows[0]['unit']=='source pixel' and rows[0]['electrical_assignment_required']
    assert price_rows(rows,[])['items'][0]['pricing_state']=='electrical_assignment_required'
    assert generate_draft_wiring(c,review)[0]==wires
    wires[0]['disposition']='rejected'
    assert generate_draft_wiring(c,review)[0]==wires
    assert c.payload==before


def test_actual_glyph_only_raster_recovery_produces_only_unassigned_generated_alternative():
    import numpy as np
    import cv2
    from tests.test_automatic_wiring import example
    from app.ai.floor_plan_interpretation.wiring_recovery import recover_wiring
    image,payload=example();image[:]=255
    raw=payload.model_dump(mode='json')
    raw['symbols']['items'][0]['observed_label']='Panelboard'
    raw['symbols']['items'][1]['observed_label']='Duplex outlet'
    for symbol in raw['symbols']['items']:
        b=symbol['bounds'];cv2.rectangle(image,(int(b['x']),int(b['y'])),(int(b['x']+b['width']),int(b['y']+b['height'])),(0,0,0),2)
    recovered=recover_wiring(FloorPlanInterpretationPayload.model_validate(raw),image)
    assert not recovered.observed_routes.segments and not recovered.observed_routes.connections
    assert {d.state for d in recovered.observed_routes.recovery.devices}=={'no_usable_observed_path'}
    paths,_=generate_draft_wiring(NS(payload=recovered))
    assert len(paths)==1 and paths[0]['assignment_state']=='unresolved' and paths[0]['algorithm']=='astar'


def test_unresolved_source_ink_never_becomes_generated_replacement_and_unknown_source_is_explicit():
    c=source();raw=c.payload.model_dump(mode='json')
    raw['observed_routes']['recovery']['devices'][1].update(state='unresolved_observed',reason='partial_source_evidence')
    assert generate_draft_wiring(NS(payload=FloorPlanInterpretationPayload.model_validate(raw)))[0]==[]
    raw['symbols']['items'][0]['observed_label']='Duplex outlet'
    paths,notes=generate_draft_wiring(NS(payload=FloorPlanInterpretationPayload.model_validate(raw)))
    assert paths==[] and 'choose one source panel' in notes[0]


def test_no_path_retains_all_wall_obstacles():
    c=source();raw=c.payload.model_dump(mode='json')
    raw['walls']=dict(state='completed',items=[dict(id='wall-0001',start=dict(x=150,y=0),end=dict(x=150,y=200),
        evidence_refs=['region:region-0001'],ambiguity='ambiguous')])
    paths,notes=generate_draft_wiring(NS(payload=FloorPlanInterpretationPayload.model_validate(raw)))
    assert paths==[] and any('no permitted geometric path' in n for n in notes)
