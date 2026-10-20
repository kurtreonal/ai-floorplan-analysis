from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from app.api.dependencies import get_current_user
from app.models import MaterialPrice
from tests.test_estimates import estimate_context, source_schema
from tests.test_routing_api import context


def test_bom_without_route_is_reviewed_and_access_checked(context):
    client, _, _, _, layout, app, other, _ = context
    url = f'/api/projects/{layout.project_id}/bom'
    result = client.get(url)
    assert result.status_code == 200, result.text
    assert sum(row['quantity'] for row in result.json()['components']) == 2
    assert result.json()['route_lengths'] is None
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(url).status_code == 404
    app.dependency_overrides.pop(get_current_user)
    assert client.get(url).status_code == 401


def test_canonical_wiring_and_vertical_length_remain_visible_in_bom_and_csv(context):
    from copy import deepcopy
    client,_,_,session,layout,*_=context
    raw=deepcopy(layout.geometry_document)
    raw['routes']=[dict(id=7,points=[dict(project_floor_id=layout.project_floor_id,x=x,y=1,elevation_meters=z)
                                    for x,z in [(1,3),(3,3),(3,1.2)]])]
    layout.geometry_document=raw;session.commit()
    url=f'/api/projects/{layout.project_id}/bom'
    response=client.get(url)
    assert response.status_code==200,response.text
    paths=[row for row in response.json()['planning']['items'] if row['kind']=='path']
    assert len(paths)==2 and all(Decimal(row['quantity'])==Decimal('3.8') for row in paths)
    assert {row['material_kind'] for row in paths}=={'wire','conduit'}
    assert paths[0]['vertical_meters']==1.8 and paths[0]['origin']=='unresolved'
    assert paths[0]['line_total'] is None
    assert 'Saved canonical metric centerlines' in paths[0]['basis']
    csv=client.get(url+'.csv')
    assert csv.status_code==200 and '3.8000' in csv.text
    assert layout.geometry_document==raw
    inventory=client.get(f'/api/projects/{layout.project_id}/client-pricing/item-assignments')
    assert inventory.status_code==200,inventory.text
    keys=[row['item_key'] for row in inventory.json()['items']]
    assert len(keys)==len(set(keys))


def test_draft_calculator_rejects_invalid_choices_and_does_not_replace_saved_snapshot(estimate_context):
    context, request, materials = estimate_context
    client, _, _, session, layout, _, _, _ = context
    materials[1].category = 'CONDUIT - EMT'
    materials[1].name = 'EMT pipe 1/2 inch'
    session.commit()
    url=f'/api/projects/{layout.project_id}/bom'
    value=client.get(url).json()['planning']
    assert value['conduit_materials'][0]['id']==materials[1].id
    assert client.get(url,params={'paper_size':'A3'}).status_code==422
    assert client.get(url,params={'floor_plan_id':layout.floor_plan_id,'paper_size':'CUSTOM'}).status_code==422
    assert client.get(url,params={'conduit_material_id':materials[0].id}).status_code==422
    count=session.scalar(select(MaterialPrice.id).where(MaterialPrice.material_id==materials[1].id))
    chosen=client.get(url,params={'conduit_material_id':materials[1].id})
    assert chosen.status_code==200,chosen.text
    assert chosen.json()['planning']['selected_conduit_material_id']==materials[1].id
    assert session.scalar(select(MaterialPrice.id).where(MaterialPrice.material_id==materials[1].id))==count
    exported=client.get(url+'.csv',params={'conduit_material_id':materials[1].id})
    assert exported.status_code==200 and 'DRAFT CONDUIT CHOICE' in exported.text
    custom={'floor_plan_id':layout.floor_plan_id,'paper_size':'CUSTOM','custom_width_mm':300,'custom_height_mm':600}
    result=client.get(url,params=custom)
    assert result.status_code==200,result.text
    assert result.json()['planning']['custom_height_mm']==600
    assert 'CUSTOM' in client.get(url+'.csv',params=custom).text
    for bad in [{'custom_width_mm':0}, {'custom_height_mm':10001}, {'paper_size':'A3'}]:
        assert client.get(url,params={**custom,**bad}).status_code==422
    assert client.get(url,params={'wire_material_id':materials[0].id}).status_code==422
    custom_wire=client.get(url,params={'wire_price_per_meter':20})
    assert custom_wire.status_code==200,custom_wire.text
    assert custom_wire.json()['planning']['wire_price_per_meter']==20
    assert 'CUSTOM WIRE PRICE PER METRE' in client.get(url+'.csv',params={'wire_price_per_meter':20}).text
    for query in [{'wire_price_per_meter':-1},{'wire_meters_per_unit':0},{'wire_meters_per_unit':100}]:
        assert client.get(url,params=query).status_code==422


def test_purchase_units_extras_csv_and_historical_price(estimate_context):
    context, request, materials = estimate_context
    client, _, _, session, layout, app, other, _ = context
    materials[2].unit = 'roll'
    wire_price = session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[2].id))
    wire_price.unit = 'roll'
    session.commit()
    request.update(wire_meters_per_unit='3', additional_materials=[dict(material_id=materials[0].id, quantity='2')])
    url = f'/api/projects/{layout.project_id}/estimates'
    created = client.post(url, json=request)
    assert created.status_code == 201, created.text
    value = created.json()
    assert Decimal(value['total']) == 50
    assert Decimal(value['items'][3]['quantity']) == 2
    assert value['items'][3]['unit'] == 'roll'
    assert len(value['items']) == 5
    download = f'{url}/{value["id"]}/bom.csv'
    original = client.get(download)
    assert original.status_code == 200 and 'Captured unit price' in original.text and 'roll' in original.text
    wire_price.unit_price = 99
    session.commit()
    assert client.get(download).text == original.text
    # Automatic draft reuses saved specifications, but prices it from today's
    # database catalog. Historical estimates remain unchanged.
    draft = client.get(f'/api/projects/{layout.project_id}/bom').json()['planning']
    wire = next(r for r in draft['items'] if r.get('preferred_material_id') == materials[2].id)
    assert Decimal(wire['quantity']) == 2 and wire['unit'] == 'roll'
    assert Decimal(wire['line_total']) == 198
    assert 'Saved conductor count 3' in wire['basis']
    assert Decimal(draft['priced_subtotals']['PHP']) == 224
    invalid = {**request, 'request_id': str(uuid4()), 'conduit_meters_per_unit': '2'}
    assert client.post(url, json=invalid).status_code == 422
    # A new routing version must not inherit stale circuit purchase assumptions.
    route_url = f'/api/projects/{layout.project_id}/routes'
    newer = client.post(route_url, json=context[2])
    assert newer.status_code == 201, newer.text
    stale_draft = client.get(f'/api/projects/{layout.project_id}/bom').json()['planning']
    assert not any(r.get('preferred_material_id') == materials[2].id for r in stale_draft['items'])
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(download).status_code == 404
