"""Integrated existing-item pricing; all records are isolated verification fixtures."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models import ItemPriceAssignment, MaterialPrice
from app.services.product_compatibility import compatible_product
from tests.test_item_pricing import item_schema, commit
from tests.test_project_pricing import estimate_context, source_schema, project_price_schema, automatic_data, upload
from tests.test_routing_api import context
from pathlib import Path


def selection_import(client, root, data):
    response=client.post(root+'/client-pricing/preview',files={'file':('client.xlsx',data)},data={'usage':'item_selection'})
    assert response.status_code==200,response.text
    p=response.json()
    assert p['ready'],p
    request=dict(usage='item_selection',mapping=p['document']['mapping'],
        choices=[{k:r[k] for k in ('row_id','material_id','units_per_purchase','excluded')} for r in p['document']['rows']],
        request_id=str(uuid4()),confirmed=True,file_sha256=p['file_sha256'],preview_token=p['preview_token'],expected_version=p['expected_version'])
    saved=upload(client,root+'/client-pricing','apply',data,request)
    assert saved.status_code==200,saved.text
    assert saved.json()['usage']=='item_selection'
    return saved.json()


def test_import_is_not_a_future_default_and_batch_application_is_atomic_persistent(estimate_context):
    ctx,payload,materials=estimate_context
    client,_,_,session,layout,*_=ctx
    root=f'/api/projects/{layout.project_id}'
    old=client.post(root+'/estimates',json=payload).json()
    catalog=[p.unit_price for p in session.scalars(select(MaterialPrice))]
    before=deepcopy(layout.geometry_document)
    base=client.get(root+'/bom').json()['planning']['priced_subtotals']
    version=selection_import(client,root,automatic_data(materials))
    assert client.get(root+'/bom').json()['planning']['priced_subtotals']==base
    url=root+'/client-pricing/item-assignments'
    items=client.get(url,params={'price_version_id':version['id']}).json()['items']
    bindings=[dict(item_key=r['item_key'],price_row_id='Devices:'+str(materials.index(next(m for m in materials if m.id==r['material_id']))+2),material_id=r['material_id'])
        for r in items if r.get('material_id')]
    proposal=dict(price_version_id=version['id'],scope='project',mode='selected',bindings=bindings)
    preview,saved,request=commit(client,url,proposal)
    assert len({r['price_row_id'] for r in preview['affected']})==3
    assert session.scalar(select(func.count()).select_from(ItemPriceAssignment))==1
    assert client.post(url+'/apply',json=request).json()==saved
    actual={r['item_key']:r for r in client.get(url).json()['items']}
    for row in preview['affected']:
        assert Decimal(actual[row['item_key']]['unit_price'])==Decimal(row['unit_price'])
        if row['line_total'] is not None:
            assert Decimal(actual[row['item_key']]['line_total'])==Decimal(row['line_total'])
    assert client.get(root+f'/estimates/{old["id"]}').json()==old
    assert [p.unit_price for p in session.scalars(select(MaterialPrice))]==catalog
    assert layout.geometry_document==before


def test_item_only_import_keeps_previous_project_default(estimate_context):
    from tests.test_project_pricing import automatic_request
    ctx,_,materials=estimate_context
    client=ctx[0];root=f'/api/projects/{ctx[4].project_id}'
    data=automatic_data(materials)
    p=upload(client,root+'/client-pricing','preview',data).json()
    assert upload(client,root+'/client-pricing','apply',data,automatic_request(p)).status_code==200
    before=client.get(root+'/bom').json()['planning']['priced_subtotals']
    selection_import(client,root,automatic_data(materials,change=lambda rows:[r.__setitem__(3,'99') for r in rows[1:]]))
    assert client.get(root+'/bom').json()['planning']['priced_subtotals']==before


@pytest.mark.parametrize('name,unit,expected',[
    ('Other THHN wire 3.5 mm2','meter',True),('Other THHN wire 2.0 mm2','meter',False),
    ('Other PVC conduit 3.5 mm','meter',False),('THHN wire 3.5 mm2','roll',False),
    ('Cable without stated gauge','meter',False)])
def test_product_compatibility_preserves_known_specifications(name,unit,expected):
    row=dict(kind='path',material_kind='wire',name='THHN wire 3.5 mm2',unit='meter',material_id=None)
    assert compatible_product(row,dict(id=1,name=name,unit=unit,category='')) is expected


def test_product_compatibility_preserves_material_and_cable_core_count():
    row=dict(kind='path',material_kind='conduit',name='Wiring path',material_name='PVC conduit 20 mm',unit='meter',material_id=1)
    assert not compatible_product(row,dict(id=2,name='EMT conduit 20 mm',unit='meter',category='Conduit'))
    row.update(material_kind='wire',material_name='Cable 2C 2.5 mm2')
    assert not compatible_product(row,dict(id=2,name='Cable 3C 2.5 mm2',unit='meter',category='Cable'))


def test_item_import_rejects_manual_mapping_to_conflicting_gauge(estimate_context):
    ctx,_,materials=estimate_context
    material=materials[2];material.name='THHN wire 3.5 mm2';ctx[3].commit()
    data=f'Code,Description,Unit,Unit price,Currency\n{material.code},THHN wire 2.0 mm2,meter,12,PHP\n'.encode()
    response=ctx[0].post(f'/api/projects/{ctx[4].project_id}/client-pricing/preview',
        files={'file':('quote.csv',data)},data={'usage':'item_selection'})
    assert response.status_code==200,response.text
    assert not response.json()['ready']
    assert 'conflicts' in ' '.join(response.json()['document']['rows'][0]['reasons'])


def test_delivered_workbook_prices_exact_synthetic_devices_and_both_path_components(context):
    from tests.synthetic_pricing import prepare
    fixture,materials=prepare(context)
    client=context[0];root=f'/api/projects/{context[4].project_id}'
    data=(Path(__file__).resolve().parents[2]/'frontend/public/fixtures/ved-synthetic-pricing.xlsx').read_bytes()
    p=client.post(root+'/client-pricing/preview',files={'file':('synthetic.xlsx',data)},data={'usage':'item_selection'})
    assert p.status_code==200,p.text
    initial=p.json()
    assert not initial['ready']
    decisions=[{k:r[k] for k in ('row_id','material_id','units_per_purchase','excluded')} for r in initial['document']['rows']]
    for row in decisions:
        row['excluded']=row['material_id'] is None or int(row['row_id'].split(':')[-1]) in fixture['excluded_quote_rows']
    request=dict(usage='item_selection',mapping=initial['document']['mapping'],choices=decisions)
    checked=upload(client,root+'/client-pricing','preview',data,request).json()
    assert checked['ready'],checked
    saved=upload(client,root+'/client-pricing','apply',data,request|dict(request_id=str(uuid4()),confirmed=True,
        file_sha256=checked['file_sha256'],preview_token=checked['preview_token'],expected_version=checked['expected_version']))
    assert saved.status_code==200,saved.text
    version=saved.json()
    url=root+'/client-pricing/item-assignments'
    rows=client.get(url,params={'price_version_id':version['id']}).json()['items']
    assert len(rows)==7
    outlets=[r for r in rows if r['kind']=='device' and r['class_id']==7]
    assert all(Decimal(r['line_total'])==100 for r in outlets)
    source_rows={r['code']:r for r in checked['document']['rows'] if not r['excluded']}
    bindings=[]
    for row in rows:
        code=(materials[0].code if row['class_id']==7 else materials[1].code) if row['kind']=='device' else fixture['path_products'][row['path_id']][0 if row['material_kind']=='wire' else 1]
        quote=source_rows[code]
        assert quote['row_id'] in row['compatible_prices']
        bindings.append(dict(item_key=row['item_key'],price_row_id=quote['row_id'],material_id=quote['material_id']))
    preview,_,_=commit(client,url,dict(price_version_id=version['id'],scope='project',mode='selected',bindings=bindings))
    assert sum(Decimal(r['line_total']) for r in preview['affected'])==Decimal(fixture['expected']['priced_total_php'])
    actual=client.get(root+'/bom').json()['planning']
    assert actual['unpriced_items']==0
    assert Decimal(actual['priced_subtotals']['PHP'])==980
    assert sorted({Decimal(r['quantity']) for r in actual['items'] if r['kind']=='path'})==[6,14]
    assert all(Decimal(r['quantity'])!=999 for r in actual['items'])
    # A reload retains explicit product choices without changing source metric points.
    assert client.get(root+'/bom').json()['planning']['items']==actual['items']
