from copy import deepcopy
from decimal import Decimal
from app.services.bom_display import grouped_rows


def device(identity, **extra):
    return dict(kind='device',class_id=1,name='Lamp',symbol_ids=[identity],
        quantity=1,unit='piece',unit_price='12.5',currency='PHP',line_total='12.5',**extra)


def test_similar_devices_group_with_server_totals_and_scoped_references_without_mutation():
    rows=[device('symbol-0001',floor_plan_id=1),device('symbol-0001',floor_plan_id=2)]
    before=deepcopy(rows)
    group,=grouped_rows(rows)
    assert group['components'][0]['quantity']==2 and group['costs']=={'PHP':Decimal('25')}
    assert len(group['members'])==2 and group['members'][0]['floor_plan_id']!=group['members'][1]['floor_plan_id']
    assert not group['incomplete'] and rows==before


def test_price_product_class_currency_and_units_never_merge():
    first=device('symbol-0001')
    variants=[dict(first,unit_price='13'),dict(first,material_id=2),dict(first,class_id=2),
        dict(first,currency='USD'),dict(first,unit='box'),dict(first,client_product_name='Other lamp')]
    assert len(grouped_rows([first,*variants]))==7
    assert len(grouped_rows([first,dict(first,unit_price='12.5000')]))==1


def test_paths_pair_and_sum_without_joining_geometry_or_inventing_unknown_costs():
    rows=[]
    for identity,length in [('segment-0001',3),('segment-0002',5)]:
        for kind,price in [('conduit',25),('wire',12)]:
            rows.append(dict(kind='path',material_kind=kind,name=kind+' — wiring path '+identity,
                paired_path_component=True,path_id=identity,quantity=length,unit='meter',
                unit_price=price,currency='PHP',line_total=length*price,origin='observed'))
    group,=grouped_rows(rows)
    assert [r['quantity'] for r in group['components']]==[8,8]
    assert group['costs']=={'PHP':Decimal(296)} and len(group['members'])==2
    # Source pixels, generated routes and unknown totals stay distinct.
    unknown=[dict(row,unit='source pixel',line_total=None) for row in rows]
    measured,unmeasured=grouped_rows(rows+unknown)
    assert measured['costs']=={'PHP':Decimal(296)}
    assert unmeasured['costs']=={} and unmeasured['incomplete']
    assert len(grouped_rows(rows+[dict(r,origin='generated') for r in rows]))==2
