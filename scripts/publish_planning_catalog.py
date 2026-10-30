"""Publish a reviewed local quote file and flat recipes; never replace existing SKUs.

Default is a dry run. --apply requires an existing Admin ID. Source URLs remain
with the recipe/activity record; official prices live only in database revisions.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy.orm import Session
from app.core.database import get_engine
from app.models import User
from app.repositories import material_catalog_repository as catalog, material_price_repository as prices
from app.services.material_price_service import update_material_price
from app.services.material_assembly_service import save as save_assembly
from app.schemas.material_price import MaterialPriceWrite
from app.schemas.material_assembly import AssemblyWrite
from app.services.activity_log import record


def publish(db, admin, data):
    if not admin or admin.role.name!='ADMIN': raise ValueError('An approved Admin account is required.')
    if data.get('shipping_included') is not False: raise ValueError('Shipping must be excluded.')
    created, recipes = 0, 0
    for offer in data['offers']:
        if not offer.get('source','').startswith('https://') or not offer.get('checked'): raise ValueError('Every quote needs its source and check date.')
        material=catalog.by_code(db,offer['code'],lock=True)
        if material:
            if (material.name,material.unit)!=(offer['name'],offer['unit']): raise ValueError('An existing SKU has a different identity.')
            continue  # Admin changes to existing prices always win over a rerun.
        material=catalog.create(db,{k:offer[k] for k in ('code','name','unit','category')})
        update_material_price(db,current_user=admin,material_id=material.id,
            request=MaterialPriceWrite(unit_price=Decimal(offer['price_php']),currency='PHP',effective_at=datetime.now(timezone.utc)))
        record(db,admin,'CATALOG_QUOTE_IMPORTED','material',material.id,
            f"{offer['checked']}: {offer['source']} | {offer.get('notes','')}"[:500])
        created+=1
    for recipe in data['recipes']:
        if catalog.by_code(db,recipe['code']): continue
        components=[]
        for part in recipe['components']:
            material=catalog.by_code(db,part['code'])
            if not material: raise ValueError('A recipe component SKU is missing.')
            components.append(dict(material_id=material.id,quantity=part['quantity']))
        payload={k:v for k,v in recipe.items() if k!='components'}
        payload.update(expected_revision=0,components=components)
        save_assembly(db,admin,AssemblyWrite.model_validate(payload),commit=False)
        recipes+=1
    return dict(created_products=created,created_recipes=recipes,existing_prices_replaced=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path);parser.add_argument('--admin-id',required=True,type=int);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    with Session(get_engine()) as db:
        try:
            result=publish(db,db.get(User,args.admin_id),json.loads(args.source.read_text(encoding='utf-8')))
            if args.apply: db.commit()
            else: db.rollback()
            print(dict(result,applied=args.apply))
        except Exception as error:
            db.rollback();print(dict(status='not_applied',error_type=type(error).__name__,message=str(error) if isinstance(error,ValueError) else 'Catalog operation failed.'));sys.exit(1)
