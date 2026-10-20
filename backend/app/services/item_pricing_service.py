"""Price existing identities only; never choose products, circuits or quantities."""
from copy import deepcopy
from decimal import Decimal
from app.repositories import item_price_repository as repository
from app.repositories import project_pricing_repository as prices
from app.services import project_pricing_service as pricing
from app.services.material_workbook import WorkbookError


def device_key(floor_id, plan_id, symbol_id, page_id=None, candidate_run_id=None):
    return pricing._hash(['device', floor_id, plan_id, page_id, candidate_run_id, symbol_id])


def route_key(route_id, kind):
    return pricing._hash(['saved_route', route_id, kind])


def expand_items(rows):
    result = []
    for source in rows:
        ids = source.get('symbol_ids') or []
        for identity in ids if source['kind'] == 'device' else [None]:
            row = dict(source)
            if identity is not None:
                row.update(symbol_ids=[identity], quantity=Decimal(str(source['quantity'])) / len(ids))
                key = device_key(row.get('floor_id'), row.get('floor_plan_id'), identity, row.get('page_id'), row.get('candidate_run_id'))
            elif source.get('saved_route_version_id'):
                key = route_key(source['saved_route_version_id'], source['material_kind'])
            else:
                key = pricing._hash(['path', row.get('floor_id'), row.get('floor_plan_id'), row.get('page_id'), row.get('candidate_run_id'), sorted(row.get('path_ids') or [])])
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
        material = catalog.get(row.get('material_id'))
        if not assignment:
            continue
        quote = assignment_quote(session, project_id, assignment, material, quote_cache) if material else None
        valid = material and assignment['fingerprint'] == fingerprint(row, material) and quote
        if not valid:
            row['item_price_warning'] = 'Saved price choice no longer matches this item. Review its material and unit.'
            row.update(pricing_state='item_price_review_required', unit_price=None, line_total=None, currency=None)
            continue
        factor = Decimal(str(row.get('wire_meters_per_unit') or 1)) if row['unit'] == 'meter' and material['unit'] != 'meter' else Decimal(1)
        amount = Decimal(quote['unit_price']) / Decimal(quote['units_per_purchase']) / factor
        row.update(unit_price=amount, currency=quote['currency'], price_source='item_project',
            project_price_version_id=assignment['price_version_id'], project_price_row_id=quote['row_id'],
            item_price_assignment_version=batch.version_number, price_revision_id=None)
        if row['line_total'] is not None or row['pricing_state'] in ('missing_price', 'missing_project_material_price'):
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


def options(session, user, project_id):
    planning = inventory(session, user, project_id)
    from app.repositories.estimate_repository import catalog
    materials = {m.id: dict(id=m.id, code=m.code, name=m.name, unit=m.unit) for m in catalog(session)}
    return dict(items=planning['items'], assignment_version=planning['item_assignment_version'],
        floors=sorted({r['floor_id'] for r in planning['items'] if r.get('floor_id')}),
        materials=list(materials.values()))


def preview(session, user, project_id, selection):
    planning = inventory(session, user, project_id)
    version = pricing.get_version(session, user, project_id, selection.price_version_id)
    quote = next((r for r in version.document['rows'] if r['row_id'] == selection.price_row_id and not r['excluded']), None)
    if quote is None:
        raise WorkbookError('Choose an available client price entry.')
    all_rows = planning['items']
    rows = [r for r in all_rows if selection.scope == 'project' or r.get('floor_id') == selection.floor_id]
    if selection.mode == 'selected':
        if not set(selection.item_keys) <= {r['item_key'] for r in rows}:
            raise pricing.PricingConflict('Selected items changed or fall outside this scope. Reload the saved items.')
        rows = [r for r in rows if r['item_key'] in selection.item_keys]
    else:
        rows = [r for r in rows if r['kind'] == 'path']
    from app.repositories.material_price_repository import lock_material
    material = lock_material(session, quote['material_id'])
    identity = dict(id=material.id, code=material.code, name=material.name, unit=material.unit) if material and material.is_active else None
    compatible = identity and (quote['catalog_code'], quote['catalog_name'], quote['catalog_unit']) == (material.code, material.name, material.unit)
    affected, skipped = [], []
    if selection.mode == 'all_wiring' and selection.scope == 'floor':
        skipped.extend(dict(item_key=r['item_key'], name=r['name'], reason='Project-wide route has no single floor scope; use Entire project.')
            for r in all_rows if r['kind'] == 'path' and r.get('floor_id') is None)
    for row in rows:
        reason = None
        if not compatible or row.get('material_id') != quote['material_id']:
            reason = 'Different or unresolved material/specification.'
        elif row['unit'] != material.unit and not (row['unit'] == 'meter' and row.get('material_kind') == 'wire' and row.get('wire_meters_per_unit')):
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
            line_total=str(Decimal(str(row['quantity'])) * amount) if row['line_total'] is not None or row['pricing_state'] in ('missing_price','missing_project_material_price') else None,
            fingerprint=fingerprint(row, identity)))
    content = dict(scope=selection.model_dump(mode='json'), affected=affected, skipped=skipped,
        sources=planning['sources'], assignment_version=planning['item_assignment_version'])
    return content | dict(preview_token=pricing._hash(content), ready=bool(affected))


def apply(session, user, project_id, request):
    pricing._access(session, user, project_id, write=True)
    from app.repositories.routing_repository import lock_context
    from app.repositories.estimate_repository import floor_ids
    lock_context(session, project_id, floor_ids(session, project_id))
    request_hash = pricing._hash(request.model_dump(mode='json'))
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
            price_row_id=request.price_row_id, fingerprint=row['fingerprint'])
    if len(assignments) > 20000:
        raise WorkbookError('This project has reached the saved item-price limit.')
    record = repository.append(session, project_id=project_id, version_number=(current.version_number if current else 0) + 1,
        created_by_user_id=user.id, request_id=str(request.request_id), request_hash=request_hash,
        document=dict(assignments=assignments, application=result))
    session.commit()
    return dict(id=record.id, version_number=record.version_number)
