from copy import deepcopy
from types import SimpleNamespace as NS
import cv2
import numpy as np
import pytest
from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence
from app.ai.floor_plan_interpretation.candidate import FloorPlanInterpretationPayload
from app.routing.endpoint_connections import apply_source_contacts
from app.ai.floor_plan_interpretation.reviewed_reference import inherit_review_draft
from tests.test_automatic_wiring import example


def source(*,inline=False,adjacent=False,nearby=False,crossing=False):
    image,payload=example()
    value=payload.model_dump(mode='json')
    # Endpoints are outside the glyph by its mask padding, not at its centre.
    points=[dict(x=72,y=100),dict(x=248,y=100)]
    if inline:
        middle=deepcopy(value['symbols']['items'][0]);middle.update(id='symbol-0003',center=dict(x=160,y=100),
            bounds=dict(x=152,y=88,width=16,height=24))
        value['symbols']['items'].append(middle)
        cv2.rectangle(image,(152,88),(168,112),(0,0,0),2)
    if adjacent:
        other=deepcopy(value['symbols']['items'][0]);other.update(id='symbol-0003',center=dict(x=60,y=132),
            bounds=dict(x=52,y=120,width=16,height=24))
        value['symbols']['items'].append(other)
        cv2.rectangle(image,(52,120),(68,144),(0,0,0),2)
    if nearby:
        value['symbols']['items'][0]['center']['y']=116
        value['symbols']['items'][0]['bounds']['y']=104
    if crossing:
        cv2.line(image,(160,20),(160,180),(0,0,0),2)
    value['observed_routes']=dict(state='partial',segments=[dict(id='segment-0001',points=points,
        evidence_refs=['region:region-0001'],ambiguity='ambiguous',line_style='solid')],connections=[])
    value['document_state']='partial'
    return image,FloorPlanInterpretationPayload.model_validate(value)


def test_boundary_masked_glyph_direction_and_source_evidence_are_retained_not_approval():
    image,payload=source();before=payload.model_dump_json();pixels=image.copy()
    result=with_device_contact_evidence(payload,image)
    assert len(result.observed_routes.connections)==2
    assert all(c.evidence_kind=='symbol_occlusion' and c.ambiguity=='unambiguous' for c in result.observed_routes.connections)
    assert result.observed_routes.segments==payload.observed_routes.segments
    assert payload.model_dump_json()==before
    np.testing.assert_array_equal(image,pixels)
    assert with_device_contact_evidence(payload,image)==result


def test_inline_contact_is_proposed_and_applied_as_a_persisted_vertex():
    image,payload=source(inline=True)
    result=with_device_contact_evidence(payload,image)
    assert len(result.observed_routes.connections)==3
    assert next(c for c in result.observed_routes.connections if c.to_ref=='symbol:symbol-0003').evidence_kind=='inline_device'
    candidate=NS(payload=result,provenance=NS(candidate_run_id='a'*32,inference_parameters=[NS(
        name='wiring-evidence-version',value='raw-source-device-port-evidence-v7')]))
    document=dict(symbols=[dict(id=s.id,center=s.center.model_dump(),disposition='unresolved') for s in result.symbols.items],
        observed_wiring=[dict(id='segment-0001',disposition='unresolved',points=[p.model_dump() for p in payload.observed_routes.segments[0].points])])
    connected=apply_source_contacts(candidate,document)['observed_wiring'][0]
    assert connected['points']==[dict(x=60,y=100),dict(x=72,y=100),dict(x=155.2,y=100),
        dict(x=160,y=100),dict(x=164.8,y=100),dict(x=248,y=100),dict(x=260,y=100)]
    assert next(a for a in connected['device_attachments'] if a['symbol_id']=='symbol-0003')['point_index']==3
    assert all(a['provenance']=='source_supported_proposal' for a in connected['device_attachments'])
    assert len(document['observed_wiring'][0]['points'])==2
    candidate.provenance.source_sha256='a'*64
    # Pure untouched proposals are not frozen as human geometry on reanalysis.
    next_payload=result.model_copy(update={'observed_routes':result.observed_routes.model_copy(update={'connections':()})})
    next_candidate=NS(payload=next_payload,provenance=NS(source_sha256='a'*64))
    carried=inherit_review_draft(next_candidate,candidate,{**document,'observed_wiring':[connected]})
    assert all(not w.get('device_attachments') for w in carried['observed_wiring'])


@pytest.mark.parametrize('option',['adjacent','nearby','crossing'])
def test_no_nearest_neighbor_or_crossing_junction(option):
    image,payload=source(**{option:True});result=with_device_contact_evidence(payload,image)
    contacts=result.observed_routes.connections
    assert not any(c.to_ref=='symbol:symbol-0003' for c in contacts)
    if option=='nearby':assert not any(c.to_ref=='symbol:symbol-0001' for c in contacts)
    assert all(c.from_ref.startswith('segment:') and c.to_ref.startswith('symbol:') for c in contacts)


def test_overlapping_devices_are_ambiguous_and_missing_ink_is_not_a_lead():
    image,payload=source();value=payload.model_dump(mode='json')
    duplicate=deepcopy(value['symbols']['items'][0]);duplicate['id']='symbol-0003';value['symbols']['items'].append(duplicate)
    result=with_device_contact_evidence(FloorPlanInterpretationPayload.model_validate(value),image)
    assert all(c.ambiguity=='ambiguous' for c in result.observed_routes.connections if c.to_ref in ('symbol:symbol-0001','symbol:symbol-0003'))
    image[:,72:120]=255
    result=with_device_contact_evidence(payload,image)
    assert not any(c.to_ref=='symbol:symbol-0001' for c in result.observed_routes.connections)
