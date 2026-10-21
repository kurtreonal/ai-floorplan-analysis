"""Client-owned prices apply in one request without catalog registration or review."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from app.models import Material,MaterialPrice,ProjectPriceVersion,ItemPriceAssignment
from app.services.automatic_client_pricing import parse,compatible
from tests.test_item_pricing import item_schema
from tests.test_project_pricing import project_price_schema,source_schema,estimate_context
from tests.test_routing_api import context
from tests.synthetic_pricing import prepare


def client_file():
    return ('Code,Description,Unit,Unit price,Currency,Units per purchase,Quantity\n'
        'CLIENT-A,ClientBrand duplex outlet 16 A,piece,90,PHP,1,999\n'
        'CLIENT-B,ClientBrand switch 1 gang,piece,60,PHP,1,999\n'
        'CLIENT-C,ClientBrand THHN wire 3.5 mm2,roll,1200,PHP,100,999\n'
        'CLIENT-D,ClientBrand PVC conduit 20 mm,stock,75,PHP,3,999\n').encode()


def upload(client,root,data=None,request_id=None,name='client.csv',**extra):
    return client.post(root+'/client-pricing/automatic',
        files={'file':(name,client_file() if data is None else data,'application/octet-stream')},
        data=dict(request_id=str(request_id or uuid4()),**extra))


@pytest.mark.parametrize('file_format',['csv','xlsx'])
def test_upload_applies_off_catalog_products_without_review_and_reloads_exact_totals(context,file_format):
    import csv
    from tests.test_material_import import workbook
    prepare(context)
    client,_,_,session,layout,*_=context
    root=f'/api/projects/{layout.project_id}'
    # No active VED products at all; the import must stand on its own.
    for material in session.scalars(select(Material)):
        material.is_active=False
    session.commit()
    geometry=deepcopy(layout.geometry_document)
    catalog_prices=[p.unit_price for p in session.scalars(select(MaterialPrice))]
    before_materials=session.scalar(select(func.count()).select_from(Material))
    request_id=uuid4()
    data=client_file() if file_format=='csv' else workbook(list(csv.reader(client_file().decode().splitlines())))
    response=upload(client,root,data,request_id=request_id,name='client.'+file_format)
    assert response.status_code==200,response.text
    assert response.json()['applied']==7 and response.json()['skipped']==[]
    assert upload(client,root,data,request_id=request_id,name='client.'+file_format).json()==response.json()
    assert session.scalar(select(func.count()).select_from(ProjectPriceVersion))==1
    assert session.scalar(select(func.count()).select_from(ItemPriceAssignment))==1
    actual=client.get(root+'/bom').json()['planning']
    assert actual['unpriced_items']==0
    assert Decimal(actual['priced_subtotals']['PHP'])==980
    assert all(r['price_source']=='client_upload' and r['material_id'] is None for r in actual['items'])
    assert all('ClientBrand' in r['client_product_name'] for r in actual['items'])
    assert all(Decimal(r['quantity'])!=999 for r in actual['items'])
    assert client.get(root+'/bom').json()['planning']['items']==actual['items']
    exported=client.get(root+'/bom.csv')
    assert exported.status_code==200 and 'ClientBrand PVC conduit 20 mm' in exported.text
    assert layout.geometry_document==geometry
    assert session.scalar(select(func.count()).select_from(Material))==before_materials
    assert [p.unit_price for p in session.scalars(select(MaterialPrice))]==catalog_prices
    assert upload(client,root,client_file().replace(b',90,',b',91,'),request_id=request_id).status_code==409


def test_scope_access_and_ambiguous_products_are_not_silently_chosen(context):
    from app.api.dependencies import get_current_user
    prepare(context)
    client,_,_,session,layout,app,other,admin=context
    root=f'/api/projects/{layout.project_id}'
    data=client_file()+b'OTHER,OtherBrand THHN wire 3.5 mm2,meter,11,PHP,1,999\n'
    result=upload(client,root,data,floor_id=layout.project_floor_id)
    assert result.status_code==200,result.text
    assert result.json()['applied']==5  # devices + both conduit rows; no arbitrary cheapest wire.
    assert len(result.json()['skipped'])==2
    assert all('Multiple compatible' in row['reason'] for row in result.json()['skipped'])
    assert upload(client,root,floor_id=layout.project_floor_id+999999).status_code==404
    app.dependency_overrides[get_current_user]=lambda:other
    assert upload(client,root).status_code==404
    app.dependency_overrides[get_current_user]=lambda:admin
    assert upload(client,root).status_code==403


def test_duplicates_invalid_prices_and_missing_conversions_remain_explicit():
    data=client_file()+b'CLIENT-A,ClientBrand duplex outlet 16 A,piece,90,PHP,1,999\n'
    rows=parse(data,'client.csv')['rows']
    assert not rows[0]['excluded'] and rows[-1]['excluded']
    data=client_file()+b'CLIENT-A,ClientBrand duplex outlet 16 A,piece,85,PHP,1,999\n'
    rows=parse(data,'client.csv')['rows']
    assert rows[0]['excluded'] and rows[-1]['excluded']
    for broken in (client_file().replace(b',1200,',b',,').replace(b',100,999',b',,999'),
            client_file().replace(b',1200,',b',=100*12,').replace(b',100,999',b',,999')):
        assert parse(broken,'client.csv')['rows'][2]['excluded']
    assert parse(client_file().replace(b',100,999',b',1e-999999,999'),'client.csv')['rows'][2]['excluded']
    # Client quantities never drive our calculation; do not execute them or
    # reject otherwise literal unit prices merely because that reference is a formula.
    assert not any(row['excluded'] for row in parse(client_file().replace(b',999',b',=2*5'),'client.csv')['rows'])


@pytest.mark.parametrize('source,offered,expected',[
    ('Data outlet CAT6','Duplex power outlet',False),
    ('Data outlet CAT6','Client data outlet CAT5e',False),
    ('Data outlet CAT6','Client data outlet CAT6',True),
    ('Downlight 10 W','Client downlight 15 W',False),
    ('Downlight 10 W','Client downlight 10 W',True)])
def test_automatic_devices_retain_type_and_explicit_ratings(source,offered,expected):
    quote=parse(f'Description,Unit,Unit price,Currency\n{offered},piece,5,PHP\n'.encode(),'client.csv')['rows'][0]
    row=dict(kind='device',item_kind='device',class_id=1,name=source,unit='piece')
    assert compatible(row,quote) is expected


def test_known_specifications_and_missing_measurements_are_preserved(context):
    from app.services.automatic_client_pricing import apply_row
    wire=parse(client_file(),'client.csv')['rows'][2]
    row=dict(kind='path',item_kind='wire',name='THHN wire 2.0 mm2',material_kind='wire',unit='meter')
    assert not compatible(row,wire)
    row.update(name='THHN wire 3.5 mm2',unit='source pixel',quantity=100,pricing_state='scale_required',line_total=None)
    assert compatible(row,wire)
    apply_row(row,wire,dict(price_version_id=1),1)
    assert row['unit_price'] is None and row['line_total'] is None and row['unit']=='source pixel'
    assert Decimal(row['client_unit_price'])==12 and row['client_price_unit']=='meter'
    row.update(unit='meter',missing_vertical_inputs=['missing service elevation'],pricing_state='measurement_incomplete')
    apply_row(row,wire,dict(price_version_id=1),1)
    assert row['line_total'] is None and Decimal(row['unit_price'])==12
    row.update(electrical_assignment_required=True,pricing_state='electrical_assignment_required')
    assert compatible(row,wire)  # A price assignment is not a circuit assignment.
    apply_row(row,wire,dict(price_version_id=1),1)
    assert row['line_total'] is None


def test_failure_rolls_back_both_quote_and_assignments(context,monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.services import automatic_client_pricing as service
    prepare(context)
    client,_,_,session,layout,*_=context
    root=f'/api/projects/{layout.project_id}'
    def fail(*args,**kwargs):
        raise OperationalError('private SQL',{},Exception('private password'))
    monkeypatch.setattr(service.assignments,'append',fail)
    result=upload(client,root)
    assert result.status_code==503 and 'private' not in result.text
    assert session.scalar(select(func.count()).select_from(ProjectPriceVersion))==0
    assert session.scalar(select(func.count()).select_from(ItemPriceAssignment))==0


def test_history_is_immutable_and_final_estimate_captures_client_prices(estimate_context):
    ctx,payload,materials=estimate_context
    client,_,_,session,layout,*_=ctx
    root=f'/api/projects/{layout.project_id}'
    materials[1].name='PVC conduit 20 mm'
    materials[2].name='THHN wire 3.5 mm2'
    session.commit()
    old=client.post(root+'/estimates',json=payload)
    assert old.status_code==201,old.text
    # Reuse source types, but quote different client brand/codes and own prices.
    data=('Description,Unit,Unit price,Currency\n'
        'ClientBrand outlet,piece,5,PHP\nClientBrand wall light,piece,5,PHP\n'+''.join(
        f'ClientBrand {m.name},{m.unit},5,PHP\n' for m in materials[1:])).encode()
    imported=upload(client,root,data)
    assert imported.status_code==200,imported.text
    assert imported.json()['applied']>0
    newer=client.post(root+'/estimates',json=payload|{'request_id':str(uuid4())})
    assert newer.status_code==201,newer.text
    assert client.get(root+f'/estimates/{old.json()["id"]}').json()==old.json()
    priced=[item for item in newer.json()['items'] if item['material_name'].startswith('ClientBrand')]
    assert priced and all(Decimal(item['captured_unit_price'])==5 for item in priced)
