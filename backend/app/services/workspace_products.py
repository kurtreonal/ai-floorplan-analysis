"""Source-bound, per-device and connected-network products for the live workspace."""
from copy import deepcopy
from decimal import Decimal
import re
from sqlalchemy import select
from app.models import FloorPlanInterpretationRun,SymbolLegend
from app.services.material_workbook import WorkbookError


def validate_choices(db,plan_id,choices,products,materials,defaults,layout):
    from app.services.draft_device_pricing import compatible
    from app.services.draft_bom_service import wire_choices,conduit_choices
    from app.services.layout_materials import wire_allowed
    from app.services.wiring_material_pairing import allowed_conduits
    runs=set(db.scalars(select(FloorPlanInterpretationRun.candidate_run_id).where(FloorPlanInterpretationRun.floor_plan_id==plan_id)).all()) if plan_id else set()
    wires={m['id'] for m in wire_choices(materials)}
    conduits={m['id'] for m in conduit_choices(materials)}
    rules={p['wire_material_id']:p for p in defaults['wire_conduit_pairs']}
    for key,choice in choices.items():
        if not re.fullmatch(r'(?:device|wire):[A-Za-z0-9_.:-]{1,160}',key) or not key.startswith(choice.kind+':') or choice.candidate_run_id not in runs:
            raise WorkbookError('Open the current plan workspace before changing this product.')
        product=products.get(choice.material_id)
        if product is None:raise WorkbookError('Choose an available approved product.')
        if choice.kind=='device':
            legend=db.scalar(select(SymbolLegend).where(SymbolLegend.class_id==choice.class_id,SymbolLegend.is_active.is_(True)))
            if not legend or not compatible(dict(class_id=choice.class_id,name=legend.name,unit='piece',kind='device'),product):
                raise WorkbookError('Choose a product compatible with this device symbol.')
        else:
            rule=rules.get(choice.material_id)
            if choice.material_id not in wires or not wire_allowed(product,layout) or not rule:
                raise WorkbookError('Choose wiring with an Admin-approved conduit pair for this layout.')
            if choice.conduit_id and (choice.conduit_id not in conduits or choice.conduit_id not in allowed_conduits(rule)):
                raise WorkbookError('Choose one of this wire product’s compatible conduits.')
            if product['unit']=='meter' and choice.wire_meters_per_unit not in (None,1):
                raise WorkbookError('A metre-priced product already uses one metre per unit.')


def choice_for(row,settings,kind,identity):
    choice=settings.get('itemMaterials',{}).get(f'{kind}:{identity}')
    return choice if choice and choice.get('candidate_run_id')==row.get('candidate_run_id') else None


def split_devices(rows,scopes):
    result=[]
    for row in rows:
        ids=row.get('symbol_ids') or []
        if row['kind']!='device' or not ids or len(ids)!=row['quantity']:
            result.append(row);continue
        buckets={}
        for identity in ids:
            choice=choice_for(row,scopes[row.get('floor_plan_id')],'device',identity)
            material=choice['material_id'] if choice and choice.get('class_id')==row.get('class_id') else None
            buckets.setdefault(material,[]).append(identity)
        for material,identities in buckets.items():
            result.append(dict(row,symbol_ids=identities,quantity=Decimal(len(identities)),workspace_material_id=material))
    return result


def apply_network_choices(rows,scopes,materials,rules,*,planning_counts=None):
    """Replace purchases, never geometry; one choice covers the physical network."""
    from app.services.wiring_bom_components import path_scope
    from app.services.wiring_material_pairing import pair_rows,fill_planning_conductor_counts
    from app.services.draft_bom_service import apply_wire_choice,price_rows,wire_unit_length
    from app.services.layout_materials import wire_allowed
    networks={}
    for row in rows:
        if row.get('material_kind') in ('wire','conduit'):networks.setdefault(path_scope(row),[]).append(row)
    catalog={m['id']:m for m in materials}
    for network in networks.values():
        source=network[0]
        selected=[choice_for(source,scopes[source.get('floor_plan_id')],'wire',identity) for identity in source.get('path_ids') or [source.get('path_id')]]
        choices={ (c['material_id'],c.get('conduit_id'),c.get('conductor_count'),c.get('wire_meters_per_unit'),c.get('conduit_meters_per_unit')) for c in selected if c }
        if not choices:continue
        if len(choices)>1:
            for row in network:row.update(material_conflict=True,line_total=None,pricing_state='network_material_review_required')
            continue
        wire_id,conduit_id,conductor_count,meters_per_unit,conduit_length=choices.pop()
        if wire_id not in catalog:
            for row in network:row.update(line_total=None,pricing_state='material_not_found')
            continue
        if not wire_allowed(catalog[wire_id],scopes[source.get('floor_plan_id')].get('layoutType')):continue
        copies=deepcopy(network)
        assumed_count=any(c.get('conductor_count_assumed') for c in selected if c)
        for row in copies:
            for key in list(row):
                if key.startswith(('client_','catalog_')):row.pop(key,None)
            for key in ('compatible_pair_missing','client_product_name','client_product_code','client_product_specification','client_price_only','item_price_warning','preferred_material_id','material_id','custom_wire_price_per_meter','purchase_meters_per_unit','wire_meters_per_unit'):
                row.pop(key,None)
        apply_wire_choice(copies,materials,wire_id,meters_per_unit=meters_per_unit)
        if assumed_count:
            for row in copies:
                if row.get('material_kind')=='wire' and (row.get('conductor_count') is None or row.get('conductor_count_assumed')):row.update(conductor_count_assumed=True,estimated=True)
        for row in copies:
            if row.get('material_kind')=='wire':
                if conductor_count is not None and (not assumed_count or row.get('conductor_count') is None or row.get('conductor_count_assumed')):row.update(conductor_count=conductor_count,conductor_count_assumed=assumed_count)
                if meters_per_unit is not None:row['workspace_purchase_meters_per_unit']=meters_per_unit
        setup=scopes[source.get('floor_plan_id')]
        fill_planning_conductor_counts(copies,materials,(planning_counts or {}).get(source.get('floor_plan_id'),(setup.get('automaticDefaults') or {}).get('conductor_count')),wire_id=wire_id)
        pair_rows(copies,rules,wire_id=wire_id,conduit_id=conduit_id,materials=materials)
        if conduit_length is not None:
            for row in copies:
                if row.get('material_kind')=='conduit':row['workspace_purchase_meters_per_unit']=conduit_length
        priced=price_rows(copies,materials,device_defaults=False)['items']
        for original,replacement in zip(network,priced):
            quote=catalog.get(replacement.get('preferred_material_id') or replacement.get('material_id'))
            if quote:
                replacement.update(material_id=quote['id'],material_name=quote['name'],wire_meters_per_unit=meters_per_unit if replacement.get('material_kind')=='wire' and meters_per_unit is not None else wire_unit_length(quote),price_source='designer_product_choice',catalog_unit_price=quote['unit_price'],catalog_price_unit=quote['unit'],catalog_currency=quote['currency'])
            original.clear();original.update(replacement)
