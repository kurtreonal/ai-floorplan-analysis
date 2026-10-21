"""Explicit planning estimates; no inferred material or electrical rules."""
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP
from hashlib import sha256
import json

from app.repositories import estimate_repository as repository
from app.repositories import material_price_repository as prices
from app.repositories.routing_repository import lock_context, latest_route, current_layout_ids
from app.routing.contracts import RouteResult
from app.routing.measurements import measure_material_lengths
from app.services.material_quantity_service import retrieve_component_quantities
from app.services.project_service import get_accessible_project
from app.services import project_pricing_service as project_pricing


class EstimateError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def response(session, record):
    provenance = repository.source(session, record.id)
    return {key: getattr(record, key) for key in ("id", "project_id", "version_number", "created_by_user_id", "created_at", "currency", "total")} | {
        "items": repository.items(session, record.id), "source": provenance.snapshot if provenance else None}


def retrieve_estimate(session, user, project_id, estimate_id):
    get_accessible_project(session, current_user=user, project_id=project_id)
    record = repository.find_estimate(session, project_id, estimate_id)
    if record is None:
        raise EstimateError("ESTIMATE_NOT_FOUND")
    return response(session, record)


def retrieve_estimates(session, user, project_id):
    get_accessible_project(session, current_user=user, project_id=project_id)
    return [response(session, record) for record in repository.list_estimates(session, project_id)]


def components_for_route(session, user, project_id, route):
    grouped, snapshots = {}, {}
    for floor in sorted(int(key) for key in route.layout_versions):
        quantities = retrieve_component_quantities(session, current_user=user, project_id=project_id, project_floor_id=floor)
        if quantities.layout_version_id != route.layout_versions[str(floor)]:
            raise EstimateError("STALE_ROUTE")
        snapshots[str(floor)] = asdict(quantities)
        for item in quantities.components:
            existing = grouped.setdefault(item.class_id, {"class_id": item.class_id, "class_name": item.class_name, "quantity": 0})
            if existing["class_name"] != item.class_name:
                raise EstimateError("CONFLICTING_CLASS_NAMES")
            existing["quantity"] += item.quantity
    return grouped, snapshots


def estimate_options(session, user, project_id, project_price_version_id=None):
    get_accessible_project(session, current_user=user, project_id=project_id)
    route = latest_route(session, project_id)
    route_blocker = 'CIRCUIT_ESTIMATION_NOT_CONFIGURED' if route and route.result.get('status') == 'saved_planning' else None
    stale = bool(route and current_layout_ids(session, project_id, [int(k) for k in route.layout_versions]) != route.layout_versions)
    grouped = components_for_route(session, user, project_id, route)[0] if route and not stale and not route_blocker else {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    materials = []
    project_version = project_pricing.get_version(session, user, project_id, project_price_version_id) if project_price_version_id else None
    project_rows = project_pricing.accepted_rows(project_version) if project_version else {}
    for material in repository.catalog(session):
        price = prices.latest_price(session, material.id, at=now) if project_version is None else None
        quote = project_rows.get(material.id)
        materials.append({"id": material.id, "code": material.code, "name": material.name, "unit": material.unit,
                          "has_price": bool(quote and quote['catalog_unit'] == material.unit) if project_version else bool(price and price.unit == material.unit),
                          "currency": quote['currency'] if quote else price.currency if price else None,
                          "price_unit": quote['unit'] if quote else material.unit})
    return dict(route_version_id=route.id if route else None, stale=stale, route_blocker=route_blocker,
        floors=sorted(int(k) for k in route.layout_versions) if route else [],
        components=[grouped[k] for k in sorted(grouped)], materials=materials,
        price_source='project' if project_version else 'catalog', project_price_version_id=project_price_version_id)


def generate_estimate(session, user, project_id, request):
    if user.role.name != "DESIGNER":
        raise EstimateError("AUTHORIZATION_DENIED")
    get_accessible_project(session, current_user=user, project_id=project_id)
    # Same project/floor lock order as route publication; no inference under locks.
    lock_context(session, project_id, repository.floor_ids(session, project_id))
    request_document = request.model_dump(mode="json", exclude={'price_source','project_price_version_id'} if request.price_source == 'catalog' else set())
    request_hash = sha256(json.dumps(request_document, sort_keys=True).encode()).hexdigest()
    retry = repository.retry(session, project_id, str(request.request_id))
    if retry:
        if retry.request_hash != request_hash:
            raise EstimateError("ESTIMATE_RETRY_CONFLICT")
        result = retrieve_estimate(session, user, project_id, retry.estimate_id)
        session.commit()
        return result
    route = latest_route(session, project_id, lock=True)
    if route is None or route.id != request.route_version_id:
        raise EstimateError("STALE_ROUTE")
    if current_layout_ids(session, project_id, [int(k) for k in route.layout_versions], lock=True) != route.layout_versions:
        raise EstimateError("STALE_ROUTE")
    if route.result.get('status') == 'saved_planning':
        raise EstimateError('CIRCUIT_ESTIMATION_NOT_CONFIGURED')
    grouped, snapshots = components_for_route(session, user, project_id, route)
    project_version = project_pricing.get_version(session, user, project_id, request.project_price_version_id) if request.price_source == 'project' else None
    project_rows = project_pricing.accepted_rows(project_version) if project_version else {}
    if set(grouped) != {item.class_id for item in request.components}:
        raise EstimateError("COMPLETE_COMPONENT_MAPPING_REQUIRED")
    lengths = measure_material_lengths(RouteResult.model_validate(route.result), conductor_count=request.conductor_count)
    raw_lines = [(item.material_id, Decimal(grouped[item.class_id]["quantity"]) * item.units_per_symbol, None, False)
                 for item in request.components]
    raw_lines.extend([(request.conduit_material_id, Decimal(str(lengths.conduit_meters)), request.conduit_meters_per_unit or Decimal(1), request.conduit_meters_per_unit is None),
                      (request.wire_material_id, Decimal(str(lengths.wire_meters)), request.wire_meters_per_unit or Decimal(1), request.wire_meters_per_unit is None)])
    raw_lines.extend((item.material_id, item.quantity, None, False) for item in request.additional_materials)
    from app.repositories.item_price_repository import current as current_item_prices
    from app.services.item_pricing_service import device_key, route_key, assignment_quote, fingerprint
    from app.models import LayoutVersion
    item_prices = current_item_prices(session, project_id)
    assignments = item_prices.document['assignments'] if item_prices else {}
    client_items = {}
    from app.repositories.project_pricing_repository import latest_automatic
    if any(a.get('source_kind')=='client_product' for a in assignments.values()) or latest_automatic(session,project_id):
        from app.services.item_pricing_service import inventory
        client_items={row['item_key']:row for row in inventory(session,user,project_id)['items']}
        # Compatibility-derived rates from an older upload are still quoted
        # client prices, never a reason to fall back silently to catalog prices.
        assignments=dict(assignments)
        for key,row in client_items.items():
            if key not in assignments and row.get('client_price_only'):
                from app.services.automatic_client_pricing import target_fingerprint
                assignments[key]=dict(source_kind='client_product',fingerprint=target_fingerprint(row),
                    price_version_id=row['project_price_version_id'],price_row_id=row['project_price_row_id'],
                    price_row_ids=row['client_price_row_ids'],price_only=True)
    item_keys = [None] * len(raw_lines)
    # Split only explicitly priced existing devices. Unselected grouping and
    # quantity arithmetic stay unchanged; a new symbol has a different key.
    device_lines, device_keys = [], []
    for binding, line in zip(request.components, raw_lines):
        keys = []
        for floor_id, snapshot in snapshots.items():
            layout = session.get(LayoutVersion, snapshot['layout_version_id'])
            for component in snapshot['components']:
                if component['class_id'] == binding.class_id:
                    keys.extend(device_key(int(floor_id), layout.floor_plan_id, symbol) for symbol in component['symbol_ids'])
        if any(key in assignments for key in keys):
            device_lines.extend((binding.material_id, binding.units_per_symbol, None, False) for key in keys)
            device_keys.extend(keys)
        else:
            device_lines.append(line); device_keys.append(None)
    offset = len(request.components)
    raw_lines = device_lines + raw_lines[offset:]
    item_keys = device_keys + [route_key(route.id, 'conduit'), route_key(route.id, 'wire')] + [None] * len(request.additional_materials)
    locked = {key: prices.lock_material(session, key) for key in sorted({item[0] for item in raw_lines})}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lines, price_ids, currencies, price_sources = [], [], set(), []
    item_quote_cache = {}
    with localcontext() as context:
        context.prec = 48
        for line_index, (material_id, raw_quantity, meters_per_unit, meter_required) in enumerate(raw_lines):
            material = locked[material_id]
            if material is None or not material.is_active:
                raise EstimateError("MATERIAL_UNAVAILABLE")
            if meters_per_unit is not None:
                if material.unit != 'meter' and meter_required:
                    raise EstimateError('MATERIAL_UNIT_MUST_BE_METER')
                if material.unit == 'meter' and meters_per_unit != 1:
                    raise EstimateError('METER_UNIT_CONVERSION_MUST_BE_ONE')
                raw_quantity /= meters_per_unit
            assignment = assignments.get(item_keys[line_index])
            client_quote = None
            if assignment and assignment.get('source_kind')=='client_product':
                from app.services.automatic_client_pricing import quote_for
                target=client_items.get(item_keys[line_index])
                client_quote=quote_for(session,project_id,assignment,target,item_quote_cache) if target else None
                if client_quote is None or target['line_total'] is None:
                    raise EstimateError('ITEM_PRICE_ASSIGNMENT_STALE')
                raw_quantity=Decimal(str(target['quantity']))/Decimal(client_quote['units_per_purchase'])
                unit_price,currency,unit=Decimal(client_quote['unit_price']),client_quote['currency'],client_quote['unit']
                price_sources.append(dict(material_id=material_id,kind='client_upload',item_key=item_keys[line_index],
                    project_price_version_id=assignment['price_version_id'],row_id=client_quote['row_id'],
                    catalog_unit=client_quote['quantity_unit'],units_per_purchase=client_quote['units_per_purchase'],
                    quoted_unit=unit,client_product_name=client_quote['name'],client_product_code=client_quote['code'],
                    price_only=bool(client_quote.get('price_only')),product_options=client_quote.get('product_options',[])))
            elif assignment:
                identity = dict(id=material.id, code=material.code, name=material.name, unit=material.unit)
                quote = assignment_quote(session, project_id, assignment, identity, item_quote_cache)
                kind = 'device' if line_index < len(device_lines) else 'conduit' if line_index == len(device_lines) else 'wire'
                if quote is None or fingerprint(dict(item_kind=kind, unit=material.unit), identity) != assignment['fingerprint']:
                    raise EstimateError('ITEM_PRICE_ASSIGNMENT_STALE')
                raw_quantity /= Decimal(quote['units_per_purchase'])
                unit_price, currency, unit = Decimal(quote['unit_price']), quote['currency'], quote['unit']
                price_sources.append(dict(material_id=material_id, kind='item_project', item_key=item_keys[line_index],
                    project_price_version_id=assignment['price_version_id'], row_id=quote['row_id'],
                    catalog_unit=quote['catalog_unit'], units_per_purchase=quote['units_per_purchase'], quoted_unit=unit))
            elif project_version:
                quote = project_rows.get(material_id)
                if quote is None:
                    raise EstimateError('MISSING_PROJECT_MATERIAL_PRICE')
                if (quote['catalog_unit'], quote['catalog_code'], quote['catalog_name']) != (material.unit, material.code, material.name):
                    raise EstimateError('PROJECT_MATERIAL_IDENTITY_CHANGED')
                raw_quantity /= Decimal(quote['units_per_purchase'])
                unit_price, currency, unit = Decimal(quote['unit_price']), quote['currency'], quote['unit']
                price_sources.append(dict(material_id=material_id, kind='project', row_id=quote['row_id'],
                    catalog_unit=quote['catalog_unit'], units_per_purchase=quote['units_per_purchase'], quoted_unit=unit))
            else:
                price = prices.latest_price(session, material_id, at=now, lock=True)
                if price is None or price.unit != material.unit:
                    raise EstimateError("MISSING_MATERIAL_PRICE")
                unit_price, currency, unit = price.unit_price, price.currency, material.unit
                price_ids.append(price.id)
                price_sources.append(dict(material_id=material_id, kind='catalog', catalog_unit=unit,
                    units_per_purchase='1', quoted_unit=unit, price_revision_id=price.id))
            currencies.add(currency)
            quantity = raw_quantity.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            total = quantity * unit_price
            if quantity >= Decimal("1e12") or total >= Decimal("1e22"):
                raise EstimateError("ESTIMATE_NUMERIC_LIMIT")
            lines.append(dict(material_id=material.id, material_code=client_quote['code'] or material.code if client_quote else material.code,
                material_name=client_quote['name'] if client_quote else material.name,
                quantity=quantity, unit=unit, captured_unit_price=unit_price, line_total=total))
        if len(currencies) != 1:
            raise EstimateError("MIXED_CURRENCIES")
        # Match the stored numeric scale on the initial response and reload.
        # Products already have at most eight decimals; this only pads zeros.
        total = sum((line["line_total"] for line in lines), Decimal(0)).quantize(Decimal('0.00000001'))
        if total >= Decimal("1e22"):
            raise EstimateError("ESTIMATE_NUMERIC_LIMIT")
    record = repository.save(session, dict(project_id=project_id, version_number=repository.next_version(session, project_id),
        created_by_user_id=user.id, currency=currencies.pop(), total=total), lines,
        dict(request_id=str(request.request_id), request_hash=request_hash, snapshot={
            "configuration": request_document, "layouts": snapshots, "route_version_id": route.id,
            "lengths": asdict(lengths), "price_revision_ids": price_ids,
            "price_source": request.price_source, "price_sources": price_sources,
            "item_price_assignment_version": item_prices.version_number if item_prices else None,
            "project_pricing": dict(id=project_version.id, version_number=project_version.version_number,
                filename=project_version.filename, file_sha256=project_version.file_sha256, kind=project_version.kind,
                document=project_version.document) if project_version else None,
            "scope": "Reviewed components on route floors plus one saved route; planning only.",
            "quantity_precision": "4 decimals, ROUND_HALF_UP; no waste or monetary rounding added"}))
    result = response(session, record)
    session.commit()
    return result
