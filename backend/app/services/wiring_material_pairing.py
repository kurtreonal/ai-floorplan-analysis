"""Use Admin-defined product pairs; never infer conduit fill from conductor area."""
import json
import math
import re
from typing import Annotated
from decimal import Decimal, ROUND_CEILING,ROUND_DOWN
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class MaterialPair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    wire_material_id: int = Field(gt=0)
    conduit_material_id: int = Field(gt=0)
    wire_meters_per_unit: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    conduit_meters_per_unit: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    under_floor_conduit_material_id: int | None = Field(default=None, gt=0)
    under_floor_meters_per_unit: float | None = Field(default=None, gt=0, le=100000, allow_inf_nan=False)
    conduit_options: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list,max_length=256)
    conductor_count: int | None = Field(default=None, ge=1, le=1000)
    specification: str = Field(min_length=1, max_length=500)
    assumed: StrictBool = False


def provisional_pairs(materials):
    """Editable budgeting assumptions over actual active SKUs, not a fill certificate.

    One communications cable per dedicated raceway; large multi-pair/core cable
    receives a larger provisional trade size. Purchase lengths remain unknown
    unless explicit on the wire product. No conductor multiplier is inferred.
    """
    import re
    from app.services.product_compatibility import inch_sizes
    from app.services.draft_bom_service import wire_choices, conduit_choices, wire_unit_length
    conduits = conduit_choices(materials)
    result = []
    for wire in wire_choices(materials):
        bulky = bool(re.search(r'\b(?:25|50|100)\s*(?:pairs?|prs?)\b|\b(?:24|48|96)\s*cores?\b', wire['name'], re.I))
        size = 1.0 if bulky else .75
        explicit = re.search(r'\b(IMC|EMT|RSC|RMC|PVC|HDPE)\b', wire['name'], re.I)
        family = explicit[1].upper() if explicit else 'IMC' if re.search(r'outdoor|buried|underground|external|gel[- ]filled', wire['name'], re.I) else 'EMT'
        # Trade-size labels are not measured bores. Do not equate an EMT fitting
        # with an NPS pipe fitting, or calculate fill from a nominal inch value.
        options = [m for m in conduits if inch_sizes(m['name']) == {size} and re.search(r'\b'+family+r'\b', m['name'], re.I)]
        options.sort(key=lambda m: (not m.get('code','').startswith('PANASONIC-'), m.get('code',''), m['id']))
        if not options:
            continue
        conduit = options[0]
        under_floor = sorted([m for m in conduits if inch_sizes(m['name']) == {size} and re.search(r'\bIMC\b',m['name'],re.I)],
            key=lambda m:(not m.get('code','').startswith('PANASONIC-'),m.get('code',''),m['id']))
        result.append(MaterialPair(wire_material_id=wire['id'], conduit_material_id=conduit['id'],
            conduit_options=[m['id'] for m in conduits],
            wire_meters_per_unit=wire_unit_length(wire),
            conduit_meters_per_unit=wire_unit_length(conduit) or (3 if conduit['unit']=='length' else None),
            under_floor_conduit_material_id=under_floor[0]['id'] if under_floor else None,
            under_floor_meters_per_unit=(wire_unit_length(under_floor[0]) or (3 if under_floor[0]['unit']=='length' else None)) if under_floor else None,
            assumed=True, specification=f'Estimated dedicated {size:g}-inch {family} {"tubing" if family=="EMT" else "pipe"} for one cable. '
                'Assume 3 m per stick only where no length is recorded. Verify bore, cable OD, bends and environment; no conductor multiplier.').model_dump())
    return result


class PurchasePrice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    material_id: int = Field(gt=0)
    price: float | None = Field(default=None,ge=0, le=1000000000, allow_inf_nan=False)
    meters_per_unit: float | None = Field(default=None,gt=0, le=100000, allow_inf_nan=False)


def purchase_prices(value):
    if not value:
        return {}
    data = json.loads(value) if isinstance(value,str) else value
    if not isinstance(data, dict) or set(data) - {'wire', 'conduit'}:
        raise ValueError('Invalid purchase pricing.')
    return {key: PurchasePrice.model_validate(row).model_dump() for key, row in data.items()}


def allowed_conduits(rule):
    return set(rule.get('conduit_options',[])) | {rule['conduit_material_id']} | ({rule['under_floor_conduit_material_id']} if rule.get('under_floor_conduit_material_id') else set())


def fill_planning_conductor_counts(rows, materials, count, *, wire_id=None):
    """Fill missing individual-wire counts before pairing, preserving circuit data."""
    if count is None:return
    catalog={m['id']:m for m in materials}
    for row in rows:
        if row.get('material_kind')!='wire' or row.get('saved_route_version_id') or row.get('conductor_count') is not None:continue
        product=catalog.get(wire_id or row.get('preferred_material_id') or row.get('material_id'),{})
        if re.search(r'\b(?:THHN|THW|single[ -]?core|single conductor)\b',product.get('name') or row.get('material_name') or '',re.I):
            row.update(conductor_count=count,conductor_count_assumed=True,estimated=True)


def pair_rows(rows, rules, *, wire_id=None, conduit_id=None, materials=()):
    from app.services.wiring_bom_components import path_scope
    by_wire = {p['wire_material_id']: p for p in rules}
    catalog={m['id']:m for m in materials}
    wires = {path_scope(row): row for row in rows if row.get('material_kind') == 'wire'}
    for row in rows:
        if row.get('material_kind') != 'conduit' or row.get('saved_route_version_id'):
            continue
        wire = wires.get(path_scope(row))
        product = wire_id or (wire or {}).get('preferred_material_id') or (wire or {}).get('material_id')
        rule = by_wire.get(product)
        if not rule:
            if wire_id or conduit_id:
                row['compatible_pair_missing']=True
            continue
        if conduit_id is not None and conduit_id not in allowed_conduits(rule):
            raise ValueError('Choose a conduit approved for the selected wire product.')
        if wire and wire.get('conductor_count') is not None and rule.get('conductor_count') is not None and wire['conductor_count']!=rule['conductor_count']:
            row['compatible_pair_missing']=True
            continue
        under_floor = row.get('installation_method') == 'concealed_under_floor' and rule.get('under_floor_conduit_material_id')
        selected=conduit_id or (rule['under_floor_conduit_material_id'] if under_floor else rule['conduit_material_id'])
        row['preferred_material_id'] = selected
        row['automatic_material_pair'] = True
        row['pair_specification'] = rule['specification']
        if rule.get('assumed'):
            row.update(estimated=True, pair_assumed=True)
        from app.services.draft_bom_service import wire_unit_length
        product=catalog.get(selected)
        factor=rule.get('conduit_meters_per_unit') if selected==rule['conduit_material_id'] else rule.get('under_floor_meters_per_unit') if selected==rule.get('under_floor_conduit_material_id') else None
        row['purchase_meters_per_unit'] = (wire_unit_length(product) if product else None) or factor
        if product and product['unit']=='length' and not row['purchase_meters_per_unit'] and rule.get('assumed'):
            row.update(purchase_meters_per_unit=3,estimated=True,purchase_length_assumed=True)
        if wire:
            wire['automatic_material_pair'] = True
            wire['pair_specification'] = rule['specification']
            if rule.get('assumed'):
                wire.update(estimated=True, pair_assumed=True)
            wire['wire_meters_per_unit'] = wire.get('wire_meters_per_unit') or rule.get('wire_meters_per_unit')
            if wire.get('conductor_count') is None and rule.get('conductor_count'):
                wire['conductor_count'] = rule['conductor_count']
                wire['conductor_count_assumed'] = True
                wire['estimated'] = True


def purchase_quantities(rows, materials, overrides, *, overrides_by_plan=None, catalogs_by_plan=None):
    catalog = {m['id']: m for m in materials}
    for override in [v for scope in [overrides,*((overrides_by_plan or {}).values())] for v in scope.values()]:
        if not any(row.get('material_id') == override['material_id'] for row in rows):
            raise ValueError('Purchase price does not match a selected material.')
    packages = {}
    for row in rows:
        scoped_overrides=(overrides_by_plan or {}).get(row.get('floor_plan_id'),overrides)
        kind = row.get('material_kind')
        if kind not in ('wire', 'conduit') or row.get('saved_route_version_id'):
            continue
        if row.get('material_conflict') or row.get('electrical_assignment_required'):
            row['line_total']=None
            continue
        product = (catalogs_by_plan or {}).get(row.get('floor_plan_id'),catalog).get(row.get('material_id'))
        if not product:
            continue
        if row.get('price_source') in ('client_upload', 'manual_override', 'item_override', 'manual_draft', 'custom') and not scoped_overrides.get(kind):
            continue
        override = scoped_overrides.get(kind)
        if override and override['material_id'] != product['id']:
            override = None  # An SKU-specific price never overwrites another route's conduit.
        factor = row.get('workspace_purchase_meters_per_unit') or (override.get('meters_per_unit') if override else None) or row.get('purchase_meters_per_unit') or row.get('wire_meters_per_unit')
        import re
        increment=re.search(r'order\s+in\s+(\d+(?:\.\d+)?)\s*m\s+lengths',product['name'],re.I)
        increment=Decimal(increment[1]) if product['unit']=='meter' and increment else None
        if product['unit'] == 'meter':
            factor = 1
        if not factor and product['unit']!='meter':
            row['purchase_input_required']='wire-length' if kind=='wire' else 'conduit-length'
        if row['unit'] != 'meter' or row.get('pricing_state') == 'conductor_count_required':
            continue
        if not factor or not math.isfinite(float(factor)) or factor <= 0:
            if product['unit'] != 'meter':
                row.update(line_total=None, pricing_state='purchase_unit_required')
            continue
        if not override and row.get('price_source') in ('manual_draft', 'custom', 'client_price_only', 'item_override'):
            continue
        price = Decimal(str(override['price'])) if override and override.get('price') is not None else Decimal(str(product['unit_price'])) if product['unit_price'] is not None else None
        if price is None:
            continue
        measured = Decimal(str(row['quantity']))
        quantity = (measured/increment).to_integral_value(rounding=ROUND_CEILING)*increment if increment else measured if product['unit'] == 'meter' else (measured / Decimal(str(factor))).to_integral_value(rounding=ROUND_CEILING)
        row.update(measured_meters=measured, purchase_meters_per_unit=factor, quantity=quantity,
                   unit=product['unit'], unit_price=price, currency='PHP' if override and override.get('price') is not None else product['currency'],
                   line_total=quantity * price, pricing_state='partial_measurement_priced' if row.get('missing_vertical_inputs') else 'priced',
                   price_source='manual_purchase' if override and override.get('price') is not None else row.get('price_source') or 'catalog')
        if product['unit'] != 'meter' or increment:
            if increment:row['purchase_increment_meters']=increment
            key=(product['id'],row.get('floor_id'),kind,row['currency'],str(price),factor,increment)
            packages.setdefault(key,[]).append(row)
    # Buy shared stock per floor rather than a new roll for every branch.
    for group in packages.values():
        total=sum((Decimal(str(row['measured_meters'])) for row in group),Decimal(0))
        increment=group[0].get('purchase_increment_meters')
        units=(total/(increment or Decimal(str(group[0]['purchase_meters_per_unit'])))).to_integral_value(rounding=ROUND_CEILING)
        if increment:units*=increment
        purchase_cost=units*Decimal(str(group[0]['unit_price']))
        remaining=purchase_cost
        for index,row in enumerate(group):
            row.update(shared_purchase_meters=total,shared_purchase_quantity=units,shared_purchase=len(group)>1)
            row['quantity']=units if index==0 else Decimal(0)
            row['line_total']=row['quantity']*row['unit_price']
            share=remaining if index==len(group)-1 else (purchase_cost*Decimal(str(row['measured_meters']))/total).quantize(Decimal('.00000001'),rounding=ROUND_DOWN) if total else Decimal(0)
            row['purchase_cost_share']=share
            remaining-=share
