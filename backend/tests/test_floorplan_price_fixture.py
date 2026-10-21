from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tests.test_manual_item_prices import item_schema,project_price_schema,source_schema
from tests.test_automatic_client_pricing import upload
from tests.test_routing_api import context
from tests.synthetic_pricing import prepare


def test_delivered_prices_match_lighting_fixture_without_mapping_or_catalog_entries(context):
    prepare(context)
    client,_,_,session,layout,*_=context
    geometry=deepcopy(layout.geometry_document)
    geometry['symbols']=[]
    labels=[('1 x 40 watts fluorescent lamp',4),('2 x 40 watts fluorescent lamp',16),
        ('One gang device switch',6),('Two gang device switch',3)]
    for class_id,(name,count) in enumerate(labels,101):
        for _ in range(count):
            number=len(geometry['symbols'])+1
            geometry['symbols'].append(dict(id=f'manual:{number}',source_type='manual',source_record_id=number,
                processing_job_id=103,status='manually_added',**{'class':dict(id=class_id,name=name)},position=dict(x=1+number%15,y=1+number//15)))
    layout.geometry_document=geometry;session.commit()
    data=(Path(__file__).resolve().parents[2]/'frontend/public/fixtures/ved-synthetic-pricing.xlsx').read_bytes()
    root=f'/api/projects/{layout.project_id}'
    imported=upload(client,root,data,name='floorplan-test.xlsx')
    assert imported.status_code==200,imported.text
    assert imported.json()['applied']==33,imported.json()
    value=client.get(root+'/bom').json()['planning']
    summary=value['cost_summary']['currencies']['PHP']
    assert Decimal(summary['devices'])==14445
    assert Decimal(summary['conduit'])==500 and Decimal(summary['wire'])==240
    assert Decimal(summary['total'])==15185
    assert len(value['display_groups'])==5
    assert client.get(root+'/bom').json()['planning']['cost_summary']==value['cost_summary']
