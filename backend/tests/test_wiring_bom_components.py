from copy import deepcopy
from decimal import Decimal
from app.services.draft_bom_service import document_takeoff, price_rows, apply_wire_choice, apply_conduit_choice
from app.services.wiring_bom_components import paired_wiring_components
from app.services.item_pricing_service import expand_items


def source():
    return dict(symbols=[dict(id='s',class_id=1,class_name='Outlet',mounting_height_meters=.45)],
        observed_wiring=[dict(id='w',points=[dict(x=0,y=0),dict(x=100,y=0)],
            elevation_meters=3,device_attachments=[dict(symbol_id='s',point_index=0)])])


def materials():
    return [dict(id=1,name='THHN wire 3.5 mm2',category='Wire',unit='meter',unit_price=Decimal(10),currency='PHP',price_revision_id=1),
        dict(id=2,name='Conduit PVC pipe 20 mm',category='Conduit',unit='meter',unit_price=Decimal(5),currency='PHP',price_revision_id=2)]


def test_every_path_has_two_distinct_components_with_the_same_measured_drop():
    document=source(); original=deepcopy(document)
    rows=paired_wiring_components(document_takeoff(document,scale=10,floor_elevation=0),materials())
    paths=[r for r in rows if r['kind']=='path']
    assert {r['material_kind'] for r in paths}=={'wire','conduit'}
    assert all(r['quantity']==Decimal('12.55') and r['vertical_meters']==2.55 for r in paths)
    assert all(r['path_ids']==['w'] for r in paths)
    keys=[r['item_key'] for r in expand_items(paths)]
    assert len(set(keys))==2
    assert paired_wiring_components(rows,materials())==rows
    assert document==original


def test_explicit_products_price_both_components_once_without_cross_applying_prices():
    rows=paired_wiring_components(document_takeoff(source(),scale=10,floor_elevation=0),materials())
    apply_conduit_choice(rows,materials(),2)
    apply_wire_choice(rows,materials(),1)
    paths=[r for r in price_rows(rows,materials())['items'] if r['kind']=='path']
    assert len(paths)==2
    assert {r['material_kind']:r['line_total'] for r in paths}=={'conduit':Decimal('62.75'),'wire':Decimal('125.50')}


def test_connected_but_unmeasured_keeps_exact_product_identity_without_making_up_costs():
    document=source(); document['symbols'][0].pop('mounting_height_meters')
    document['symbols'][0]['class_name']='Fixture without mounting data'
    rows=paired_wiring_components(document_takeoff(document,scale=10,floor_elevation=0),materials())
    apply_conduit_choice(rows,materials(),2); apply_wire_choice(rows,materials(),1)
    paths=[r for r in price_rows(rows,materials())['items'] if r['kind']=='path']
    assert {r['material_id'] for r in paths}=={1,2}
    assert all(r['pricing_state']=='partial_measurement_priced' and r['line_total']==Decimal(str(r['quantity']))*r['unit_price'] for r in paths)
    assert all(r['missing_vertical_inputs']==['s: save device mounting height for the connected drop/rise'] for r in paths)


def test_a_detected_wire_product_does_not_become_the_conduit_product_or_invent_a_gauge():
    document=source(); document['observed_wiring'][0]['wiring_legend_name']='THHN wire 3.5 mm2'
    rows=paired_wiring_components(document_takeoff(document,scale=10,floor_elevation=0),materials())
    paths=[r for r in price_rows(rows,materials())['items'] if r['kind']=='path']
    wire=next(r for r in paths if r['material_kind']=='wire')
    conduit=next(r for r in paths if r['material_kind']=='conduit')
    assert wire['material_id']==1 and conduit['material_id'] is None
    document['observed_wiring'][0].pop('wiring_legend_name')
    unknown=paired_wiring_components(document_takeoff(document,scale=10,floor_elevation=0),materials())
    assert all(r['material_id'] is None for r in price_rows(unknown,materials())['items'] if r['kind']=='path')


def test_saved_purchase_quantities_are_not_replicated_or_converted_to_cable_metres():
    row=dict(kind='path',saved_route_version_id=8,material_kind='wire',quantity=3,unit='roll')
    assert paired_wiring_components([row],[])==[row]


def test_canonical_paths_can_choose_products_without_rewriting_unknown_provenance():
    rows=document_takeoff(source(),scale=10,floor_elevation=0)
    for row in rows:
        if row['kind']=='path':
            row.update(canonical=True,origin='unresolved')
    rows=paired_wiring_components(rows,materials())
    apply_conduit_choice(rows,materials(),2); apply_wire_choice(rows,materials(),1)
    paths=[r for r in price_rows(rows,materials())['items'] if r['kind']=='path']
    assert {r['material_id'] for r in paths}=={1,2}
    assert all(r['origin']=='unresolved' for r in paths)


def test_legacy_shared_key_applies_only_to_its_original_product(monkeypatch):
    from types import SimpleNamespace as NS
    from app.services import item_pricing_service as pricing
    catalog=[dict(m,code=str(m['id'])) for m in materials()]
    rows=paired_wiring_components(document_takeoff(source(),scale=10,floor_elevation=0),catalog)
    apply_conduit_choice(rows,catalog,2); apply_wire_choice(rows,catalog,1)
    priced=price_rows(rows,catalog)
    conduit=next(r for r in expand_items(priced['items']) if r.get('material_kind')=='conduit')
    old_key=pricing.path_key(conduit,legacy=True)
    old_fingerprint=pricing.fingerprint(dict(conduit,item_kind='path'),catalog[1])
    quote=dict(row_id='CSV:2',excluded=False,material_id=2,catalog_code='2',catalog_name=catalog[1]['name'],catalog_unit='meter',unit_price='2',units_per_purchase='1',currency='PHP')
    monkeypatch.setattr(pricing.repository,'current',lambda *_:NS(version_number=1,document={'assignments':{old_key:dict(price_version_id=1,price_row_id='CSV:2',fingerprint=old_fingerprint)}}))
    monkeypatch.setattr(pricing.prices,'find',lambda *_:NS(document={'rows':[quote]}))
    monkeypatch.setattr(pricing.prices,'latest_automatic',lambda *_args,**_kwargs:None)
    result=pricing.apply_prices(None,1,priced,catalog)
    paths=[r for r in result['items'] if r['kind']=='path']
    assert next(r for r in paths if r['material_kind']=='conduit')['unit_price']==2
    assert next(r for r in paths if r['material_kind']=='wire')['unit_price']==10
    assert len({r['item_key'] for r in paths})==2
