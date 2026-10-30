from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.database import get_engine,get_db
from app.core.config import Settings
from app.api.dependencies import get_current_user
from app.main import create_app
from app.models import Material,MaterialAssembly,Role,User
from app.repositories import material_price_repository as prices
from app.schemas.material_price import MaterialPriceWrite
from app.schemas.material_assembly import AssemblyWrite
from app.services import material_assembly_service as service
from app.services.material_price_service import update_material_price,MaterialPriceError
from app.services.draft_bom_service import price_rows
from sqlalchemy.orm import Session


@pytest.fixture
def context():
    engine=get_engine()
    assert (engine.url.username,engine.url.database)==('ved_test','ved_electrical_verify')
    MaterialAssembly.__table__.create(engine,checkfirst=True)
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            with Session(connection,join_transaction_mode='create_savepoint') as db:
                role=db.scalar(select(Role).where(Role.name=='ADMIN'))
                user=User(oauth_provider='test',oauth_subject=uuid4().hex,role=role)
                db.add(user);db.flush()
                parts=[]
                for name,amount in [('Panasonic simplex outlet 16A 250V mechanism','100'),('Panasonic compatible plate','50')]:
                    part=Material(code=uuid4().hex,name=name,unit='piece',category='Synthetic test component')
                    db.add(part);db.flush();parts.append(part)
                    update_material_price(db,current_user=user,material_id=part.id,
                        request=MaterialPriceWrite(unit_price=amount,currency='PHP',effective_at=datetime.now(timezone.utc)))
                yield db,user,parts
        finally:
            transaction.rollback()


def request(parts,**changes):
    return AssemblyWrite.model_validate(dict(expected_revision=0,code='ASSEMBLY-'+uuid4().hex,
        name='Simplex outlet — Panasonic 16A 250V',brand='Panasonic',device_type='simplex_outlet',is_default=True,
        specifications='16A 250V',scope='Mechanism and plate. Box and shipping excluded.',
        components=[dict(material_id=p.id,quantity=1) for p in parts])|changes)


def catalog(db):
    materials=[]
    for m in db.scalars(select(Material).where(Material.is_active.is_(True))):
        price=prices.latest_price(db,m.id,at=datetime.now(timezone.utc).replace(tzinfo=None))
        materials.append(dict(id=m.id,code=m.code,name=m.name,unit=m.unit,
            unit_price=price.unit_price if price else None,currency=price.currency if price else None,
            price_revision_id=price.id if price else None))
    return service.annotate_catalog(db,materials)


def row(name='Simplex outlet',**changes):
    return dict(kind='device',name=name,class_id=1,quantity=2,unit='piece',symbol_ids=['a','b'],basis='Synthetic takeoff.')|changes


def test_parts_combine_reprice_and_capture_old_snapshot(context):
    db,user,parts=context
    saved=service.save(db,user,request(parts))['assemblies'][0]
    assert saved['unit_price']==150 and len(saved['component_prices'])==2
    old=service.estimate_snapshot(db,saved['material_id'],saved['price_revision_id'])
    frozen=deepcopy(old)
    before=prices.last_revision(db,saved['material_id'])
    update_material_price(db,current_user=user,material_id=parts[0].id,
        request=MaterialPriceWrite(unit_price='120',currency='PHP',effective_at=datetime.now(timezone.utc)))
    db.commit()
    after=prices.last_revision(db,saved['material_id'])
    assert (before.unit_price,after.unit_price)==(150,170)
    assert after.version_number==before.version_number+1 and old==frozen
    assert service.listing(db)['assemblies'][0]['unit_price']==170
    result=price_rows([row()],catalog(db))
    assert result['priced_subtotals']=={'PHP':Decimal(340)}
    assert result['items'][0]['default_brand_used'] and result['items'][0]['assembly']['brand']=='Panasonic'
    assert result['items'][0]['material_id']==saved['material_id']


def test_default_matches_only_compatible_known_devices(context):
    db,user,parts=context
    service.save(db,user,request(parts))
    values=catalog(db)
    assert service.choose_default(row(),values)
    assert service.choose_default(row('Panasonic simplex outlet'),values)
    for target in [row('Royu simplex outlet'),row('Simplex outlet 10A 250V'),row('GFCI simplex outlet'),
            row('Floor-mounted simplex outlet'),row('Duplex outlet'),row(class_id=None),
            row(preferred_material_id=parts[0].id),row(custom_unit_price=0),row(kind='path')]:
        assert service.choose_default(target,values) is None


def test_client_upload_identity_and_matching_ignore_fallback_brand_not_source_specification(context):
    from app.services.automatic_client_pricing import target_fingerprint,compatible
    db,user,parts=context
    service.save(db,user,request(parts))
    original=row();original['item_kind']='device'
    defaulted=deepcopy(original)
    price_rows([defaulted],catalog(db))
    assert target_fingerprint(defaulted)==target_fingerprint(original)
    # The source has no 16A rating: a default must not invent that constraint
    # when comparing a later Designer-uploaded product.
    quote=dict(excluded=False,family='outlet',quantity_unit='piece',name='Simplex outlet 10A 250V',specification='')
    assert compatible(defaulted,quote)
    specified=deepcopy(original);specified['name']='Simplex outlet 16A 250V'
    assert not compatible(specified,quote)


def test_disabled_default_does_not_automatically_choose_only_remaining_recipe(context):
    db,user,parts=context
    service.save(db,user,request(parts,is_default=False))
    assert service.choose_default(row(),catalog(db)) is None


@pytest.mark.parametrize('name,kind',[('One gang device switch','switch_1gang'),('Two gang device switch','switch_2gang'),
    ('Three gang device switch','switch_3gang'),('Three way device switch','switch_3way'),
    ('Single data outlet','data_simplex'),('Duplex floor-mounted data outlet','data_duplex'),('CCTV camera (dome type)','cctv')])
def test_device_types_are_not_interchanged(name,kind):
    assert service.device_type(name)==kind


def test_stale_recipe_rejected_and_only_one_default_survives(context):
    db,user,parts=context
    data=request(parts)
    first=service.save(db,user,data)['assemblies'][0]
    with pytest.raises(service.AssemblyConflict):
        service.save(db,user,data,first['material_id'])
    second=request(parts,name='Simplex outlet — Alternative Panasonic 16A 250V')
    result=service.save(db,user,second)['assemblies']
    assert sum(r['is_default'] for r in result)==1
    previous=next(r for r in result if r['material_id']==first['material_id'])
    assert not previous['is_default'] and previous['expected_revision']==2


def test_shipping_nested_and_ambiguous_components_rejected(context):
    db,user,parts=context
    data=request(parts)
    with pytest.raises(service.AssemblyError,match='once'):
        service.save(db,user,data.model_copy(update={'components':[data.components[0],data.components[0]]}))
    saved=service.save(db,user,data)['assemblies'][0]
    with pytest.raises(MaterialPriceError,match='ASSEMBLY_PRICE_IS_DERIVED'):
        update_material_price(db,current_user=user,material_id=saved['material_id'],
            request=MaterialPriceWrite(unit_price=1,currency='PHP',effective_at=datetime.now(timezone.utc)))
    nested=request(parts,components=[dict(material_id=saved['material_id'],quantity=1)])
    with pytest.raises(service.AssemblyError,match='Nested'):
        service.save(db,user,nested)
    parts[0].name='Shipping service'
    with pytest.raises(service.AssemblyError,match='Shipping'):
        service.save(db,user,request(parts))
    db.rollback()


def test_deactivated_or_changed_component_cannot_use_stale_total(context):
    db,user,parts=context
    saved=service.save(db,user,request(parts))['assemblies'][0]
    parts[0].is_active=False;db.flush()
    assert not service.listing(db)['assemblies'][0]['price_available']
    result=price_rows([row()],catalog(db))
    assert result['unpriced_items']==1 and result['items'][0]['unit_price'] is None
    with pytest.raises(service.AssemblyError):
        service.estimate_snapshot(db,saved['material_id'],saved['price_revision_id'])


def test_api_role_guards_save_reload_and_stale_writes(context):
    db,user,parts=context
    app=create_app(Settings(_env_file=None,auto_start_demo_worker=False,auto_start_interpretation_worker=False))
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:user
    client=TestClient(app)
    body=request(parts).model_dump(mode='json')
    response=client.post('/api/admin/material-assemblies',json=body)
    assert response.status_code==201,response.text
    stored=response.json()['assemblies'][0]
    assert stored['unit_price']=='150.0000'
    assert client.get('/api/admin/material-assemblies').json()['assemblies'][0]==stored
    assert client.put(f'/api/admin/material-assemblies/{stored["material_id"]}',json=body).status_code==409
    designer=SimpleNamespace(id=user.id,role=SimpleNamespace(name='DESIGNER'))
    app.dependency_overrides[get_current_user]=lambda:designer
    assert client.get('/api/admin/material-assemblies').status_code==403
    assert client.post('/api/admin/material-assemblies',json=body).status_code==403
    assert client.put(f'/api/admin/material-assemblies/{stored["material_id"]}',json=body).status_code==403
