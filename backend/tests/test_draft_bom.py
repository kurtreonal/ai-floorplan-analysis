from copy import deepcopy
from decimal import Decimal
import pytest
from app.services.draft_bom_service import document_takeoff, price_rows
from types import SimpleNamespace as NS
from app.services.draft_bom_service import name_draft_symbols
from app.services.draft_bom_service import paper_scale, apply_conduit_choice, apply_wire_choice


def document():
    return dict(symbols=[dict(id='symbol-0001',class_id=1,class_name='Lamp',disposition='unresolved'),
        dict(id='symbol-0002',class_id=1,class_name='Lamp',disposition='rejected'),
        dict(id='symbol-0003',class_id=2,class_name='Circuit homerun notation',disposition='unresolved')],
        observed_wiring=[dict(id='segment-0001',disposition='unresolved',wiring_legend_name='Conduit',
            points=[dict(x=0,y=0),dict(x=30,y=0),dict(x=30,y=40)])])


def material(name='Lamp', unit='piece', price='12.50', identity=1):
    return dict(id=identity,name=name,unit=unit,unit_price=Decimal(price) if price is not None else None,
        currency='PHP',price_revision_id=8)


def test_unapproved_draft_counts_and_source_lengths_are_read_only():
    source=document(); before=deepcopy(source)
    rows=document_takeoff(source)
    assert rows[0]['quantity']==1 and rows[1]['quantity']==70 and rows[1]['unit']=='source pixel'
    measured=document_takeoff(source,scale=10)
    assert measured[1]['quantity']==7 and measured[1]['unit']=='meter'
    priced=price_rows(measured,[material(),material('Conduit','meter','3',2)])
    assert priced['priced_subtotals']=={'PHP':Decimal('33.50')}
    assert priced['unpriced_items']==0
    assert source==before


def test_same_path_retracing_counts_physical_span_once_but_not_separate_circuits():
    source = document()
    source['observed_wiring'][0]['points'] = [dict(x=x, y=y) for x, y in
        [(0, 0), (30, 0), (15, 0), (15, 20), (15, 0), (40, 0)]]
    first = document_takeoff(source, scale=10)[1]
    assert first['quantity'] == 6 and first['horizontal_meters'] == 6
    # Circuit/network identity is not known across separate logical paths.
    source['observed_wiring'].append({**source['observed_wiring'][0], 'id': 'segment-0002'})
    paths = [row for row in document_takeoff(source, scale=10) if row['kind'] == 'path']
    assert sum(row['quantity'] for row in paths) == 12


def joined_document():
    source=document()
    source['observed_wiring']=[dict(id='segment-0001',disposition='corrected',circuit_id='C1',wiring_legend_name='Conduit',
        points=[dict(x=0,y=0),dict(x=100,y=0),dict(x=100,y=50)],junction_attachments=[dict(junction_id='junction-0001',point_index=1)]),
        dict(id='segment-0002',disposition='corrected',circuit_id='C1',wiring_legend_name='Conduit',
        points=[dict(x=50,y=0),dict(x=100,y=0),dict(x=150,y=0)],junction_attachments=[dict(junction_id='junction-0001',point_index=1)])]
    return source


def test_explicit_network_shared_spans_count_once_not_same_circuit_names_or_nearby_lines():
    source=joined_document();before=deepcopy(source)
    paths=[r for r in document_takeoff(source,scale=10) if r['kind']=='path']
    assert len(paths)==1 and paths[0]['quantity']==20
    assert paths[0]['path_ids']==['segment-0001','segment-0002']
    assert source==before
    for wire in source['observed_wiring']:wire.pop('junction_attachments')
    paths=[r for r in document_takeoff(source,scale=10) if r['kind']=='path']
    assert len(paths)==2 and sum(r['quantity'] for r in paths)==25


def test_conflicting_materials_do_not_duplicate_network_or_pick_an_arbitrary_price():
    source=joined_document();source['observed_wiring'][1]['wiring_legend_name']='Other conduit'
    paths=[r for r in document_takeoff(source,scale=10) if r['kind']=='path']
    assert len(paths)==1 and paths[0]['quantity']==20 and paths[0]['material_conflict']
    paths[0]['custom_wire_price_per_meter']=10;paths[0]['material_kind']='wire'
    result=price_rows(paths,[material('Conduit','meter','3')])
    assert result['items'][0]['pricing_state']=='network_material_review_required'
    assert result['items'][0]['line_total'] is None


def test_saved_elevations_add_drop_to_both_conduit_and_wire_cost_without_display_measurements():
    source=document()
    source['symbols'][0]['mounting_height_meters']=1.2
    source['observed_wiring'][0].update(elevation_meters=8.8,
        device_attachments=[dict(symbol_id='symbol-0001',point_index=0)])
    rows=document_takeoff(source,scale=10,floor_elevation=6)
    assert rows[1]['quantity']==Decimal('8.6000')
    assert rows[1]['vertical_meters']==pytest.approx(1.6)
    apply_wire_choice(rows,[],None,price_per_meter=10)
    result=price_rows(rows,[material(),material('Conduit','meter','10',2)])
    assert result['items'][1]['line_total']==Decimal('86.0000')
    assert result['items'][2]['line_total']==Decimal('86.0000')
    # Distinct logical paths do not prove that the physical drop is shared.
    source['observed_wiring'].append({**source['observed_wiring'][0],'id':'segment-0002'})
    paths=[r for r in document_takeoff(source,scale=10,floor_elevation=6) if r['kind']=='path']
    assert sum(r['vertical_meters'] for r in paths)==pytest.approx(3.2)


def test_missing_drop_measurements_keep_2d_quantities_and_flag_incomplete_price():
    source=document();source['observed_wiring'][0]['device_attachments']=[dict(symbol_id='symbol-0001',point_index=0)]
    row=document_takeoff(source,scale=10)[1]
    assert row['quantity']==7 and row['vertical_meters']==0
    assert row['missing_vertical_inputs'] and 'INCOMPLETE' in row['basis']
    priced=price_rows([row],[material('Conduit','meter','10')])['items'][0]
    assert priced['pricing_state']=='measurement_incomplete' and priced['line_total'] is None
    apply_wire_choice([row],[],None,price_per_meter=10)
    row.update(material_kind='wire',custom_wire_price_per_meter=10)
    assert price_rows([row],[])['priced_subtotals']=={}


def test_explicitly_joined_branches_share_one_drop_but_independent_paths_do_not():
    source=joined_document()
    source['symbols'][0]['mounting_height_meters']=1.2
    for wire in source['observed_wiring']:
        wire.update(elevation_meters=3,device_attachments=[dict(
            symbol_id='symbol-0001',terminal_id='terminal-a',point_index=1)])
    joined=[r for r in document_takeoff(source,scale=10,floor_elevation=0) if r['kind']=='path']
    assert len(joined)==1 and joined[0]['vertical_meters']==pytest.approx(1.8)
    for wire in source['observed_wiring']:
        wire.pop('junction_attachments')
        wire['device_attachments'][0].pop('terminal_id')
    separate=[r for r in document_takeoff(source,scale=10,floor_elevation=0) if r['kind']=='path']
    assert len(separate)==2 and sum(r['vertical_meters'] for r in separate)==pytest.approx(3.6)


@pytest.mark.parametrize('catalog,state', [([], 'material_not_found'),
    ([material(price=None)],'missing_price'), ([material(unit='pack')],'purchase_unit_required'),
    ([material(),material(identity=2)],'ambiguous_material')])
def test_missing_prices_ambiguous_names_and_pack_units_are_not_zero(catalog,state):
    value=price_rows(document_takeoff(document())[:1],catalog)
    assert value['items'][0]['pricing_state']==state
    assert value['items'][0]['line_total'] is None and value['priced_subtotals']=={}


def test_zero_price_is_valid_but_scale_is_never_inferred():
    value=price_rows(document_takeoff(document()),[material(price='0'),material('Conduit','meter','4',2)])
    assert value['items'][0]['line_total']==0
    assert value['items'][1]['pricing_state']=='scale_required'
    assert value['items'][1]['line_total'] is None
    assert value['unpriced_items']==1


def test_ratings_and_brand_are_not_stripped_to_force_a_match():
    rows=document_takeoff(document())[:1];rows[0]['name']='Lamp 40W'
    assert price_rows(rows,[material('Lamp 20W')])['unpriced_items']==1


@pytest.mark.parametrize('suffix',[' [u:lamp-40w]',' [sheet-52:L02]',' [pdf-source:p1:L01]'])
def test_catalog_source_suffix_does_not_prevent_exact_material_matching(suffix):
    rows=document_takeoff(document())[:1];rows[0]['name']='Lamp 40W'+suffix
    assert price_rows(rows,[material('Lamp 40W')])['unpriced_items']==0


def test_separate_currency_subtotals_and_duplicate_identity_rejection():
    source=document(); source['symbols'].append(dict(id='manual-symbol-0001',class_id=4,class_name='Outlet',disposition='added'))
    catalog=[material(),{**material('Outlet',identity=2),'currency':'USD'}]
    result=price_rows(document_takeoff(source),catalog)
    assert result['priced_subtotals']=={'PHP':Decimal('12.50'),'USD':Decimal('12.50')}
    source['symbols'].append(source['symbols'][0])
    with pytest.raises(ValueError): document_takeoff(source)


def test_suppressed_generated_path_is_not_counted():
    source=document()
    source['generated_wiring']=[dict(source['observed_wiring'][0],suppression_reason='redundant_observed_connection')]
    assert len(document_takeoff(source))==2


def test_training_catalog_identity_names_draft_without_approving_or_confusing_model_indices():
    training=NS(name='Lamp 40W',legend_entry='pdf-source:p1:L01',model_class_id=91)
    prediction=NS(id='symbol-1',training_legend=training,catalog_class_id=None,observed_label='Original')
    candidate=NS(payload=NS(symbols=NS(items=[prediction])),provenance=NS(model_release_id='development_multiclass56_yolo'))
    legend=NS(id=7,class_id=91,name='Lamp 40W [pdf-source:p1:L01]')
    doc=dict(symbols=[dict(id='symbol-1',disposition='unresolved',symbol_legend_id=None)])
    name_draft_symbols(doc,candidate,{7:legend})
    assert doc['symbols'][0]['class_id']==91
    assert doc['symbols'][0]['disposition']=='unresolved' and doc['symbols'][0]['symbol_legend_id'] is None
    assert prediction.observed_label=='Original'
    # Same wording from another source, different rating, or ambiguous catalog
    # is NOT an authorized material classification.
    for other in [NS(id=8,class_id=92,name='Lamp 40W [pdf-other:p1:L01]'),NS(id=9,class_id=93,name='Lamp 20W [pdf-source:p1:L01]')]:
        name_draft_symbols(doc,candidate,{other.id:other})
        assert doc['symbols'][0]['class_id'] is None and doc['symbols'][0]['class_name']=='Lamp 40W'
    name_draft_symbols(doc,candidate,{7:legend,8:NS(id=8,class_id=92,name=legend.name)})
    assert doc['symbols'][0]['class_id'] is None
    prediction.catalog_class_id=91
    prediction.training_legend=None
    name_draft_symbols(doc,candidate,{7:legend})
    assert doc['symbols'][0]['class_id']==91


@pytest.mark.parametrize('scale',[0,-1,float('nan'),float('inf')])
def test_invalid_scale_never_produces_purchase_lengths(scale):
    with pytest.raises(ValueError): document_takeoff(document(),scale=scale)


@pytest.mark.parametrize('paper,width,height', [('A4',2100,2970),('A3',2970,4200),
    ('A2',4200,5940),('A1',5940,8410),('A0',8410,11890)])
def test_full_paper_assumption_at_one_to_one_hundred_is_orientation_independent(paper,width,height):
    assert paper_scale(width,height,paper)==100
    assert paper_scale(height,width,paper)==100
    assert paper_scale(1552,3264,paper) > 0  # explicit approximate allowance for cropped scan
    with pytest.raises(ValueError): paper_scale(width,height,'unknown')


def test_conduit_purchase_length_requires_conversion_not_an_implicit_metre():
    source=document(); before=deepcopy(source)
    source['observed_wiring'][0]['wiring_legend_name']='Raceway conduit concealed in ceiling'
    rows=document_takeoff(source,scale=10)
    conduit={**material('EMT pipe 1/2 inch, per length','length','360',9), 'category':'CONDUIT - EMT'}
    apply_conduit_choice(rows,[material(),conduit],9)
    result=price_rows(rows,[material(),conduit])
    assert result['items'][1]['quantity']==7 and result['items'][1]['unit']=='meter'
    assert result['items'][1]['line_total'] is None
    assert result['items'][1]['pricing_state']=='purchase_unit_required'
    assert 'requires an explicit conversion' in result['items'][1]['basis']
    assert result['items'][0]['material_id']==1
    assert before['observed_wiring'][0]['points']==source['observed_wiring'][0]['points']
    unscaled=document_takeoff(source)
    apply_conduit_choice(unscaled,[conduit],9)
    assert price_rows(unscaled,[conduit])['items'][1]['pricing_state']=='scale_required'
    for bad in [{**conduit,'category':'CABLE'}, {**conduit,'unit':'roll'}, {**conduit,'unit_price':None},
                {**conduit,'name':'Threaded rod, 10 ft 1/2 inch, per length'}]:
        with pytest.raises(ValueError): apply_conduit_choice(rows,[bad],9)
    with pytest.raises(ValueError): apply_conduit_choice(rows,[conduit],99)


def test_under_floor_and_ceiling_paths_keep_installation_identity_and_no_wire_multiplier():
    source=document()
    source['observed_wiring'][0].update(wiring_legend_name='Raceway conduit concealed under floor',installation_method='concealed_under_floor')
    source['generated_wiring']=[dict(id='g1',points=[dict(x=0,y=0),dict(x=20,y=0)],
        wiring_legend_name='Raceway conduit concealed in ceiling',installation_method='concealed_in_ceiling')]
    conduit={**material('Conduit','meter','10',9),'category':'CONDUIT'}
    rows=document_takeoff(source,scale=10)
    apply_conduit_choice(rows,[conduit],9)
    result=price_rows(rows,[conduit])
    assert [r['line_total'] for r in result['items'][1:]]==[Decimal('70'),Decimal('20')]
    assert [r['installation_method'] for r in result['items'][1:]]==['concealed_under_floor','concealed_in_ceiling']


def test_custom_sheet_scale_and_invalid_dimensions():
    assert paper_scale(3000,6000,'CUSTOM',300,600) == 100
    assert paper_scale(6000,3000,'CUSTOM',600,300) == 100
    for width,height in [(None,600),(0,600),(-1,600),(float('nan'),600),(300,10001)]:
        with pytest.raises(ValueError): paper_scale(3000,6000,'CUSTOM',width,height)
    with pytest.raises(ValueError): paper_scale(0,6000,'A3')


def test_wire_and_tube_are_separate_allowances_without_roll_conversion_or_conductor_guess():
    rows=document_takeoff(document(),scale=10)
    conduit={**material('Conduit','meter','10',9),'category':'CONDUIT'}
    wire={**material('THHN wire','meter','20',10),'category':'WIRE'}
    apply_conduit_choice(rows,[conduit,wire],9)
    apply_wire_choice(rows,[conduit,wire],10)
    result=price_rows(rows,[conduit,wire])
    assert result['items'][1]['line_total']==70
    assert result['items'][2]['line_total']==140
    assert result['items'][2]['quantity']==7
    assert result['items'][2]['material_kind']=='wire'
    assert 'Not conductor purchase quantity' in result['items'][2]['basis']
    roll={**wire,'unit':'roll'}
    rows=document_takeoff(document(),scale=10)
    apply_wire_choice(rows,[roll],10)
    assert price_rows(rows,[roll])['items'][-1]['pricing_state']=='purchase_unit_required'
    with pytest.raises(ValueError): apply_wire_choice(rows,[conduit],9)


def test_custom_device_price_groups_separately_and_overrides_catalog_only_in_draft():
    doc=document()
    doc['symbols'][0]['custom_unit_price']=25.5
    doc['symbols'].append(dict(doc['symbols'][0],id='symbol-0004',custom_unit_price=30))
    rows=document_takeoff(doc)
    priced=price_rows(rows,[])
    assert priced['priced_subtotals']=={'PHP':Decimal('55.50')}
    assert [r['quantity'] for r in rows if r['kind']=='device']==[1,1]
    assert all(r['pricing_state']=='custom_priced' for r in rows if r['kind']=='device')
    override=price_rows(document_takeoff(doc),[material()])
    assert override['priced_subtotals']=={'PHP':Decimal('55.50')}
    assert override['items'][0]['price_revision_id'] is None
    doc['symbols'][0]['custom_unit_price']=0
    assert price_rows(document_takeoff(doc),[])['items'][0]['line_total']==0


def test_wire_roll_conversion_custom_price_and_no_extra_allowance():
    wire={**material('THHN wire','roll','3500',10),'category':'WIRE'}
    before=deepcopy(wire)
    rows=document_takeoff(document(),scale=10)
    apply_wire_choice(rows,[wire],10,meters_per_unit=100)
    result=price_rows(rows,[wire])
    assert result['items'][-1]['unit_price']==35
    assert result['items'][-1]['quantity']==7
    assert result['items'][-1]['line_total']==245
    assert wire==before
    rows=document_takeoff(document(),scale=10)
    apply_wire_choice(rows,[wire],10,price_per_meter=20)
    assert price_rows(rows,[wire])['items'][-1]['line_total']==140
    rows=document_takeoff(document(),scale=10)
    apply_wire_choice(rows,[],None,price_per_meter=0)
    assert price_rows(rows,[])['items'][-1]['line_total']==0
    rows=document_takeoff(document())
    apply_wire_choice(rows,[],None,price_per_meter=20)
    assert price_rows(rows,[])['items'][-1]['pricing_state']=='scale_required'
    for factor in [0,-1,float('nan'),100001]:
        with pytest.raises(ValueError): apply_wire_choice([], [wire],10,meters_per_unit=factor)
    for price in [-1,float('inf'),1000000001]:
        with pytest.raises(ValueError): apply_wire_choice([],[],None,price_per_meter=price)


def test_only_explicit_wire_purchase_length_is_read_from_product_label():
    from app.services.draft_bom_service import wire_unit_length
    wire={**material('CAT6 cable (305M)','roll','30500',10),'category':'CABLE'}
    assert wire_unit_length(wire)==305
    rows=document_takeoff(document(),scale=10)
    apply_wire_choice(rows,[wire],10)
    assert price_rows(rows,[wire])['items'][-1]['line_total']==700
    assert wire_unit_length({**wire,'name':'Cable 16 AWG, max 75 C'}) is None
    assert wire_unit_length({**wire,'name':'Cable (100M) (200M)'}) is None
