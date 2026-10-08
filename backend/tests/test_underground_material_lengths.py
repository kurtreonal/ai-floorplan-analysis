"""Measure generated underground geometry without assumptions or allowances."""
from copy import deepcopy

import pytest

from app.routing.contracts import Point
from app.routing.engine import generate_route, result, segment
from app.routing.contracts import RoutingRequest
from app.routing.measurements import measure_material_lengths
from tests.test_underground_routing import geometry, inputs


def test_generated_underground_run_counts_floor_crossings_and_wall_legs_once():
    route = generate_route(RoutingRequest.model_validate(inputs()), {2: geometry()})
    before = deepcopy(route.model_dump())
    lengths = measure_material_lengths(route, conductor_count=3)
    assert lengths.horizontal_meters == 1.5
    assert lengths.vertical_meters == 3.5
    assert lengths.riser_meters == 0
    assert lengths.conduit_meters == 5
    assert lengths.wire_meters == 15
    assert measure_material_lengths(route).wire_meters is None
    assert route.model_dump() == before


@pytest.mark.parametrize('kind,a,b', [
    ('underground', (2, 0, 0, -.5), (2, 0, 0, 0)),
    ('underground', (2, 0, 0, -.5), (3, 1, 0, -.5)),
    ('underground_rise', (2, 0, 0, 0), (2, 0, 0, -.5)),
    ('underground_drop', (2, 0, 0, -.5), (2, 0, 0, 0)),
    ('underground_rise', (2, 0, 0, -.5), (2, 1, 0, -.5)),
    ('underground_drop', (2, 0, 0, -.5), (3, 0, 0, -1)),
])
def test_new_segment_types_reject_contradictory_geometry(kind, a, b):
    points = [Point(floor_id=floor, x=x, y=y, elevation_meters=elevation)
              for floor, x, y, elevation in (a, b)]
    route = result([segment(*points, kind)])
    with pytest.raises(ValueError, match='type contradicts geometry'):
        measure_material_lengths(route)


@pytest.mark.parametrize('kind', ['underground', 'underground_rise', 'underground_drop'])
def test_underground_segments_cannot_carry_interfloor_connector_identity(kind):
    a = Point(floor_id=2, x=0, y=0, elevation_meters=-.5)
    b = Point(floor_id=2, x=1 if kind == 'underground' else 0, y=0,
              elevation_meters=-.5 if kind == 'underground' else 0 if kind.endswith('rise') else -1)
    route = result([segment(a, b, kind, 'invented-riser')])
    with pytest.raises(ValueError, match='type contradicts geometry'):
        measure_material_lengths(route)
