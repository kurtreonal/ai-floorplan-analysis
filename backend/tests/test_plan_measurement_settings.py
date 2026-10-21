from io import BytesIO
from uuid import uuid4
import json
import pytest
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import select,func
from app.core.database import get_engine
from app.models import PlanMeasurementSetting,FloorElevationSetting,PageScaleSetting,FloorPlan
from app.schemas.plan_measurement import PlanMeasurementInput
from app.services.plan_measurement_service import source_metadata,effective
from tests.test_routing_api import context


@pytest.fixture(autouse=True)
def measurement_schema():
    engine=get_engine()
    assert engine.url.username=='ved_test' and engine.url.database=='ved_electrical_verify'
    PlanMeasurementSetting.__table__.create(engine,checkfirst=True)


def png():
    output=BytesIO();Image.new('RGB',(80,40),'white').save(output,format='PNG');return output.getvalue()


def test_pdf_pages_retain_real_paper_crop_rotation_and_do_not_calibrate():
    writer=PdfWriter()
    writer.add_blank_page(width=420*72/25.4,height=297*72/25.4).rotate(90)
    page=writer.add_blank_page(width=594*72/25.4,height=841*72/25.4)
    page.cropbox.upper_right=(100,200)
    data=BytesIO();writer.write(data)
    metadata=source_metadata(data.getvalue(),'application/pdf')
    result=effective(PlanMeasurementInput(),metadata)
    assert result['pages'][0]['paper_size']=='A3'
    assert result['pages'][0]['orientation']=='portrait'
    assert result['pages'][1]['paper_size']=='A1' and result['pages'][1]['cropped']
    assert all(not page['calibrated'] and page['scale_denominator']==100 for page in result['pages'])
    changed=effective(PlanMeasurementInput(paper_size='A4',orientation='landscape',scale_denominator=50),metadata)
    assert changed['pages'][0]['paper_basis']=='user_input' and changed['pages'][0]['scale_basis']=='nominal_input_not_calibration'
    assert metadata[0]['paper_size']=='A3'


def test_image_defaults_are_metadata_not_a_pixel_scale():
    result=effective(PlanMeasurementInput(),source_metadata(png(),'image/png'))
    assert result['pages'][0]['paper_size']=='A1'
    assert result['pages'][0]['orientation']=='landscape'
    assert result['pages'][0]['paper_basis']=='input_default'
    assert 'pixels_per_meter' not in result['settings']


def test_settings_revision_retry_authorization_and_approved_scale_are_preserved(context):
    client,_,_,session,layout,app,other,admin=context
    from app.api.dependencies import get_current_user
    url=f'/api/projects/{layout.project_id}/floor-plans/{layout.floor_plan_id}/measurement-settings'
    initial=client.get(url)
    assert initial.status_code==200,initial.text
    assert initial.json()['settings']['paper_size'] is None and initial.json()['settings']['scale_denominator']==100
    scale_count=session.scalar(select(func.count()).select_from(PageScaleSetting))
    request=dict(expected_revision=0,request_id=str(uuid4()),floor_elevation_meters=6,
        floor_to_ceiling_height_meters=3.2,service_elevation_meters=8.8,scale_denominator=50)
    saved=client.put(url,json=request)
    assert saved.status_code==200,saved.text
    assert saved.json()['revision']==1
    assert saved.json()['floor_elevation_meters']==6
    assert client.put(url,json=request).json()==saved.json()
    reloaded=client.get(url).json()
    assert reloaded['settings']==saved.json()['settings'] and reloaded['floor_elevation_meters']==6
    assert session.scalar(select(func.count()).select_from(PageScaleSetting))==scale_count
    assert session.scalar(select(func.count()).select_from(FloorElevationSetting))==1
    assert client.put(url,json=request|dict(request_id=str(uuid4()))).status_code==409
    assert client.put(url,json=request|dict(service_elevation_meters=7)).status_code==409
    for bad in (True,-1,'A9'):
        assert client.put(url,json=request|dict(scale_denominator=bad)).status_code==422
    app.dependency_overrides[get_current_user]=lambda:other
    assert client.get(url).status_code==404
    app.dependency_overrides[get_current_user]=lambda:admin
    assert client.put(url,json=request).status_code==403


def test_normal_upload_stores_metadata_atomically_without_changing_original_or_approving_scale(context,tmp_path):
    from app.services.floor_plan_upload import upload_floor_plan
    client,_,_,session,layout,app,*_=context
    from app.api.dependencies import get_current_user
    user=app.dependency_overrides[get_current_user]()
    content=png()
    uploaded=upload_floor_plan(session,current_user=user,project_id=layout.project_id,project_floor_id=layout.project_floor_id,
        filename='synthetic.png',declared_mime_type='image/png',content=content,upload_directory=tmp_path,max_file_size_bytes=100000,
        measurement_settings=PlanMeasurementInput(floor_to_ceiling_height_meters=3,service_elevation_meters=2.8))
    assert (tmp_path/uploaded.storage_path).read_bytes()==content
    row=session.scalar(select(PlanMeasurementSetting).where(PlanMeasurementSetting.floor_plan_id==uploaded.id))
    assert row.document['pages'][0]['paper_size']=='A1' and row.document['settings']['service_elevation_meters']==2.8
    assert not row.document['pages'][0]['calibrated']
    assert session.scalar(select(func.count()).select_from(PageScaleSetting))==0


def test_multipart_upload_rejects_invalid_settings_without_storing_and_reloads_valid_settings(context,tmp_path):
    client,_,_,session,layout,app,*_=context
    app.state.settings.upload_dir=tmp_path
    url=f'/api/projects/{layout.project_id}/floor-plans'
    files={'file':('synthetic.png',png(),'image/png')}
    data={'project_floor_id':str(layout.project_floor_id)}
    count=session.scalar(select(func.count()).select_from(FloorPlan))
    for invalid in ('not-json',json.dumps({'scale_denominator':True}),json.dumps({'paper_size':'A9'})):
        rejected=client.post(url,data=data|{'measurement_settings':invalid},files=files)
        assert rejected.status_code==422,rejected.text
        assert session.scalar(select(func.count()).select_from(FloorPlan))==count
        assert not list(tmp_path.rglob('*.png'))
    settings={'scale_denominator':75,'floor_to_ceiling_height_meters':3.2,'service_elevation_meters':2.8}
    result=client.post(url,data=data|{'measurement_settings':json.dumps(settings)},files=files)
    assert result.status_code==201,result.text
    plan=session.get(FloorPlan,result.json()['id'])
    assert (tmp_path/plan.storage_path).read_bytes()==png()
    reloaded=client.get(f'{url}/{plan.id}/measurement-settings')
    assert reloaded.status_code==200,reloaded.text
    assert reloaded.json()['settings']['scale_denominator']==75
    assert reloaded.json()['settings']['floor_to_ceiling_height_meters']==3.2
    assert reloaded.json()['settings']['service_elevation_meters']==2.8
    assert reloaded.json()['revision']==1


def test_metadata_failure_rolls_back_new_original_and_all_new_records_but_preserves_existing(context,tmp_path,monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.services import plan_measurement_service as measurements
    client,_,_,session,layout,app,*_=context
    app.state.settings.upload_dir=tmp_path
    existing=tmp_path/'originals'/'keep.png'
    existing.parent.mkdir();existing.write_bytes(png())
    count=session.scalar(select(func.count()).select_from(FloorPlan))
    def fail(*args,**kwargs):
        raise OperationalError('private SQL and path',{},Exception('private credentials'))
    monkeypatch.setattr(measurements.repository,'append',fail)
    result=client.post(f'/api/projects/{layout.project_id}/floor-plans',
        data={'project_floor_id':str(layout.project_floor_id),'measurement_settings':'{}'},
        files={'file':('synthetic.png',png(),'image/png')})
    assert result.status_code==503,result.text
    assert 'private' not in result.text and str(tmp_path) not in result.text
    assert session.scalar(select(func.count()).select_from(FloorPlan))==count
    assert list(existing.parent.iterdir())==[existing] and existing.read_bytes()==png()
    assert session.scalar(select(func.count()).select_from(PlanMeasurementSetting))==0
    assert session.scalar(select(func.count()).select_from(FloorElevationSetting))==0


def test_unavailable_settings_return_safe_error_while_legacy_upload_does_not_query_new_table(context,tmp_path,monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.services import plan_measurement_service as measurements
    client,_,_,session,layout,app,*_=context
    app.state.settings.upload_dir=tmp_path
    def fail(*args,**kwargs):
        raise OperationalError('private SQL',{},Exception('private credentials'))
    monkeypatch.setattr(measurements.repository,'current',fail)
    monkeypatch.setattr(measurements.repository,'append',fail)
    url=f'/api/projects/{layout.project_id}/floor-plans'
    unavailable=client.get(f'{url}/{layout.floor_plan_id}/measurement-settings')
    assert unavailable.status_code==503 and 'private' not in unavailable.text
    uploaded=client.post(url,data={'project_floor_id':str(layout.project_floor_id)},
        files={'file':('synthetic.png',png(),'image/png')})
    assert uploaded.status_code==201,uploaded.text
    assert session.get(FloorPlan,uploaded.json()['id']) is not None


def test_blank_upload_floor_input_preserves_existing_floor_datum_and_historical_plan_settings(context,tmp_path):
    from app.services.floor_plan_upload import upload_floor_plan
    from app.api.dependencies import get_current_user
    client,_,_,session,layout,app,*_=context
    user=app.dependency_overrides[get_current_user]()
    session.add(FloorElevationSetting(project_floor_id=layout.project_floor_id,elevation_meters=6,
        reviewed_by_user_id=user.id,evidence_notes='Reviewed project datum'))
    session.flush()
    uploaded=upload_floor_plan(session,current_user=user,project_id=layout.project_id,
        project_floor_id=layout.project_floor_id,filename='synthetic.png',declared_mime_type='image/png',
        content=png(),upload_directory=tmp_path,max_file_size_bytes=100000,measurement_settings=PlanMeasurementInput())
    url=f'/api/projects/{layout.project_id}/floor-plans/{uploaded.id}/measurement-settings'
    first=client.get(url).json()
    updated=client.put(url,json=first['settings']|dict(expected_revision=1,request_id=str(uuid4()),scale_denominator=25))
    assert updated.status_code==200,updated.text
    assert updated.json()['floor_elevation_meters']==6
    assert session.scalar(select(func.count()).select_from(FloorElevationSetting))==1
    rows=session.scalars(select(PlanMeasurementSetting).where(PlanMeasurementSetting.floor_plan_id==uploaded.id)
        .order_by(PlanMeasurementSetting.revision)).all()
    assert [row.document['settings']['scale_denominator'] for row in rows]==[100,25]


def test_repeatable_read_snapshot_cannot_replace_newer_revision_and_retry_sees_latest_commit():
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from app.models import User,Role,Project,ProjectFloor
    from app.repositories import plan_measurement_repository as repository
    from app.schemas.plan_measurement import PlanMeasurementWrite
    from app.services.plan_measurement_service import save,MeasurementSettingsError
    engine=get_engine()
    marker=uuid4().hex
    with Session(engine,expire_on_commit=False) as setup:
        role=setup.scalar(select(Role).where(Role.name=='DESIGNER'))
        user=User(oauth_provider='measurement-concurrency-test',oauth_subject=marker,role=role)
        project=Project(owner=user,name='Synthetic testing only')
        floor=ProjectFloor(project=project,name='Synthetic floor',sort_order=0)
        plan=FloorPlan(project_floor=floor,original_filename='synthetic.png',storage_path=f'originals/{marker}.png',
            mime_type='image/png',file_size=12,processing_status='uploaded')
        setup.add(plan);setup.commit()
        user_id,project_id,floor_id,plan_id=user.id,project.id,floor.id,plan.id
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with Session(connection,autoflush=False) as stale,Session(engine,autoflush=False) as fresh:
                stale_user=stale.get(User,user_id)
                fresh_user=fresh.get(User,user_id)
                assert repository.current(stale,plan_id) is None
                first=PlanMeasurementWrite(expected_revision=0,request_id=uuid4())
                assert save(fresh,fresh_user,project_id,plan_id,first)['revision']==1
                fresh.commit()
                with pytest.raises(MeasurementSettingsError) as caught:
                    save(stale,stale_user,project_id,plan_id,PlanMeasurementWrite(expected_revision=0,request_id=uuid4()))
                assert caught.value.status==409
                stale.rollback()
                assert repository.current(stale,plan_id).revision==1
                second=PlanMeasurementWrite(expected_revision=1,request_id=uuid4(),scale_denominator=50)
                assert save(fresh,fresh_user,project_id,plan_id,second)['revision']==2
                fresh.commit()
                assert save(stale,stale_user,project_id,plan_id,second)['revision']==2
                stale.rollback()
    finally:
        # Only committed fixture rows owned by the IDs allocated above; never
        # delete by broad table, filename or a shared account predicate.
        with Session(engine) as cleanup:
            cleanup.execute(delete(PlanMeasurementSetting).where(PlanMeasurementSetting.floor_plan_id==plan_id))
            cleanup.execute(delete(FloorPlan).where(FloorPlan.id==plan_id))
            cleanup.execute(delete(ProjectFloor).where(ProjectFloor.id==floor_id))
            cleanup.execute(delete(Project).where(Project.id==project_id))
            cleanup.execute(delete(User).where(User.id==user_id))
            cleanup.commit()
