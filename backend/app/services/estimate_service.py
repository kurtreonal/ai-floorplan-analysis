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


def estimate_options(session, user, project_id):
    get_accessible_project(session, current_user=user, project_id=project_id)
    route = latest_route(session, project_id)
    stale = bool(route and current_layout_ids(session, project_id, [int(k) for k in route.layout_versions]) != route.layout_versions)
    grouped = components_for_route(session, user, project_id, route)[0] if route and not stale else {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    materials = []
    for material in repository.catalog(session):
        price = prices.latest_price(session, material.id, at=now)
        materials.append({"id": material.id, "code": material.code, "name": material.name, "unit": material.unit,
                          "has_price": bool(price and price.unit == material.unit), "currency": price.currency if price else None})
    return dict(route_version_id=route.id if route else None, stale=stale,
        floors=sorted(int(k) for k in route.layout_versions) if route else [],
        components=[grouped[k] for k in sorted(grouped)], materials=materials)


def generate_estimate(session, user, project_id, request):
    if user.role.name != "DESIGNER":
        raise EstimateError("AUTHORIZATION_DENIED")
    get_accessible_project(session, current_user=user, project_id=project_id)
    # Same project/floor lock order as route publication; no inference under locks.
    lock_context(session, project_id, repository.floor_ids(session, project_id))
    request_document = request.model_dump(mode="json")
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
    grouped, snapshots = components_for_route(session, user, project_id, route)
    if set(grouped) != {item.class_id for item in request.components}:
        raise EstimateError("COMPLETE_COMPONENT_MAPPING_REQUIRED")
    lengths = measure_material_lengths(RouteResult.model_validate(route.result), conductor_count=request.conductor_count)
    raw_lines = [(item.material_id, Decimal(grouped[item.class_id]["quantity"]) * item.units_per_symbol, False)
                 for item in request.components]
    raw_lines.extend([(request.conduit_material_id, Decimal(str(lengths.conduit_meters)), True),
                      (request.wire_material_id, Decimal(str(lengths.wire_meters)), True)])
    locked = {key: prices.lock_material(session, key) for key in sorted({item[0] for item in raw_lines})}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    lines, price_ids, currencies = [], [], set()
    with localcontext() as context:
        context.prec = 48
        for material_id, raw_quantity, is_length in raw_lines:
            material = locked[material_id]
            if material is None or not material.is_active:
                raise EstimateError("MATERIAL_UNAVAILABLE")
            if is_length and material.unit != "meter":
                raise EstimateError("MATERIAL_UNIT_MUST_BE_METER")
            price = prices.latest_price(session, material_id, at=now, lock=True)
            if price is None or price.unit != material.unit:
                raise EstimateError("MISSING_MATERIAL_PRICE")
            currencies.add(price.currency)
            quantity = raw_quantity.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            total = quantity * price.unit_price
            if quantity >= Decimal("1e12") or total >= Decimal("1e22"):
                raise EstimateError("ESTIMATE_NUMERIC_LIMIT")
            lines.append(dict(material_id=material.id, material_code=material.code, material_name=material.name,
                quantity=quantity, unit=material.unit, captured_unit_price=price.unit_price, line_total=total))
            price_ids.append(price.id)
        if len(currencies) != 1:
            raise EstimateError("MIXED_CURRENCIES")
        total = sum((line["line_total"] for line in lines), Decimal(0))
        if total >= Decimal("1e22"):
            raise EstimateError("ESTIMATE_NUMERIC_LIMIT")
    record = repository.save(session, dict(project_id=project_id, version_number=repository.next_version(session, project_id),
        created_by_user_id=user.id, currency=currencies.pop(), total=total), lines,
        dict(request_id=str(request.request_id), request_hash=request_hash, snapshot={
            "configuration": request_document, "layouts": snapshots, "route_version_id": route.id,
            "lengths": asdict(lengths), "price_revision_ids": price_ids,
            "scope": "Reviewed components on route floors plus one saved route; planning only.",
            "quantity_precision": "4 decimals, ROUND_HALF_UP; no waste or monetary rounding added"}))
    result = response(session, record)
    session.commit()
    return result
