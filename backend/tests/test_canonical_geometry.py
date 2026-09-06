import copy
import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import pytest

from app.geometry import (
    CanonicalCoordinateSystem,
    CanonicalGeometryError,
    CanonicalPoint,
    CanonicalWall,
    CanonicalWallCandidate,
    NormalizedWallGeometry,
    RawPixelPoint,
    RawPixelWall,
    build_canonical_geometry,
    canonical_geometry_from_dict,
)
from app.services.authoritative_symbol_service import AuthoritativeSymbolCandidate


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "canonical_geometry_v1.json"
COMPATIBILITY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "canonical_geometry_compatibility_v1.json"
)


@pytest.fixture
def payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def mutate(payload, path, value):
    changed = copy.deepcopy(payload)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


def test_shared_fixture_serializes_deterministically_and_is_immutable(payload):
    document = canonical_geometry_from_dict(payload)
    assert document.to_dict() == payload
    with pytest.raises(FrozenInstanceError):
        document.project_id = 99
    assert canonical_geometry_from_dict(document.to_dict()) is not document


def test_shared_compatibility_fixture_keeps_v1_native_and_v2_unsupported(payload):
    matrix = json.loads(COMPATIBILITY_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert matrix["decision_fixture_version"] == 1
    assert matrix["current_contract"] == {
        "schema_version": 1,
        "document_fixture": "canonical_geometry_v1.json",
        "python_expectation": "accept",
        "javascript_expectation": "accept",
        "storage_behavior": "read_native_without_rewrite",
    }
    assert canonical_geometry_from_dict(payload).to_dict() == payload
    future = copy.deepcopy(payload)
    future["schema_version"] = matrix["reserved_contract"]["extension_schema_version"]
    with pytest.raises(CanonicalGeometryError) as error:
        canonical_geometry_from_dict(future)
    assert error.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_empty_document_is_valid(payload):
    for key in ("walls", "rooms", "symbols", "routes"):
        payload[key] = []
    assert canonical_geometry_from_dict(payload).to_dict() == payload


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), 2),
        (("project_id",), True),
        (("project_id",), 0),
        (("project_id",), 9_007_199_254_740_992),
        (("floor", "sort_order"), True),
        (("floor", "elevation_meters"), math.inf),
        (("coordinate_system", "unit"), "pixel"),
        (("coordinate_system", "origin"), "bottom_left"),
        (("coordinate_system", "pixels_per_meter"), 0),
        (("coordinate_system", "image_width_pixels"), 4097),
        (("coordinate_system", "width_meters"), 6.5),
        (("walls", 0, "start", "x"), -1),
        (("walls", 0, "end", "x"), 7),
        (("walls", 0, "length_meters"), 3),
        (("walls", 0, "angle_degrees"), 180),
        (("walls", 0, "status"), "pending"),
        (("walls", 0, "status"), {}),
        (("walls", 0, "height_meters"), 0),
        (("rooms", 0, "boundary"), [{"x": 0, "y": 0}, {"x": 1, "y": 0}]),
        (("symbols", 0, "status"), "manually_added"),
        (("symbols", 0, "source_type"), {}),
        (("symbols", 0, "id"), "manual:501"),
        (("symbols", 0, "class", "id"), -1),
        (("routes", 0, "points"), [{"project_floor_id": 2, "x": 0, "y": 0, "elevation_meters": 0}]),
        (("routes", 0, "points", 0, "elevation_meters"), math.nan),
    ],
)
def test_invalid_values_raise_stable_sanitized_error(payload, path, value):
    with pytest.raises(CanonicalGeometryError, match="^The canonical geometry document is invalid\\.$"):
        canonical_geometry_from_dict(mutate(payload, path, value))


def test_missing_and_unknown_fields_are_rejected(payload):
    missing = copy.deepcopy(payload)
    missing.pop("routes")
    unknown = copy.deepcopy(payload)
    unknown["extra"] = None
    for value in (missing, unknown, [], None):
        with pytest.raises(CanonicalGeometryError):
            canonical_geometry_from_dict(value)


def test_room_omits_repeated_closing_point_and_rejects_adjacent_duplicate(payload):
    repeated_close = copy.deepcopy(payload)
    repeated_close["rooms"][0]["boundary"].append({"x": 0.1, "y": 0.1})
    duplicate = copy.deepcopy(payload)
    duplicate["rooms"][0]["boundary"].insert(1, {"x": 0.1, "y": 0.1})
    for value in (repeated_close, duplicate):
        with pytest.raises(CanonicalGeometryError):
            canonical_geometry_from_dict(value)


def test_builder_adapts_h2_walls_and_ordered_j5_symbols_with_explicit_elevation():
    cs = CanonicalCoordinateSystem(100.0, 640, 480, 6.4, 4.8)
    geometry = NormalizedWallGeometry(
        coordinate_system=cs,
        source_truncated=False,
        walls=(CanonicalWallCandidate(
            candidate_id=1,
            raw_pixels=RawPixelWall(RawPixelPoint(20, 35), RawPixelPoint(220, 35), 200, 0),
            canonical=CanonicalWall(CanonicalPoint(0.2, 0.35), CanonicalPoint(2.2, 0.35), 2.0, 0),
        ),),
    )
    candidates = (
        AuthoritativeSymbolCandidate("detected", 501, 81, 103, 9, "Corrected outlet", 250, 150, 640, 480, "confirmed"),
        AuthoritativeSymbolCandidate("manual", 601, 81, 103, 2, "Wall light", 410, 225, 640, 480, "manually_added"),
    )
    document = build_canonical_geometry(
        project_id=15, project_floor_id=2, floor_name="Lower Ground Floor", floor_sort_order=0,
        floor_elevation_meters=-1.5, floor_plan_id=81, wall_geometry=geometry,
        authoritative_symbols=candidates, symbol_processing_job_id=103, wall_processing_job_id=103,
    )
    serialized = document.to_dict()
    assert serialized["floor"]["elevation_meters"] == -1.5
    assert serialized["walls"][0]["start"] == {"x": 0.2, "y": 0.35}
    assert [(item["id"], item["class"]["name"], item["position"]) for item in serialized["symbols"]] == [
        ("detected:501", "Corrected outlet", {"x": 2.5, "y": 1.5}),
        ("manual:601", "Wall light", {"x": 4.1, "y": 2.25}),
    ]


@pytest.mark.parametrize(
    "replacement",
    [
        {"image_width_pixels": 641},
        {"floor_plan_id": 82},
        {"processing_job_id": 104},
        {"status": "deleted"},
        {"source_type": "pending"},
        {"center_x_pixels": 641},
    ],
)
def test_builder_rejects_invalid_symbol_provenance_and_bounds(replacement):
    cs = CanonicalCoordinateSystem(100, 640, 480, 6.4, 4.8)
    geometry = NormalizedWallGeometry(cs, False, ())
    values = dict(
        source_type="detected", source_record_id=1, floor_plan_id=81, processing_job_id=103,
        class_id=7, class_name="Outlet", center_x_pixels=250, center_y_pixels=150,
        image_width_pixels=640, image_height_pixels=480, status="confirmed",
    )
    values.update(replacement)
    candidate = AuthoritativeSymbolCandidate(**values)
    with pytest.raises(CanonicalGeometryError):
        build_canonical_geometry(
            project_id=15, project_floor_id=2, floor_name="Floor", floor_sort_order=0,
            floor_elevation_meters=0, floor_plan_id=81, wall_geometry=geometry,
            authoritative_symbols=(candidate,), symbol_processing_job_id=103,
        )


def test_nine_decimal_public_rounding(payload):
    payload["floor"]["elevation_meters"] = 1.1234567894
    assert canonical_geometry_from_dict(payload).to_dict()["floor"]["elevation_meters"] == 1.123456789


def test_optional_wall_dimensions_and_all_elevation_signs_are_valid(payload):
    payload["floor"]["elevation_meters"] = 0
    payload["walls"][0].update(status="verified", thickness_meters=0.15, height_meters=3.0)
    payload["routes"][0]["points"].append(
        {"project_floor_id": 2, "x": 3.0, "y": 2.0, "elevation_meters": 2.75}
    )
    serialized = canonical_geometry_from_dict(payload).to_dict()
    assert serialized["walls"][0]["thickness_meters"] == 0.15
    assert [point["elevation_meters"] for point in serialized["routes"][0]["points"]] == [-1.5, 0.0, 2.75]


def test_builder_has_no_filesystem_side_effect_and_does_not_mutate_inputs():
    cs = CanonicalCoordinateSystem(100, 640, 480, 6.4, 4.8)
    geometry = NormalizedWallGeometry(cs, False, ())
    candidates = (
        AuthoritativeSymbolCandidate("manual", 1, 81, 103, 2, "Wall light", 100, 100, 640, 480, "manually_added"),
    )
    with patch("builtins.open", side_effect=AssertionError("unexpected filesystem access")):
        build_canonical_geometry(
            project_id=15, project_floor_id=2, floor_name="Floor", floor_sort_order=0,
            floor_elevation_meters=0, floor_plan_id=81, wall_geometry=geometry,
            authoritative_symbols=candidates, symbol_processing_job_id=103,
        )
    assert geometry == NormalizedWallGeometry(cs, False, ())
    assert candidates[0].center_x_pixels == 100
