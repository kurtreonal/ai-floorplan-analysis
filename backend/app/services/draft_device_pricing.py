"""Explicit approved-product choices for the live draft, not historical estimates."""
import json
from decimal import Decimal
from app.services.product_compatibility import compatible_product
from app.services.material_assembly_service import device_type, _protected_match


def selections(value):
    if value is None:
        return {}
    try:
        parsed=json.loads(value) if isinstance(value,str) else value
        if not isinstance(parsed,dict) or len(parsed)>200:
            raise ValueError()
        result={}
        for key,material_id in parsed.items():
            if not str(key).isdigit() or int(key)<0 or type(material_id) is not int or material_id<=0:
                raise ValueError()
            result[int(key)]=material_id
        return result
    except (ValueError,TypeError):
        raise ValueError('Choose valid approved device products.') from None


def compatible(row,material):
    if row.get('class_id') is None or material.get('unit_price') is None:
        return False
    if material.get('category','').casefold()=='device components':
        return False
    # A previous client/default product is not a new requirement on the drawing.
    source=dict(row,material_id=None,material_name=None)
    if not compatible_product(source,material):
        return False
    assembly=material.get('assembly')
    if assembly:
        return (device_type(row['name'])==assembly['device_type'] and
            _protected_match(row['name'],material['name']+' '+assembly['specifications']))
    return True


def apply_choices(rows,materials,chosen):
    by_id={m['id']:m for m in materials}
    for class_id,material_id in chosen.items():
        targets=[r for r in rows if r['kind']=='device' and r.get('class_id')==class_id]
        if not targets:
            continue  # Removing a device group must not block the remaining canvas.
        material=by_id.get(material_id)
        if material is None or not all(compatible(r,material) for r in targets):
            raise ValueError('The selected approved product does not match this device group.')
        for row in targets:
            for key in list(row):
                if key.startswith('client_'):
                    row.pop(key)
            for key in ('project_price_version_id','project_price_row_id',
                        'item_price_warning','item_price_assignment_version',
                        'assembly_id','assembly','default_brand_used'):
                row.pop(key,None)
            row.update(material_id=material_id,material_name=material['name'],unit_price=material['unit_price'],
                currency=material['currency'],price_revision_id=material['price_revision_id'],
                price_source='manual_catalog',pricing_state='priced',
                line_total=Decimal(str(row['quantity']))*material['unit_price'])
            row['basis']+=' Explicit approved product for this draft calculation; client prices and saved estimates are unchanged.'
            if material.get('assembly'):
                row.update(assembly_id=material_id,assembly=material['assembly'])
                if material['assembly'].get('assumed'): row['estimated']=True
                row['assembly_scope_incomplete']=material['assembly'].get('scope_complete') is False
            else:
                row.pop('assembly_scope_incomplete',None)


def groups(rows,materials):
    from app.services.draft_bom_service import product_brand
    result={}
    by_id={m['id']:m for m in materials}
    for row in rows:
        if row['kind']!='device' or row.get('class_id') is None:
            continue
        key=row['class_id']
        if key not in result:
            result[key]=dict(class_id=key,name=row['name'],quantity=0,selected_material_id=row.get('material_id'),
                materials=[dict({k:m[k] for k in ('id','name','unit','unit_price','currency')},brand=product_brand(m),code=m.get('code'))
                    for m in materials if compatible(row,m)])
        else:
            if result[key]['selected_material_id']!=row.get('material_id'):result[key]['selected_material_id']=None
            result[key]['materials']=[m for m in result[key]['materials'] if compatible(row,by_id[m['id']])]
        result[key]['quantity']+=row['quantity']
    return sorted(result.values(),key=lambda r:r['name'].casefold())
