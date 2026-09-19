import pytest
from pydantic import ValidationError

from app.routing.contracts import RoutingRequest


def request_data():
    return dict(
        floors=[dict(floor_id=2, expected_layout_version=1, service_elevation_meters=3, offset_x=0, offset_y=0)],
        panel=dict(floor_id=2, x=1, y=1, elevation_meters=3),
        target=dict(floor_id=2, symbol_id="detected:501", x=2.5, y=1.5, elevation_meters=3),
        grid_step_meters=1, alignment_confirmed=True,
    )


def test_contract_requires_explicit_alignment_and_finite_heights():
    data = request_data()
    assert RoutingRequest.model_validate(data).purpose == "planning"
    for field, value in [("alignment_confirmed", False), ("grid_step_meters", float("nan"))]:
        with pytest.raises(ValidationError):
            RoutingRequest.model_validate({**data, field: value})


def test_contract_rejects_duplicate_and_unknown_floor_references():
    data = request_data()
    with pytest.raises(ValidationError):
        RoutingRequest.model_validate({**data, "floors": data["floors"] * 2})
    with pytest.raises(ValidationError):
        RoutingRequest.model_validate({**data, "target": {**data["target"], "floor_id": 9}})
