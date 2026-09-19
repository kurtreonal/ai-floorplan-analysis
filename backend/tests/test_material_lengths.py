from copy import deepcopy

import pytest

from app.routing.contracts import Point
from app.routing.engine import result, segment
from app.routing.measurements import measure_material_lengths


def route():
    points = [Point(floor_id=f, x=x, y=y, elevation_meters=z) for f, x, y, z in
              [(1, 0, 0, 1), (1, 0, 0, 3), (1, 3, 0, 3), (1, 3, 4, 3), (2, 3, 4, 6), (2, 3, 4, 4)]]
    kinds = ["wall_rise", "ceiling_service", "ceiling_service", "riser", "wall_drop"]
    return result([segment(a, b, kind, "riser-1" if kind == "riser" else None)
                   for a, b, kind in zip(points, points[1:], kinds)])


def test_known_multifloor_coordinates_and_explicit_conductors():
    saved = route()
    original = deepcopy(saved.model_dump())
    measured = measure_material_lengths(saved, conductor_count=3)
    assert measured.horizontal_meters == 7
    assert measured.vertical_meters == 7
    assert measured.riser_meters == 3
    assert measured.conduit_meters == 14
    assert measured.wire_meters == 42
    assert measured.unit == "meter"
    assert measure_material_lengths(saved).wire_meters is None
    assert saved.model_dump() == original


@pytest.mark.parametrize("count", [0, -1, True, 1.5, 1001])
def test_invalid_conductor_counts(count):
    with pytest.raises(ValueError, match="Conductor"):
        measure_material_lengths(route(), conductor_count=count)


def test_rejects_tampered_totals_disconnection_and_missing_riser():
    saved = route()
    bad_routes = [saved.model_copy(update={"total_meters": 99}), saved.model_copy(update={"points": []})]
    for index, changes in [(0, {"horizontal_meters": 4}), (3, {"connector_id": None}),
                           (3, {"kind": "wall_rise"}), (0, {"kind": "wall_drop"}),
                           (1, {"start": saved.points[0]})]:
        segments = list(saved.segments)
        segments[index] = segments[index].model_copy(update=changes)
        bad_routes.append(saved.model_copy(update={"segments": segments}))
    for invalid in bad_routes:
        with pytest.raises(ValueError):
            measure_material_lengths(invalid)
