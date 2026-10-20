from copy import deepcopy
from uuid import uuid4
import json
from pathlib import Path
import pytest
from sqlalchemy.orm import Session
from app.geometry.device_mounting import resolved_mounting,connection_height
from app.geometry.observed_connections import observed_connection_routes
from app.geometry.route_measurement import measure_metric_network
from app.services.draft_bom_service import document_takeoff


@pytest.mark.parametrize('name,height',[('Convenience outlet',.3),('Wall switch',1.2)])
def test_ved_center_defaults_drop_height_and_terminal_offset(name,height):
    original=dict(id='symbol-0001',class_name=name,class_id=1,disposition='accepted')
    symbol=resolved_mounting(original)
    assert symbol['mounting_reference']=='device_center'
    assert connection_height(symbol)==height
    wire=dict(id='segment-0001',disposition='accepted',elevation_meters=3,points=[dict(x=0,y=0),dict(x=100,y=0)],
        device_attachments=[dict(symbol_id=symbol['id'],point_index=0)])
    source=dict(symbols=[symbol],observed_wiring=[wire])
    row=document_takeoff(source,scale=10,floor_elevation=0)[1]
    assert row['vertical_meters']==pytest.approx(3-height)
    assert float(row['quantity'])==pytest.approx(10+3-height)
    symbol['terminal_offset_meters']=.1
    offset=document_takeoff(source,scale=10,floor_elevation=0)[1]
    assert offset['vertical_meters']==pytest.approx(3-height-.1)
    routes,_,_=observed_connection_routes([wire],{symbol['id']:symbol},{symbol['id']:'manual:1'},floor_id=1,floor_elevation=0,scale=10,provenance='synthetic')
    edges=[dict(start=dict(floor_id=1,**{k:a[k] for k in ('x','y','elevation_meters')}),end=dict(floor_id=1,**{k:b[k] for k in ('x','y','elevation_meters')})) for r in routes for a,b in zip(r['points'],r['points'][1:])]
    assert measure_metric_network(edges).physical_meters==pytest.approx(float(offset['quantity']))
    assert original==dict(id='symbol-0001',class_name=name,class_id=1,disposition='accepted')


def test_existing_heights_and_references_are_not_silently_reinterpreted():
    for reference in (None,'box_bottom','connection_terminal','legacy_unspecified'):
        symbol=dict(class_name='Outlet',mounting_height_meters=.75,mounting_reference=reference)
        assert resolved_mounting(symbol)==symbol
    assert 'mounting_height_meters' not in resolved_mounting(dict(class_name='Data outlet'))
    assert 'mounting_height_meters' not in resolved_mounting(dict(class_name='Distribution panel'))
    assert 'mounting_height_meters' not in resolved_mounting(dict(class_name='Outlet',disposition='rejected'))


def test_shared_v7_reference_fixture_round_trips_and_rejects_inconsistent_offset():
    from app.geometry.canonical import canonical_geometry_from_dict,CanonicalGeometryError
    from app.geometry.canonical_extension import canonical_extension_from_dict
    root=Path(__file__).resolve().parents[2]/'fixtures'
    base=canonical_geometry_from_dict(json.loads((root/'canonical_geometry_v1.json').read_text()))
    document=json.loads((root/'canonical_extension_v7_mounting.json').read_text())
    assert canonical_extension_from_dict(document,base).to_dict()==document
    bad=deepcopy(document);bad['symbol_details'][0]['installation']['elevation_meters']+=.1
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(bad,base)
    bad=deepcopy(document);bad['extension_schema_version']=6
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(bad,base)


@pytest.mark.parametrize('override',[None,.8])
def test_default_reference_and_offset_survive_review_canonical_save_reload(override):
    import tests.test_demo_interpretation_api as fixtures
    from app.models import SymbolLegend
    fixture=fixtures.DemoInterpretationApiTests
    fixture.setUpClass()
    try:
        case=fixture();case.setUp();case._login()
        with Session(fixture.engine) as db:
            db.get(SymbolLegend,fixture.ids['legend']).name='Synthetic testing only convenience outlet'
            db.commit()
        payload=case._review_payload()
        symbol=payload['symbols'][0]
        if override is not None:symbol['mounting_height_meters']=override
        symbol['terminal_offset_meters']=.1
        anchor=deepcopy(symbol['center'])
        payload['observed_wiring']=[dict(id='manual-wiring-0001',disposition='added',completeness='complete',elevation_meters=3,
            points=[anchor,dict(x=anchor['x']+30,y=anchor['y'])],device_attachments=[dict(symbol_id=symbol['id'],point_index=0)])]
        root=f'/api/floor-plans/{fixture.ids["floor_plan"]}/interpretation'
        saved=fixture.client.post(root+'/reviews',json=payload)
        assert saved.status_code==201,saved.text
        reviewed=saved.json()['review']['symbols'][0]
        height=.3 if override is None else override
        reference='device_center' if override is None else 'legacy_unspecified'
        assert reviewed['mounting_height_meters']==height
        assert reviewed.get('mounting_reference')==('device_center' if override is None else None)
        assert fixture.client.get(root).json()['review']['symbols'][0]==reviewed
        layoutroot=f'/api/projects/{fixture.ids["project"]}/floors/{fixture.ids["floor"]}'
        canonical=fixture.client.post(layoutroot+f'/floor-plans/{fixture.ids["floor_plan"]}/interpretation/layout',json=dict(
            candidate_run_id=fixture.candidate.provenance.candidate_run_id,review_revision_number=1,expected_layout_version_number=None,idempotency_key=str(uuid4())))
        assert canonical.status_code==201,canonical.text
        result=canonical.json()
        assert result['extension']['extension_schema_version']==7
        installation=result['extension']['symbol_details'][0]['installation']
        assert installation==dict(elevation_meters=round(height+.1,9),wall_id=None,mounting_reference=reference,mounting_elevation_meters=height,terminal_offset_meters=.1)
        reloaded=fixture.client.get(layoutroot+'/layouts').json()
        assert reloaded['geometry']==result['geometry'] and reloaded['extension']==result['extension']
    finally:
        fixture.tearDownClass()
