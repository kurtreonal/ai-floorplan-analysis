from copy import deepcopy
from decimal import Decimal
from io import BytesIO
import json
from uuid import uuid4
from zipfile import ZipFile
import pytest
from sqlalchemy import func, select
from app.api.dependencies import get_current_user
from app.core.database import get_engine
from app.models import Material, MaterialPrice, ProjectPriceVersion
from app.services.client_workbook import read_cells
from app.services.material_workbook import WorkbookError
from tests.test_material_import import workbook
from tests.test_estimates import estimate_context, source_schema
from tests.test_routing_api import context


@pytest.fixture(autouse=True)
def project_price_schema():
    engine = get_engine()
    assert engine.url.database == 'ved_electrical_verify' and engine.url.username == 'ved_test'
    ProjectPriceVersion.__table__.create(engine, checkfirst=True)


def source_data(prices=('4', '2', '3'), quantity='9'):
    return workbook([['SKU', 'Description', 'Specification', 'Purchase unit', 'Quoted price', 'Currency', 'Client qty'],
        ['D1', 'Client lamp', 'Explicit device spec', 'piece', prices[0], 'PHP', quantity],
        ['C1', 'Client conduit', 'Explicit conduit spec', 'meter', prices[1], 'PHP', '20'],
        ['W1', 'Client cable', 'Explicit wire spec', 'roll', prices[2], 'PHP', '1']])


def selection(materials, kind='client_bom'):
    return dict(mapping=dict(kind=kind, sheet='Devices', header_row=1,
        columns=dict(code='A', name='B', specification='C', unit='D', unit_price='E', currency='F',
            **({'quantity':'G'} if kind == 'client_bom' else {}))),
        choices=[dict(row_id='Devices:'+str(index), material_id=material.id,
            **({'units_per_purchase':'10'} if index == 4 else {})) for index, material in enumerate(materials, 2)])


def upload(client, url, operation, data, payload=None, name='client.xlsx'):
    return client.post(url+'/'+operation, files={'file':(name, data, 'application/octet-stream')},
        data={'selection':json.dumps(payload)} if payload else {})


def save_import(client, project_id, data, payload):
    url=f'/api/projects/{project_id}/client-pricing'
    response=upload(client,url,'preview',data,payload)
    assert response.status_code==200,response.text
    preview=response.json()
    assert preview['ready'],preview
    request=payload|dict(request_id=str(uuid4()),file_sha256=preview['file_sha256'],
        preview_token=preview['preview_token'],expected_version=preview['expected_version'],confirmed=True)
    saved=upload(client,url,'apply',data,request)
    assert saved.status_code==200,saved.text
    return saved.json(),request


def test_unmapped_rows_are_reviewable_not_catalog_writes(estimate_context):
    ctx, _, materials=estimate_context
    client,_,_,session,layout,*_=ctx
    url=f'/api/projects/{layout.project_id}/client-pricing'
    before=session.scalar(select(func.count()).select_from(MaterialPrice))
    payload=selection(materials);payload['choices']=[]
    inspected=upload(client,url,'inspect',source_data())
    assert inspected.status_code==200 and inspected.json()['columns'][0]['label']=='SKU'
    response=upload(client,url,'preview',source_data(),payload)
    assert response.status_code==200,response.text
    result=response.json()
    assert not result['ready'] and len(result['document']['rows'])==3
    assert all(row['material_id'] is None and row['reasons'] for row in result['document']['rows'])
    assert session.scalar(select(func.count()).select_from(MaterialPrice))==before
    assert client.get(url).json()==[]


def test_version_source_retention_idempotency_stale_and_file_fences(estimate_context):
    ctx, _, materials=estimate_context
    client,_,_,session,layout,*_=ctx
    data=source_data()
    first,request=save_import(client,layout.project_id,data,selection(materials))
    url=f'/api/projects/{layout.project_id}/client-pricing'
    assert upload(client,url,'apply',data,request).json()==first
    assert session.get(ProjectPriceVersion,first['id']).source_bytes==data
    assert client.get(url+'/'+str(first['id'])).json()['document']['rows'][2]['units_per_purchase']=='10'
    changed=deepcopy(request);changed['request_id']=str(uuid4())
    assert upload(client,url,'apply',data,changed).status_code==409
    changed=deepcopy(request);changed['request_id']=str(uuid4())
    assert upload(client,url,'apply',source_data(('5','2','3')),changed).status_code==409
    assert len(client.get(url).json())==1


def test_project_prices_capture_real_purchase_units_and_client_quantity_is_not_used(estimate_context):
    ctx, payload, materials=estimate_context
    client,_,_,session,layout,*_=ctx
    old_prices=[price.unit_price for price in session.scalars(select(MaterialPrice))]
    version,_=save_import(client,layout.project_id,source_data(('4','2','30')),selection(materials))
    request=payload|dict(price_source='project',project_price_version_id=version['id'])
    saved=client.post(f'/api/projects/{layout.project_id}/estimates',json=request)
    assert saved.status_code==201,saved.text
    result=saved.json()
    # Two reviewed devices, 2 m conduit, 6 m conductor wire / 10 m quoted roll.
    assert [Decimal(row['quantity']) for row in result['items']]==[1,1,2,Decimal('.6')]
    assert Decimal(result['total'])==30
    assert result['items'][-1]['unit']=='roll'
    assert result['source']['project_pricing']['file_sha256']==version['file_sha256']
    assert result['source']['price_source']=='project'
    assert [price.unit_price for price in session.scalars(select(MaterialPrice))]==old_prices
    comparison=client.get(f"/api/projects/{layout.project_id}/client-pricing/{version['id']}?estimate_id={result['id']}")
    assert comparison.status_code==200,comparison.text
    row=comparison.json()['comparison'][0]
    assert Decimal(row['client_quantity'])==9 and Decimal(row['calculated_quantity'])==2
    assert Decimal(row['difference'])==-7
    newer,_=save_import(client,layout.project_id,source_data(('40','20','300')),selection(materials))
    assert newer['version_number']==2
    loaded=client.get(f"/api/projects/{layout.project_id}/estimates/{result['id']}")
    assert loaded.status_code==200,loaded.text
    assert loaded.json()==result
    assert client.post(f'/api/projects/{layout.project_id}/estimates',json=request).json()==result


def test_scope_roles_unpriced_material_and_no_implicit_catalog_fallback(estimate_context):
    ctx,payload,materials=estimate_context
    client,_,_,session,layout,app,other,admin=ctx
    owner=app.dependency_overrides[get_current_user]()
    data=source_data()
    limited=selection(materials)
    limited['choices'][2]={'row_id':'Devices:4','excluded':True}
    version,_=save_import(client,layout.project_id,data,limited)
    url=f'/api/projects/{layout.project_id}/client-pricing'
    response=client.post(f'/api/projects/{layout.project_id}/estimates',
        json=payload|dict(price_source='project',project_price_version_id=version['id']))
    assert response.status_code==422 and response.json()['detail']['error']['code']=='MISSING_PROJECT_MATERIAL_PRICE'
    app.dependency_overrides[get_current_user]=lambda:other
    assert client.get(url).status_code==404
    assert client.get(url+'/'+str(version['id'])).status_code==404
    assert upload(client,url,'preview',data,selection(materials)).status_code==404
    app.dependency_overrides[get_current_user]=lambda:admin
    assert client.get(url).status_code==200
    assert upload(client,url,'preview',data,selection(materials)).status_code==403
    app.dependency_overrides[get_current_user]=lambda:owner
    assert client.get(url+'/999999999').status_code==404


@pytest.mark.parametrize('change', ['missing','formula','duplicate','conversion','currency'])
def test_unresolved_rows_require_explicit_resolution_or_exclusion(estimate_context,change):
    ctx,_,materials=estimate_context
    client,_,_,_,layout,*_=ctx
    data=source_data();payload=selection(materials)
    if change=='missing':data=source_data(('', '2','3'))
    if change=='formula':data=source_data(('=SUM(1,2)','2','3'))
    if change=='duplicate':payload['choices'][1]['material_id']=materials[0].id
    if change=='conversion':payload['choices'][2].pop('units_per_purchase')
    if change=='currency':
        data=workbook([['Name','Unit','Price','Currency','Qty'],['Lamp','piece','1','','3']])
        payload=dict(mapping=dict(kind='client_bom',sheet='Devices',columns=dict(name='A',unit='B',unit_price='C',currency='D',quantity='E')),
            choices=[dict(row_id='Devices:2',material_id=materials[0].id)])
    url=f'/api/projects/{layout.project_id}/client-pricing'
    preview=upload(client,url,'preview',data,payload).json()
    assert not preview['ready']
    assert any(row['reasons'] for row in preview['document']['rows'] if not row['excluded'])
    request=payload|dict(request_id=str(uuid4()),file_sha256=preview['file_sha256'],
        preview_token=preview['preview_token'],expected_version=0,confirmed=True)
    assert upload(client,url,'apply',data,request).status_code==422


def test_zero_prices_csv_security_and_no_quantities_for_price_lists(estimate_context):
    ctx,_,materials=estimate_context
    client,_,_,_,layout,*_=ctx
    url=f'/api/projects/{layout.project_id}/client-pricing'
    data=b'Code,Name,Unit,Unit price\r\nX,Free lamp,piece,0\r\n'
    payload=dict(mapping=dict(kind='price_list',sheet='CSV',currency='PHP',columns=dict(code='A',name='B',unit='C',unit_price='D')),
        choices=[dict(row_id='CSV:2',material_id=materials[0].id)])
    preview=upload(client,url,'preview',data,payload,'client.csv').json()
    assert preview['ready'] and preview['document']['rows'][0]['unit_price']=='0'
    assert preview['document']['rows'][0]['client_quantity'] is None
    assert upload(client,url,'preview',b'garbage',payload).status_code==422
    with pytest.raises(WorkbookError):read_cells(data,'source.xlsm')
    stream=BytesIO()
    with ZipFile(stream,'w') as archive:archive.writestr('xl/vbaProject.bin',b'macro')
    with pytest.raises(WorkbookError):read_cells(stream.getvalue(),'source.xlsx')


def test_catalog_change_invalidates_preview_and_rollback_does_not_save_partial_version(estimate_context):
    ctx,_,materials=estimate_context
    client,_,_,session,layout,*_=ctx
    url=f'/api/projects/{layout.project_id}/client-pricing'
    data=source_data();payload=selection(materials)
    preview=upload(client,url,'preview',data,payload).json()
    materials[0].unit='pack';session.commit()
    request=payload|dict(request_id=str(uuid4()),file_sha256=preview['file_sha256'],
        preview_token=preview['preview_token'],expected_version=0,confirmed=True)
    assert upload(client,url,'apply',data,request).status_code==409
    assert client.get(url).json()==[]


def test_formula_cached_values_external_links_and_xml_entities_are_never_used():
    import re
    original=source_data()
    for kind in ('formula','external','entity'):
        source=BytesIO()
        with ZipFile(BytesIO(original)) as archive, ZipFile(source,'w') as output:
            for name in archive.namelist():
                value=archive.read(name)
                if kind=='formula' and name.endswith('sheet1.xml'):
                    value=re.sub(rb'<c r="E2".*?</c>',b'<c r="E2"><f>1+1</f><v>2</v></c>',value)
                if kind=='entity' and name.endswith('sheet1.xml'):
                    value=b'<!DOCTYPE x [<!ENTITY a "not accepted">]>'+value
                output.writestr(name,value)
            if kind=='external':output.writestr('xl/externalLinks/externalLink1.xml',b'<external/>')
        if kind=='formula':
            assert read_cells(source.getvalue(),'cached.xlsx')['Devices'][1]['formulas']==['E']
        else:
            with pytest.raises(WorkbookError):read_cells(source.getvalue(),'cached.xlsx')


def test_invalid_selection_inputs_and_explicit_price_source_contract():
    from app.schemas.project_pricing import PreviewRequest
    from app.schemas.estimate import EstimateWrite
    from pydantic import ValidationError
    base=dict(mapping=dict(kind='price_list',sheet='CSV',currency='PHP',columns=dict(name='A',unit='B',unit_price='C')))
    for conversion in ('0','-1','NaN','Infinity','1.12345'):
        with pytest.raises(ValidationError):
            PreviewRequest.model_validate(base|dict(choices=[dict(row_id='CSV:2',material_id=1,units_per_purchase=conversion)]))
    duplicate=deepcopy(base);duplicate['mapping']['columns']['unit_price']='A'
    with pytest.raises(ValidationError):PreviewRequest.model_validate(duplicate)
    request=dict(request_id=str(uuid4()),route_version_id=1,components=[],conduit_material_id=1,
        wire_material_id=2,conductor_count=3,mappings_confirmed=True)
    for extra in (dict(price_source='project'),dict(price_source='catalog',project_price_version_id=1)):
        with pytest.raises(ValidationError):EstimateWrite.model_validate(request|extra)


def test_simultaneous_identical_imports_return_one_version(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from app.models import Project, Role, User
    from app.schemas.project_pricing import ApplyRequest, PreviewRequest
    from app.services import project_pricing_service as service
    from app.repositories import project_pricing_repository as repository
    engine=get_engine();marker=uuid4().hex
    with Session(engine,expire_on_commit=False) as session:
        role=session.scalar(select(Role).where(Role.name=='DESIGNER'))
        user=User(oauth_provider='client-pricing-concurrency',oauth_subject=marker,role=role)
        project=Project(owner=user,name='Temporary client import concurrency fixture')
        material=Material(code=marker,name='Temporary fixture',unit='piece',category='Test')
        session.add_all([project,material]);session.commit()
        ids=(user.id,project.id,material.id)
    data=b'Description,Unit,Price\nFixture,piece,1\n'
    selection=dict(mapping=dict(kind='price_list',sheet='CSV',currency='PHP',columns=dict(name='A',unit='B',unit_price='C')),
        choices=[dict(row_id='CSV:2',material_id=ids[2])])
    try:
        with Session(engine) as session:
            value=service.preview(session,user,ids[1],data,'client.csv',PreviewRequest.model_validate(selection))
        request=ApplyRequest.model_validate(selection|dict(request_id=str(uuid4()),file_sha256=value['file_sha256'],
            preview_token=value['preview_token'],expected_version=0,confirmed=True))
        barrier=Barrier(2);real_lock=repository.lock_project
        def lock(session, project_id):
            barrier.wait(timeout=10)
            return real_lock(session,project_id)
        monkeypatch.setattr(repository,'lock_project',lock)
        def run():
            with Session(engine,expire_on_commit=False) as session:
                return service.apply(session,user,ids[1],data,'client.csv',request).id
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run(),range(2)))
        assert results[0]==results[1]
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(ProjectPriceVersion).where(ProjectPriceVersion.project_id==ids[1]))==1
    finally:
        with Session(engine) as session:
            session.execute(delete(ProjectPriceVersion).where(ProjectPriceVersion.project_id==ids[1]))
            session.execute(delete(Project).where(Project.id==ids[1]))
            session.execute(delete(Material).where(Material.id==ids[2]))
            session.execute(delete(User).where(User.id==ids[0]));session.commit()
