from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.api.dependencies import get_current_user
from app.core.database import get_engine
from app.models import ItemPriceAssignment, LayoutVersion
from tests.test_project_pricing import estimate_context, source_schema, project_price_schema, automatic_data, automatic_request, upload
from tests.test_routing_api import context


@pytest.fixture(autouse=True)
def item_schema():
    engine = get_engine()
    assert engine.url.database == 'ved_electrical_verify' and engine.url.username == 'ved_test'
    ItemPriceAssignment.__table__.create(engine, checkfirst=True)


def setup(estimate_context):
    ctx, payload, materials = estimate_context
    client, _, _, _, layout, *_ = ctx
    root = f'/api/projects/{layout.project_id}'
    old = client.post(root + '/estimates', json=payload).json()
    versions = []
    for values in (('4','2','3'),('8','5','7')):
        data = automatic_data(materials, change=lambda rows: [row.__setitem__(3,value) for row,value in zip(rows[1:],values)])
        result = upload(client, root + '/client-pricing', 'preview', data).json()
        saved = upload(client, root + '/client-pricing', 'apply', data, automatic_request(result))
        assert saved.status_code == 200, saved.text
        versions.append(saved.json())
    url = root + '/client-pricing/item-assignments'
    return client, root, url, old, versions


def choice(version, keys, *, row='Devices:2', floor=None, mode='selected'):
    return dict(price_version_id=version['id'],price_row_id=row,scope='floor' if floor else 'project',floor_id=floor,
        mode=mode,item_keys=keys)


def commit(client, url, selection):
    preview = client.post(url + '/preview', json=selection)
    assert preview.status_code == 200, preview.text
    request = selection | dict(request_id=str(uuid4()), preview_token=preview.json()['preview_token'])
    saved = client.post(url + '/apply', json=request)
    assert saved.status_code == 200, saved.text
    return preview.json(), saved.json(), request


def test_selected_prices_are_atomic_shared_persistent_and_capture_only_new_estimates(estimate_context):
    ctx,payload,materials = estimate_context
    client,root,url,old,versions = setup(estimate_context)
    before = deepcopy(ctx[4].geometry_document)
    inventory = client.get(url)
    assert inventory.status_code == 200, inventory.text
    devices = [r for r in inventory.json()['items'] if r['item_kind'] == 'device']
    assert len(devices) == 2 and all(Decimal(r['unit_price']) == 8 for r in devices)
    proposal,saved,request = commit(client,url,choice(versions[0],[devices[0]['item_key']]))
    assert Decimal(proposal['affected'][0]['previous_price']) == 8
    assert Decimal(proposal['affected'][0]['unit_price']) == 4
    assert client.post(url + '/apply',json=request).json() == saved
    assert client.post(url + '/apply',json=request | dict(item_keys=[devices[1]['item_key']])).status_code == 409
    assert Decimal(client.get(root + '/bom').json()['planning']['priced_subtotals']['PHP']) == 64
    floor_view = client.get(root + '/bom',params={'floor_plan_id':ctx[4].floor_plan_id}).json()['planning']
    assert Decimal(floor_view['priced_subtotals']['PHP']) == 64
    assert Decimal(client.get(url).json()['items'][0]['unit_price']) in (4,8)
    estimate = client.post(root + '/estimates',json=payload | dict(request_id=str(uuid4())))
    assert estimate.status_code == 201, estimate.text
    assert Decimal(estimate.json()['total']) == 32
    assert any(r['kind'] == 'item_project' for r in estimate.json()['source']['price_sources'])
    assert client.get(root + f'/estimates/{old["id"]}').json() == old
    assert ctx[4].geometry_document == before
    assert ctx[3].scalar(select(func.count()).select_from(ItemPriceAssignment)) == 1


def test_all_wiring_preview_skips_other_products_and_is_floor_scoped(estimate_context):
    ctx,_,_ = estimate_context
    client,root,url,_,versions = setup(estimate_context)
    selection = choice(versions[0],[],row='Devices:4',floor=ctx[4].project_floor_id,mode='all_wiring')
    proposal,_,_ = commit(client,url,selection)
    assert len(proposal['affected']) == 1 and proposal['affected'][0]['item_kind'] == 'wire'
    assert len(proposal['skipped']) >= 2
    rows = client.get(root + '/bom').json()['planning']['items']
    assert next(Decimal(r['unit_price']) for r in rows if r.get('item_kind') == 'wire') == 3
    assert next(Decimal(r['unit_price']) for r in rows if r.get('item_kind') == 'conduit') == 5
    # The same source price never turns an unresolved canonical path into a wire.
    assert any(r['line_total'] is None for r in rows)


def test_new_items_do_not_inherit_existing_item_action_and_old_preview_is_rejected(estimate_context):
    ctx,_,_ = estimate_context
    client,root,url,_,versions = setup(estimate_context)
    devices = [r for r in client.get(url).json()['items'] if r['item_kind'] == 'device']
    selection = choice(versions[0],[r['item_key'] for r in devices])
    first = client.post(url + '/preview',json=selection).json()
    commit(client,url,selection)
    stale = client.post(url + '/apply',json=selection | dict(request_id=str(uuid4()),preview_token=first['preview_token']))
    assert stale.status_code == 409
    session,layout = ctx[3:5]
    geometry = deepcopy(layout.geometry_document)
    geometry['symbols'].append(dict(geometry['symbols'][1],id='manual:602',source_record_id=602))
    layout.is_current = None
    session.flush()
    session.add(LayoutVersion(project_id=layout.project_id,project_floor_id=layout.project_floor_id,floor_plan_id=layout.floor_plan_id,
        version_number=2,schema_version=1,is_current=True,geometry_document=geometry))
    session.commit()
    # A changed layout makes its old measured route/specification snapshot stale.
    # Re-establish the same explicit material configuration, not inferred rules.
    route_request = deepcopy(ctx[2])
    route_request['floors'][0]['expected_layout_version'] = 2
    route = client.post(root + '/routes',json=route_request)
    assert route.status_code == 201, route.text
    estimate = client.post(root + '/estimates',json=estimate_context[1] | dict(request_id=str(uuid4()),route_version_id=route.json()['id']))
    assert estimate.status_code == 201, estimate.text
    items = client.get(url).json()['items']
    assert next(r for r in items if r.get('symbol_ids') == ['manual:602'])['price_source'] != 'item_project'
    assert sum(r['price_source'] == 'item_project' for r in items) == 2


def test_permissions_scope_tampering_and_invalid_preview_leave_no_assignment(estimate_context):
    ctx,_,_ = estimate_context
    client,_,url,_,versions = setup(estimate_context)
    item = client.get(url).json()['items'][0]
    selection = choice(versions[0],[item['item_key']])
    assert client.post(url + '/apply',json=selection | dict(request_id=str(uuid4()),preview_token='a'*64)).status_code == 409
    assert ctx[3].scalar(select(func.count()).select_from(ItemPriceAssignment)) == 0
    assert client.post(url + '/preview',json=selection | dict(scope='floor',floor_id=999999)).status_code == 409
    app,other,admin = ctx[5:]
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(url).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.get(url).status_code == 403


def test_unit_and_material_changes_never_receive_an_incompatible_price(estimate_context):
    ctx,_,materials = estimate_context
    client,_,url,_,versions = setup(estimate_context)
    item = next(r for r in client.get(url).json()['items'] if r['kind'] == 'device')
    selection = choice(versions[0],[item['item_key']])
    commit(client,url,selection)
    materials[0].unit = 'pack'; ctx[3].commit()
    preview = client.post(url + '/preview',json=selection)
    assert preview.status_code == 200, preview.text
    assert not preview.json()['ready'] and preview.json()['skipped']
    assert all(r.get('price_source') != 'item_project' for r in client.get(url).json()['items'])


def test_new_candidate_identity_never_inherits_old_draft_symbol_or_path_price():
    from app.services.item_pricing_service import expand_items
    rows = [dict(kind='device',quantity=2,unit='piece',symbol_ids=['symbol-0001','symbol-0002'],floor_id=1,floor_plan_id=1,page_id=1,candidate_run_id='old'),
        dict(kind='path',quantity=2,unit='meter',path_ids=['segment-0001'],floor_id=1,floor_plan_id=1,page_id=1,candidate_run_id='old')]
    first = {r['item_key'] for r in expand_items(rows)}
    assert len(first) == 3
    fresh = {r['item_key'] for r in expand_items([dict(row,candidate_run_id='new') for row in rows])}
    assert not first.intersection(fresh)


def test_preview_and_apply_agree_when_the_latest_import_has_no_price(estimate_context):
    ctx,_,materials = estimate_context
    client,root,url,_,versions = setup(estimate_context)
    data = automatic_data(materials,change=lambda rows:rows.__setitem__(slice(1,-1),[]))
    result = upload(client,root+'/client-pricing','preview',data).json()
    assert upload(client,root+'/client-pricing','apply',data,automatic_request(result)).status_code == 200
    item = next(r for r in client.get(url).json()['items'] if r['kind'] == 'device')
    assert item['unit_price'] is None
    proposal,_,_ = commit(client,url,choice(versions[0],[item['item_key']]))
    assert proposal['affected'][0]['previous_total'] is None
    assert Decimal(proposal['affected'][0]['line_total']) == 4
    actual = next(r for r in client.get(url).json()['items'] if r['item_key'] == item['item_key'])
    assert Decimal(actual['line_total']) == 4
