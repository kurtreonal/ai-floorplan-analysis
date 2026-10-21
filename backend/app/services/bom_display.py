"""Compact read-only BOM groups; never merge electrical identities or geometry."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json


def _signature(row):
    name = row['name']
    if row.get('paired_path_component') and ' — wiring path ' in name:
        name = name.split(' — wiring path ', 1)[0]
    fields = ('kind','class_id','material_kind','material_id','material_name',
        'client_product_name','client_product_code','client_product_specification',
        'client_price_only','client_product_options','unit','currency','client_price_unit',
        'pricing_state','installation_method','origin','material_conflict')
    values = {k: row.get(k) for k in fields}
    values['name'] = name
    for key in ('unit_price','client_unit_price'):
        values[key] = str(Decimal(str(row[key])).normalize()) if row.get(key) is not None else None
    return values


def grouped_rows(rows):
    # Pair wire/conduit for one existing physical takeoff row before grouping
    # similar purchases. Do NOT union spans, circuits, terminals or saved paths.
    entries, paths = [], {}
    for index, row in enumerate(rows):
        if row['kind'] == 'device':
            entries.append([row])
        else:
            identity = (row.get('floor_id'),row.get('floor_plan_id'),row.get('page_id'),
                row.get('candidate_run_id'),row.get('saved_route_version_id'),row.get('origin'),
                tuple(sorted(row.get('path_ids') or [row.get('path_id') or f'row:{index}'])))
            buckets = paths.setdefault(identity,[])
            bucket = next((b for b in buckets if all(r.get('material_kind')!=row.get('material_kind') for r in b)),None)
            if bucket is None:
                bucket = []
                buckets.append(bucket)
            bucket.append(row)
    entries.extend(bucket for buckets in paths.values() for bucket in buckets)
    groups = {}
    for entry in entries:
        entry = sorted(entry,key=lambda r:r.get('material_kind') or '')
        signature = json.dumps([_signature(r) for r in entry],sort_keys=True,default=str)
        key = sha256(signature.encode()).hexdigest()
        if key not in groups:
            components = []
            for row in entry:
                components.append(dict(deepcopy(row),quantity=Decimal(0),
                    line_total=Decimal(0) if row.get('line_total') is not None else None))
            method = {'concealed_in_ceiling':'Ceiling','concealed_under_floor':'Under floor'}.get(entry[0].get('installation_method'))
            name = entry[0]['name'] if entry[0]['kind']=='device' else 'Wiring paths'+(' — '+method if method else '')
            groups[key] = dict(key=key,kind=entry[0]['kind'],name=name,components=components,members=[],costs={})
        group = groups[key]
        for component,row in zip(group['components'],entry):
            component['quantity'] += Decimal(str(row['quantity']))
            if component['line_total'] is not None:
                if row.get('line_total') is None:
                    component['line_total'] = None
                else:
                    component['line_total'] += Decimal(str(row['line_total']))
            if row.get('line_total') is not None:
                currency = row['currency']
                group['costs'][currency] = group['costs'].get(currency,Decimal(0)) + Decimal(str(row['line_total']))
        first = entry[0]
        ids = first.get('symbol_ids') if first['kind']=='device' else first.get('path_ids') or [first.get('path_id') or f'route {first.get("saved_route_version_id")}']
        group['members'].extend(dict(id=identity,floor_id=first.get('floor_id'),
            floor_plan_id=first.get('floor_plan_id'),page_id=first.get('page_id'),
            candidate_run_id=first.get('candidate_run_id')) for identity in ids or [])
    for group in groups.values():
        group['incomplete'] = any(r['line_total'] is None for r in group['components'])
    return list(groups.values())
