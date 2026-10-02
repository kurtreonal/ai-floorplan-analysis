from sqlalchemy import select
from app.api.dependencies import get_current_user
from app.models import MaterialPrice
from tests.test_estimates import estimate_context, source_schema
from tests.test_routing_api import context


def test_api_snapshots_options_and_access(estimate_context):
    context, payload, materials = estimate_context
    client, _, _, session, layout, app, other, admin = context
    url = f"/api/projects/{layout.project_id}/estimates"
    assert client.get(url).json() == []
    options = client.get(f"/api/projects/{layout.project_id}/estimate-options")
    assert options.status_code == 200
    assert options.json()["route_version_id"] == payload["route_version_id"]
    created = client.post(url, json=payload)
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["total"] == "38.00000000" or record["total"] == "38.0000000" or float(record["total"]) == 38
    assert len(record["items"]) == 4
    price = session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[0].id))
    price.unit_price = 98
    session.commit()
    assert client.get(f'{url}/{record["id"]}').json() == record
    assert client.get(url).json() == [record]
    assert client.post(url, json=payload).json() == record
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(url).status_code == 404
    assert client.get(f'{url}/{record["id"]}').status_code == 404
    assert client.post(url, json=payload).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.get(url).status_code == 200
    assert client.post(url, json=payload).status_code == 403
    app.dependency_overrides.pop(get_current_user)
    assert client.get(url).status_code == 401


def test_missing_price_and_payload_rejection(estimate_context):
    context, payload, materials = estimate_context
    client, _, _, session, layout, _, _, _ = context
    url = f"/api/projects/{layout.project_id}/estimates"
    assert client.post(url, json={**payload, "total": 1}).status_code == 422
    assert client.post(url, json={**payload, "mappings_confirmed": False}).status_code == 422
    session.delete(session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == materials[0].id)))
    session.commit()
    failed = client.post(url, json=payload)
    assert failed.status_code == 422
    assert failed.json()["detail"]["error"]["code"] == "MISSING_MATERIAL_PRICE"
    assert client.get(url).json() == []
