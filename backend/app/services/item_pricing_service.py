"""Price existing identities with explicit compatible products; never infer circuits or quantities."""
from copy import deepcopy
from decimal import Decimal
from app.repositories import item_price_repository as repository
from app.repositories import project_pricing_repository as prices
from app.services import project_pricing_service as pricing
from app.services.material_workbook import WorkbookError
from app.services.product_compatibility import compatible_product


def device_key(floor_id, plan_id, symbol_id, page_id=None, candidate_run_id=None):
    return pricing._hash(['device', floor_id, plan_id, page_id, candidate_run_id, symbol_id])


def route_key(route_id, kind):
    return pricing._hash(['saved_route', route_id, kind])


def path_key(row, *, legacy=False):
    identity = ['path', row.get('floor_id'), row.get('floor_plan_id'), row.get('page_id'),
        row.get('candidate_run_id'), sorted(row.get('path_ids') or [])]
    return pricing._hash(identity if legacy else identity + [row.get('material_kind', 'path')])


def expand_items(rows):
    result = []
    for source in rows:
        ids = source.get('symbol_ids') or []
        for identity in ids if source['kind'] == 'device' else [None]:
            row = dict(source)
            if identity is not None:
                row.update(symbol_ids=[identity], quantity=Decimal(str(source['quantity'])) / len(ids))
                if source.get('line_total') is not None:
                    row['line_total']=Decimal(str(source['line_total'])) / len(ids)
                key = device_key(row.get('floor_id'), row.get('floor_plan_id'), identity, row.get('page_id'), row.get('candidate_run_id'))
            elif source.get('saved_route_version_id'):
                key = route_key(source['saved_route_version_id'], source['material_kind'])
            else:
                key = path_key(row)
            row['item_key'] = key
            row['item_kind'] = 'device' if source['kind'] == 'device' else source.get('material_kind', 'path')
            result.append(row)
    return result


def fingerprint(row, material):
    return pricing._hash([row['item_kind'], row['unit'], material['id'], material['code'], material['name'], material['unit']])


def assignment_quote(session, project_id, assignment, material, cache=None):
    if cache is None:
        cache = {}
    version_id = assignment['price_version_id']
    if version_id not in cache:
        cache[version_id] = prices.find(session, project_id, version_id)
    version = cache[version_id]
    quote = next((q for q in version.document['rows'] if q['row_id'] == assignment['price_row_id'] and not q['excluded']), None) if version else None
    if quote and (quote['material_id'], quote['catalog_code'], quote['catalog_name'], quote['catalog_unit']) == (
            material['id'], material['code'], material['name'], material['unit']):
        return quote


def apply_prices(session, project_id, result, materials):
    """Same read model in workspace/project BOM. Stale identities never inherit."""
    batch = repository.current(session, project_id)
    assignments = batch.document['assignments'] if batch else {}
    if not assignments:
        result['item_assignment_version'] = 0
        return result
    result['items'] = expand_items(result['items'])
    catalog = {m['id']: m for m in materials}
    quote_cache = {}
    for row in result['items']:
        assignment = assignments.get(row['item_key'])
        legacy = False
        if not assignment and row['kind'] == 'path' and not row.get('saved_route_version_id'):
            assignment = assignments.get(path_key(row, legacy=True))
            legacy = assignment is not None
        material = catalog.get(assignment.get('product_id') or row.get('material_id')) if assignment else None
        if not assignment:
            continue
        quote = assignment_quote(session, project_id, assignment, material, quote_cache) if material else None
        if legacy:
            version = quote_cache.get(assignment['price_version_id'])
            original = next((q for q in version.document['rows'] if q['row_id'] == assignment['price_row_id']), None) if version else None
            if material is None or original and original['material_id'] != material['id']:
                continue  # The old shared path key belongs to the other component.
        valid = material and quote and (not assignment.get('product_id') or compatible_product(row,material)) and (assignment['fingerprint'] == fingerprint(row, material)
            or legacy and assignment['fingerprint'] == fingerprint(dict(row, item_kind='path'), material))
        if not valid:
            row['item_price_warning'] = 'Saved price choice no longer matches this item. Review its material and unit.'
            row.update(pricing_state='item_price_review_required', unit_price=None, line_total=None, currency=None)
            continue
        factor = Decimal(str(row.get('wire_meters_per_unit') or 1)) if row['unit'] == 'meter' and material['unit'] != 'meter' else Decimal(1)
        amount = Decimal(quote['unit_price']) / Decimal(quote['units_per_purchase']) / factor
        row.update(unit_price=amount, currency=quote['currency'], price_source='item_project',
            project_price_version_id=assignment['price_version_id'], project_price_row_id=quote['row_id'],
            item_price_assignment_version=batch.version_number, price_revision_id=None)
        row.update(material_id=material['id'],material_name=material['name'])
        if row['line_total'] is not None or row['pricing_state'] in ('missing_price', 'missing_project_material_price','material_not_found','ambiguous_material'):
            row.update(line_total=Decimal(str(row['quantity'])) * amount, pricing_state='priced')
    totals = {}
    for row in result['items']:
        if row['line_total'] is not None:
            totals[row['currency']] = totals.get(row['currency'], Decimal(0)) + row['line_total']
    result.update(priced_subtotals=totals, unpriced_items=sum(r['line_total'] is None for r in result['items']),
        item_assignment_version=batch.version_number if batch else 0)
    return result


def inventory(session, user, project_id):
    pricing._access(session, user, project_id, write=True)
    from app.services.bom_service import reviewed_bom
    planning = reviewed_bom(session, user, project_id)['planning']
    rows = expand_items(planning['items'])
    planning['items'] = rows
    if len(rows) > 10000:
        raise WorkbookError('More than 10,000 saved BOM items. Split this project before applying item prices.')
    return planning


def options(session, user, project_id, price_version_id=None):
    planning = inventory(session, user, project_id)
    from app.repositories.estimate_repository import catalog
    materials = {m.id: dict(id=m.id, code=m.code, name=m.name, unit=m.unit,category=m.category or '') for m in catalog(session)}
    if price_version_id is not None:
        version=pricing.get_version(session,user,project_id,price_version_id)
        quotes=[q for q in version.document['rows'] if not q['excluded']]
        cache={}
        for row in planning['items']:
            key=(row['kind'],row.get('material_kind'),row['name'],row.get('material_name'),row.get('class_id'),row['unit'],row.get('material_id'),bool(row.get('material_conflict')),bool(row.get('electrical_assignment_required')))
            if key not in cache:
                cache[key]=[q['row_id'] for q in quotes if q['material_id'] in materials and compatible_product(row,materials[q['material_id']])]
            row['compatible_prices']=cache[key]
    return dict(items=planning['items'], assignment_version=planning['item_assignment_version'],
        floors=sorted({r['floor_id'] for r in planning['items'] if r.get('floor_id')}),
        materials=list(materials.values()))


def preview(session, user, project_id, selection):
    planning = inventory(session, user, project_id)
    version = pricing.get_version(session, user, project_id, selection.price_version_id)
    quotes = {r['row_id']:r for r in version.document['rows'] if not r['excluded']}
    bindings = {b.item_key:b.price_row_id for b in selection.bindings}
    product_bindings={b.item_key:b.material_id for b in selection.bindings if b.material_id is not None}
    quote_ids = set(bindings.values()) - {None} if bindings else {selection.price_row_id}
    if not quote_ids <= quotes.keys():
        raise WorkbookError('Choose an available client price entry.')
    all_rows = planning['items']
    rows = [r for r in all_rows if selection.scope == 'project' or r.get('floor_id') == selection.floor_id]
    keys = set(bindings) if bindings else set(selection.item_keys)
    if keys and not keys <= {r['item_key'] for r in rows}:
        raise pricing.PricingConflict('Selected items changed or fall outside this scope. Reload the saved items.')
    if selection.mode == 'selected':
        if not keys:
            raise pricing.PricingConflict('Selected items changed or fall outside this scope. Reload the saved items.')
        rows = [r for r in rows if r['item_key'] in keys]
    else:
        rows = [r for r in rows if r['kind'] == 'path']
    materials = {m.id:m for m in prices.materials(session, ids=sorted({quotes[q]['material_id'] for q in quote_ids}), lock=True)}
    affected, skipped = [], []
    if selection.mode == 'all_wiring' and selection.scope == 'floor':
        skipped.extend(dict(item_key=r['item_key'], name=r['name'], reason='Project-wide route has no single floor scope; use Entire project.')
            for r in all_rows if r['kind'] == 'path' and r.get('floor_id') is None)
    for row in rows:
        quote = quotes.get(bindings.get(row['item_key']) if bindings else selection.price_row_id)
        if selection.mode == 'all_wiring' and bindings and row['item_key'] not in bindings:
            candidates = [quotes[q] for q in quote_ids if quotes[q]['material_id'] == row.get('material_id')]
            quote = candidates[0] if len(candidates) == 1 else None
        if quote is None:
            skipped.append(dict(item_key=row['item_key'], name=row['name'], reason='No compatible imported product selected.'))
            continue
        material = materials.get(quote['material_id'])
        identity = dict(id=material.id, code=material.code, name=material.name, unit=material.unit) if material and material.is_active else None
        compatible = identity and (quote['catalog_code'], quote['catalog_name'], quote['catalog_unit']) == (material.code, material.name, material.unit)
        explicit_product=product_bindings.get(row['item_key'])
        proposed=dict(id=material.id,name=material.name,unit=material.unit,category=material.category or '') if material else {}
        product_confirmed=explicit_product==quote['material_id'] and compatible_product(row,proposed)
        reason = None
        if not compatible:
            reason = 'Client price entry no longer matches the active catalog product.'
        elif row.get('material_id') is None and not product_confirmed:
            reason = 'Choose the product/size for this item before applying its price.'
        elif row.get('material_id') != quote['material_id'] and not product_confirmed:
            reason = 'This price entry is for a different product/specification.'
        elif row['unit'] != material.unit and not (row['unit']=='piece' and material.unit=='unit') and not (row['unit'] == 'meter' and row.get('material_kind') == 'wire' and row.get('wire_meters_per_unit')):
            reason = 'Purchase unit or conversion is unresolved.'
        elif row.get('material_conflict') or row.get('electrical_assignment_required'):
            reason = 'Resolve this network’s material/circuit assignment first.'
        if reason:
            skipped.append(dict(item_key=row['item_key'], name=row['name'], reason=reason))
            continue
        factor = Decimal(str(row.get('wire_meters_per_unit') or 1)) if row['unit'] == 'meter' and material.unit != 'meter' else Decimal(1)
        amount = Decimal(quote['unit_price']) / Decimal(quote['units_per_purchase']) / factor
        affected.append(dict(item_key=row['item_key'], name=row['name'], floor_id=row.get('floor_id'),
            item_kind=row['item_kind'], quantity=str(row['quantity']), unit=row['unit'], previous_price=str(row['unit_price']) if row['unit_price'] is not None else None,
            previous_currency=row['currency'], unit_price=str(amount), currency=quote['currency'],
            previous_total=str(row['line_total']) if row['line_total'] is not None else None,
            line_total=str(Decimal(str(row['quantity'])) * amount) if row['line_total'] is not None or row['pricing_state'] in ('missing_price','missing_project_material_price','material_not_found','ambiguous_material') else None,
            fingerprint=fingerprint(row, identity), price_row_id=quote['row_id'], product_id=material.id if explicit_product else None))
    content = dict(scope=selection.model_dump(mode='json'), affected=affected, skipped=skipped,
        sources=planning['sources'], assignment_version=planning['item_assignment_version'])
    return content | dict(preview_token=pricing._hash(content), ready=bool(affected))


def apply(session, user, project_id, request):
    pricing._access(session, user, project_id, write=True)
    from app.repositories.routing_repository import lock_context
    from app.repositories.estimate_repository import floor_ids
    lock_context(session, project_id, floor_ids(session, project_id))
    request_hash = pricing._hash(request.model_dump(mode='json', exclude={'bindings'} if not request.bindings else set()))
    previous = repository.retry(session, project_id, str(request.request_id))
    if previous:
        if previous.request_hash != request_hash:
            raise pricing.PricingConflict('Retry inputs changed. Preview again.')
        session.commit()
        return dict(id=previous.id, version_number=previous.version_number)
    from app.schemas.item_pricing import ItemPriceSelection
    result = preview(session, user, project_id, ItemPriceSelection.model_validate(request.model_dump(exclude={'request_id', 'preview_token'})))
    if not result['ready'] or result['preview_token'] != request.preview_token:
        raise pricing.PricingConflict('Saved items, prices or scope changed. Preview again.')
    current = repository.current(session, project_id)
    assignments = deepcopy(current.document['assignments']) if current else {}
    for row in result['affected']:
        assignments[row['item_key']] = dict(price_version_id=request.price_version_id,
            price_row_id=row['price_row_id'], fingerprint=row['fingerprint'], **({'product_id':row['product_id']} if row.get('product_id') else {}))
    if len(assignments) > 20000:
        raise WorkbookError('This project has reached the saved item-price limit.')
    record = repository.append(session, project_id=project_id, version_number=(current.version_number if current else 0) + 1,
        created_by_user_id=user.id, request_id=str(request.request_id), request_hash=request_hash,
        document=dict(assignments=assignments, application=result))
    session.commit()
    return dict(id=record.id, version_number=record.version_number)
