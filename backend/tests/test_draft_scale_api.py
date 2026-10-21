from hashlib import sha256
import json
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.models import FloorPlanInterpretationRun, PageScaleSetting, ProcessingArtifact


def test_a1_draft_scale_is_shared_by_editor_and_bom_without_review_approval():
    # Fresh isolated synthetic source. It is not an accuracy claim on a real plan.
    from tests.test_demo_interpretation_api import DemoInterpretationApiTests
    class Fixture(DemoInterpretationApiTests):
        pass
    Fixture.setUpClass()
    try:
        fixture=Fixture();fixture._login()
        with Session(Fixture.engine) as db:
            run=db.get(FloorPlanInterpretationRun,Fixture.ids['run'])
            raw=json.loads(run.candidate_json)
            raw['payload']['source_plane'].update(width_pixels=841,height_pixels=594)
            raw['provenance'].update(expected_width_pixels=841,expected_height_pixels=594)
            run.candidate_json=json.dumps(raw);run.candidate_sha256=sha256(run.candidate_json.encode()).hexdigest()
            artifact=db.get(ProcessingArtifact,Fixture.ids['artifact'])
            artifact.pixel_width=841;artifact.pixel_height=594
            db.execute(delete(PageScaleSetting).where(PageScaleSetting.floor_plan_page_id==Fixture.ids['page']))
            db.commit()
        url=f'/api/floor-plans/{Fixture.ids["floor_plan"]}/interpretation'
        body=fixture._review_payload(complete=False,approved=False)
        anchor=body['symbols'][0]['center']
        body['observed_wiring']=[dict(id='manual-wiring-0001',disposition='added',completeness='partial',
            points=[anchor,dict(x=anchor['x']+100,y=anchor['y'])],elevation_meters=None,
            device_attachments=[dict(symbol_id=body['symbols'][0]['id'],point_index=0)])]
        saved=Fixture.client.post(url+'/reviews',json=body)
        assert saved.status_code==201,saved.text
        assert not saved.json()['review']['approved_for_layout']
        first=Fixture.client.get(url).json()
        bom_url=f'/api/projects/{Fixture.ids["project"]}/bom?floor_plan_id={Fixture.ids["floor_plan"]}'
        bom=Fixture.client.get(bom_url)
        assert bom.status_code==200,bom.text
        planning=bom.json()['planning']
        source=planning['sources'][0]
        assert first['routing_context']['pixels_per_meter']==source['pixels_per_meter']==10
        assert first['routing_context']['scale_basis']==source['scale_basis']=='ved_paper_ratio_draft'
        paths=[r for r in planning['items'] if r['kind']=='path']
        assert len(paths)==2 and all(float(r['quantity'])==10 and r['unit']=='meter' for r in paths)
        assert all(r['missing_vertical_inputs'] and not r['scale_approved'] for r in paths)
        assert Fixture.client.get(bom_url).json()['planning']['items']==planning['items']
        assert Fixture.client.get(url).json()['review']==first['review']
        with Session(Fixture.engine) as db:
            assert db.query(PageScaleSetting).filter_by(floor_plan_page_id=Fixture.ids['page']).count()==0
    finally:
        Fixture.tearDownClass()
