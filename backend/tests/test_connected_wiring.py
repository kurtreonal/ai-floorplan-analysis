"""Explicit topology, compatibility and physical length; no image-specific rules."""
from copy import deepcopy
import json
import pytest
from app.geometry.wire_network import wire_networks, takeoff_path_groups
from app.geometry.path_lengths import unique_paths_length
from app.geometry.canonical_extension import canonical_extension_from_dict
from app.geometry.canonical import CanonicalGeometryError
from app.schemas.demo_interpretation import DemoObservedWiringReview
from tests.test_canonical_device_connection_contract import fixture
from tests.test_demo_interpretation_api import DemoInterpretationApiTests


def wire(identity, points, terminal=None, circuit=None):
    return dict(id=identity,disposition='added',completeness='partial',circuit_id=circuit,
        points=[dict(x=x,y=y) for x,y in points],device_attachments=[
            dict(symbol_id='symbol-0001',point_index=0,terminal_id=terminal)] if terminal else [])


def test_only_explicit_same_terminal_unifies_paths_not_device_bounds_crossings_or_circuits():
    a=wire('manual-wiring-0001',[(10,10),(40,10)],'A')
    b=wire('manual-wiring-0002',[(10,10),(10,40)],'A')
    c=wire('manual-wiring-0003',[(10,10),(0,10)],'B')
    d=wire('manual-wiring-0004',[(5,0),(5,20)])
    source=deepcopy([a,b,c,d])
    networks=wire_networks(source)
    assert networks[a['id']]==networks[b['id']]
    assert len(set(networks.values()))==3
    assert source==[a,b,c,d]
    b['circuit_id']='C2'
    with pytest.raises(ValueError): wire_networks([a,b])
    # No terminal identifier: legacy data remains separate, not upgraded by proximity.
    for w in [a,b]: w['device_attachments'][0].pop('terminal_id')
    assert len(set(wire_networks([a,b]).values()))==2


def test_unique_physical_length_split_overlap_parallel_and_conductor_metadata_preserved():
    a=wire('manual-wiring-0001',[(10,10),(50,10)],'A')
    b=wire('manual-wiring-0002',[(10,10),(30,10)],'A')
    a['conductor_count']=3; b['conductor_count']=5  # caller-owned assignment, never inferred
    document=dict(observed_wiring=[a,b])
    before=deepcopy(document)
    groups=takeoff_path_groups(document)
    assert len(groups)==1
    assert unique_paths_length([w['points'] for w in groups[0]])==40
    a['points'].insert(1,dict(x=20,y=10))
    assert unique_paths_length([w['points'] for w in takeoff_path_groups(document)[0]])==40
    assert [w['conductor_count'] for w in groups[0]]==[3,5]
    assert before['observed_wiring'][0]['conductor_count']==3
    parallel=wire('manual-wiring-0003',[(10,10.001),(50,10.001)])
    assert unique_paths_length([a['points'],parallel['points']])==80


def test_v6_terminal_vertex_lineage_roundtrip_and_old_version_rejects_new_fields():
    base,ext,legacy=fixture()
    ext['extension_schema_version']=6
    for row in ext['route_details']:
        row.update(circuit_id=None,junction_connections=[],vertex_ids=['a','b'],network_lineage=['segment-0001'])
        row['device_connections'][0]['terminal_id']='design-anchor'
    assert canonical_extension_from_dict(ext,base).to_dict()==ext
    assert canonical_extension_from_dict(legacy,base).to_dict()==legacy
    old=deepcopy(ext);old['extension_schema_version']=5
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(old,base)
    broken=deepcopy(ext);broken['route_details'][0]['vertex_ids']=['one']
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(broken,base)


def test_loop_references_and_history_are_serializable_without_guessed_scale_or_assignment():
    value=wire('manual-wiring-0001',[(0,0),(10,0),(10,10),(0,0)])
    value['vertex_ids']=['a','b','c','a']
    doc=DemoObservedWiringReview.model_validate(value).model_dump(mode='json')
    assert DemoObservedWiringReview.model_validate_json(json.dumps(doc)).model_dump(mode='json')==doc
    assert 'circuit_id' not in doc and doc['elevation_meters'] is None
    value['points'][-1]['x']=1
    with pytest.raises(ValueError):DemoObservedWiringReview.model_validate(value)


def test_canonical_terminal_rejects_conflicting_circuit_references():
    from app.geometry.canonical import canonical_geometry_from_dict
    base,ext,_=fixture()
    raw=base.to_dict()
    extra=deepcopy(raw['routes'][0]);extra['id']=max(r['id'] for r in raw['routes'])+1
    raw['routes'].append(extra)
    base=canonical_geometry_from_dict(raw)
    ext['extension_schema_version']=6
    for row in ext['route_details']:
        row.update(circuit_id=None,junction_connections=[])
        for contact in row['device_connections']:contact['terminal_id']='A'
    other=deepcopy(ext['route_details'][0]);other.update(route_id=extra['id'],circuit_id='different')
    ext['route_details'].append(other)
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(ext,base)


def test_manual_provenance_alone_emits_complete_v6_connection_fields():
    from app.geometry.observed_connections import observed_connection_routes
    value=wire('manual-wiring-0001',[(0,0),(10,0)])
    value.update(path_origin='manual',elevation_meters=2.8)
    routes,details,version4=observed_connection_routes([value],{}, {},floor_id=1,
        floor_elevation=0,scale=10,provenance='review:test')
    assert version4 and len(routes)==1
    assert details[0]['route_kind']=='manual' and details[0]['circuit_id'] is None
    assert details[0]['device_connections']==[] and details[0]['junction_connections']==[]


def test_manual_continuation_does_not_double_count_an_explicitly_shared_canonical_span():
    from app.geometry.canonical import canonical_geometry_from_dict
    from app.geometry.canonical_takeoff import canonical_path_rows
    from tests.test_canonical_junction_contract import fixture as junction_fixture
    base,ext=junction_fixture()
    raw=base.to_dict()
    raw['routes'][1]['points'][1]=deepcopy(raw['routes'][0]['points'][0])
    base=canonical_geometry_from_dict(raw)
    ext['extension_schema_version']=6
    ext['route_details'][1]['route_kind']='manual'
    rows=canonical_path_rows(base,canonical_extension_from_dict(ext,base))
    assert len(rows)==1 and rows[0]['quantity']==1
    assert rows[0]['provenance_origins']==['manual','observed']
    assert rows[0]['path_ids']==[1,2]


class ConnectedWiringApiTests(DemoInterpretationApiTests):
    def test_network_v6_survives_review_reload_and_canonical_publication(self):
        from uuid import uuid4
        self._login()
        url=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        payload=self._review_payload(complete=False,approved=False)
        a=wire('manual-wiring-0001',[(20,30),(80,30)])
        b=wire('manual-wiring-0002',[(80,30),(80,90)])
        for w,index in [(a,1),(b,0)]:
            w['path_origin']='manual'
            w['junction_attachments']=[dict(junction_id='junction-0001',point_index=index)]
            w['vertex_ids']=[w['id']+':a',w['id']+':b']
            w['network_lineage']=[a['id'],b['id']]
        payload['observed_wiring']=[a,b]
        response=self.client.post(url+'/reviews',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        saved=response.json()['review']['observed_wiring']
        self.assertEqual(self.client.get(url).json()['review']['observed_wiring'],saved)
        self.assertEqual(len(set(wire_networks(saved).values())),1)
        before=unique_paths_length([w['points'] for w in saved])
        payload.update(expected_revision_number=1,review_complete=True,approved_for_layout=True,wall_height_meters=3,wall_thickness_meters=.15)
        for w in payload['observed_wiring']:w.update(disposition='accepted',completeness='complete',elevation_meters=2.8)
        response=self.client.post(url+'/reviews',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        target=f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
        published=self.client.post(target,json=dict(candidate_run_id=self.candidate.provenance.candidate_run_id,review_revision_number=2,
            expected_layout_version_number=None,idempotency_key=str(uuid4())))
        self.assertEqual(published.status_code,201,published.text)
        result=published.json()
        self.assertEqual(result['extension']['extension_schema_version'],6)
        self.assertTrue(all(row['vertex_ids'] for row in result['extension']['route_details']))
        self.assertTrue(all(row['route_kind']=='manual' for row in result['extension']['route_details']))
        self.assertEqual(before,120)
