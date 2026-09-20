from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from app.api.dependencies import get_current_user
from app.models import Estimate, EstimateSource, Material, MaterialPrice
from app.schemas.estimate import EstimateWrite
from app.services.estimate_service import generate_estimate, retrieve_estimate, EstimateError
from tests.test_routing_api import context


@pytest.fixture
def source_schema():
    from app.core.database import get_engine
    engine = get_engine()
    assert engine.url.database == "ved_electrical_verify" and engine.url.username == "ved_test"
    EstimateSource.__table__.create(engine, checkfirst=True)


@pytest.fixture
def estimate_context(source_schema, context):
    client, url, route_request, session, layout, app, other, admin = context
    saved = client.post(url, json=route_request).json()
    materials = [Material(code=uuid4().hex, name="Synthetic", unit=unit, category="Test") for unit in ("piece", "meter", "meter")]
    session.add_all(materials)
    session.flush()
    now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=2)
    for material, amount in zip(materials, (10, 3, 2)):
        session.add(MaterialPrice(material_id=material.id, version_number=1, unit_price=amount, unit=material.unit,
            currency="PHP", effective_at=now, changed_by_user_id=admin.id))
    session.commit()
    request = dict(request_id=str(uuid4()), route_version_id=saved["id"],
        components=[dict(class_id=key, material_id=materials[0].id, units_per_symbol="1") for key in (2, 7)],
        conduit_material_id=materials[1].id, wire_material_id=materials[2].id,
        conductor_count=3, mappings_confirmed=True)
    return context, request, materials


def test_known_answer_snapshot_and_retry(estimate_context):
    context, payload, materials = estimate_context
    _, _, _, session, layout, app, _, _ = context
    owner = app.dependency_overrides[get_current_user]()
    request = EstimateWrite.model_validate(payload)
    first = generate_estimate(session, owner, layout.project_id, request)
    assert first["total"] == Decimal("38")
    assert [item.quantity for item in first["items"]] == [1, 1, 2, 6]
    assert [item.line_total for item in first["items"]] == [10, 10, 6, 12]
    assert generate_estimate(session, owner, layout.project_id, request)["id"] == first["id"]
    assert session.scalar(select(func.count()).select_from(Estimate).where(Estimate.project_id == layout.project_id)) == 1
    old_price = session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[0].id))
    old_price.unit_price = 99
    materials[0].name = "Changed"
    session.commit()
    old = retrieve_estimate(session, owner, layout.project_id, first["id"])
    assert old["total"] == 38 and old["items"][0].captured_unit_price == 10
    assert old["source"]["layouts"][str(layout.project_floor_id)]["layout_version_id"] == layout.id
    conflict = request.model_copy(update={"conductor_count": 4})
    with pytest.raises(EstimateError, match="RETRY_CONFLICT"):
        generate_estimate(session, owner, layout.project_id, conflict)


@pytest.mark.parametrize("defect,code", [("mapping", "COMPLETE_COMPONENT"), ("route", "STALE_ROUTE"),
    ("price", "MISSING_MATERIAL_PRICE"), ("currency", "MIXED_CURRENCIES"), ("unit", "MATERIAL_UNIT"), ("layout", "STALE_ROUTE")])
def test_failures_do_not_create_partial_estimate(estimate_context, defect, code):
    context, payload, materials = estimate_context
    _, _, _, session, layout, app, _, _ = context
    if defect == "mapping": payload["components"] = []
    if defect == "route": payload["route_version_id"] += 100
    if defect == "price":
        price = session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[0].id))
        session.delete(price)
    if defect == "currency":
        session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[0].id)).currency = "USD"
    if defect == "unit": payload["wire_material_id"] = materials[0].id
    if defect == "layout": layout.is_current = None
    session.flush()
    with pytest.raises(EstimateError, match=code):
        generate_estimate(session, app.dependency_overrides[get_current_user](), layout.project_id, EstimateWrite.model_validate(payload))
    assert session.scalar(select(func.count()).select_from(Estimate).where(Estimate.project_id == layout.project_id)) == 0


def test_generation_denies_admin_and_other_owner(estimate_context):
    from app.services.project_service import ProjectNotFoundError
    context, payload, _ = estimate_context
    _, _, _, session, layout, _, other, admin = context
    with pytest.raises(EstimateError, match="AUTHORIZATION_DENIED"):
        generate_estimate(session, admin, layout.project_id, EstimateWrite.model_validate(payload))
    with pytest.raises(ProjectNotFoundError):
        generate_estimate(session, other, layout.project_id, EstimateWrite.model_validate(payload))
