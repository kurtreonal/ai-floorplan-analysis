"""One physical path, two purchase components; never infer product specifications."""
import re


def path_scope(row):
    return (row.get('floor_id'), row.get('floor_plan_id'), row.get('page_id'),
            row.get('candidate_run_id'), tuple(sorted(row.get('path_ids') or [row.get('path_id')])))


def paired_wiring_components(rows, materials):
    from app.services.draft_bom_service import material_key
    catalog = {m['id']: m for m in materials}
    by_name = {}
    for material in materials:
        by_name.setdefault(material_key(material['name']), []).append(material)
    groups, result = {}, []
    for source in rows:
        if source['kind'] != 'path' or source.get('saved_route_version_id'):
            result.append(source)
            continue
        row = dict(source)
        kind = row.get('material_kind')
        if kind not in ('wire', 'conduit'):
            material = catalog.get(row.get('preferred_material_id'))
            matches = by_name.get(material_key(row['name']), [])
            if material is None and len(matches) == 1:
                material = matches[0]
            category = material.get('category', '') if material else ''
            kind = 'wire' if re.search(r'\b(?:wire|wiring|cable|cables)\b', category, re.I) else 'conduit'
            if material is None and re.search(r'\b(?:wire|cable)\b', row['name'], re.I):
                kind = 'wire'
        row['material_kind'] = kind
        components = groups.setdefault(path_scope(row), {})
        # An explicit product/calculator selection replaces its unbound component,
        # rather than charging a second copy of the same physical path.
        if kind not in components or row.get('preferred_material_id') or row.get('custom_wire_price_per_meter') is not None:
            components[kind] = row
    for components in groups.values():
        source = next(iter(components.values()))
        for kind, label in (('conduit', 'Conduit'), ('wire', 'Wire/cable')):
            row = components.get(kind)
            if row is None:
                row = dict(source, material_kind=kind, name=f'{label} — wiring path {source["path_id"]}')
                for key in ('preferred_material_id', 'custom_wire_price_per_meter', 'wire_meters_per_unit'):
                    row.pop(key, None)
            if not row.get('paired_path_component'):
                row['basis'] += ' Wire/cable and conduit share this physical path; products and prices remain separate. Cable route metres are not a guessed conductor purchase count.'
            row['paired_path_component'] = True
            result.append(row)
    return result
