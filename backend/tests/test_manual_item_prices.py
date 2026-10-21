from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select,func
from app.models import ItemPriceAssignment,MaterialPrice
from app.api.dependencies import get_current_user
from tests.test_automatic_client_pricing import item_schema,project_price_schema,source_schema,estimate_context
from tests.test_routing_api import context
from tests.synthetic_pricing import prepare


def request(version,key,price='15',**extra):
    return dict(request_id=str(uuid4()),expected_version=version,
        items=[dict(item_key=key,unit_price=price,currency='PHP')],**extra)


def test_manual_prices_persist_one_item_zero_and_totals_without_catalog_or_geometry_changes(context):
    prepare(context)
    client,_,_,session,layout,*_=context
    root=f'/api/projects/{layout.project_id}'
    options=client.get(root+'/client-pricing/item-assignments').json()
    row=next(r for r in options['items'] if r['kind']=='device')
    prices=[r.unit_price for r in session.scalars(select(MaterialPrice))]
    geometry=deepcopy(layout.geometry_document)
    payload=request(options['assignment_version'],row['item_key'])
    url=root+'/client-pricing/item-assignments/prices'
    response=client.post(url,json=payload)
    assert response.status_code==200,response.text
    assert client.post(url,json=payload).json()==response.json()
    planning=client.get(root+'/bom').json()['planning']
    edited=[r for r in planning['items'] if r.get('price_source')=='manual_override']
    assert len(edited)==1 and Decimal(edited[0]['unit_price'])==15
    assert Decimal(planning['cost_summary']['currencies']['PHP']['devices'])==215
    assert planning['cost_summary']['incomplete']==(planning['unpriced_items']>0)
    assert client.get(root+'/bom').json()['planning']['cost_summary']==planning['cost_summary']
    assert [r.unit_price for r in session.scalars(select(MaterialPrice))]==prices
    assert layout.geometry_document==geometry
    zero=client.post(url,json=request(response.json()['version_number'],row['item_key'],'0'))
    assert zero.status_code==200,zero.text
    updated=client.get(root+'/bom').json()['planning']
    assert Decimal(next(r for r in updated['items'] if r.get('price_source')=='manual_override')['line_total'])==0


def test_manual_price_validation_stale_scope_retry_and_authorization(context):
    prepare(context)
    client,_,_,session,layout,app,other,admin=context
    root=f'/api/projects/{layout.project_id}/client-pricing/item-assignments'
    option=client.get(root).json()
    key=option['items'][0]['item_key']
    url=root+'/prices'
    for bad in ('-1','NaN','1000000001','0.123456789'):
        assert client.post(url,json=request(0,key,bad)).status_code==422
    assert client.post(url,json=request(0,'f'*64)).status_code==409
    payload=request(0,key)
    assert client.post(url,json=payload).status_code==200
    assert client.post(url,json=payload|{'items':[dict(item_key=key,unit_price='16',currency='PHP')]}).status_code==409
    assert client.post(url,json=request(0,key)).status_code==409
    app.dependency_overrides[get_current_user]=lambda:other
    assert client.post(url,json=request(1,key)).status_code==404
    app.dependency_overrides[get_current_user]=lambda:admin
    assert client.post(url,json=request(1,key)).status_code==403
    assert session.scalar(select(func.count()).select_from(ItemPriceAssignment))==1


def test_manual_price_captured_by_new_estimate_without_rewriting_old(estimate_context):
    ctx,payload,_=estimate_context
    client,_,_,session,layout,*_=ctx
    root=f'/api/projects/{layout.project_id}'
    old=client.post(root+'/estimates',json=payload)
    assert old.status_code==201,old.text
    options=client.get(root+'/client-pricing/item-assignments').json()
    key=next(r['item_key'] for r in options['items'] if r.get('material_kind')=='conduit')
    saved=client.post(root+'/client-pricing/item-assignments/prices',json=request(0,key,'17'))
    assert saved.status_code==200,saved.text
    new=client.post(root+'/estimates',json=payload|dict(request_id=str(uuid4())))
    assert new.status_code==201,new.text
    assert any(r['kind']=='manual_override' for r in new.json()['source']['price_sources'])
    assert any(Decimal(r['captured_unit_price'])==17 for r in new.json()['items'])
    assert client.get(root+f'/estimates/{old.json()["id"]}').json()==old.json()
