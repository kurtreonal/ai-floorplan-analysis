"""Ceiling routes can reach wall-mounted devices at the verified wall top."""

import pytest

from app.geometry import canonical_geometry_from_dict
from app.routing.contracts import RoutingRequest
from app.routing.engine import generate_route
from app.routing.graph import RoutingError
from tests.test_routing import request_data, wall_document


def ceiling_document(*, floor_id=2, floor_elevation=0, wall_height=3):
    data = wall_document().to_dict()
    data["floor"].update(project_floor_id=floor_id, elevation_meters=floor_elevation)
    data["walls"][0]["height_meters"] = wall_height
    return canonical_geometry_from_dict(data)


def wall_target_request(*, service_elevation=3, target_elevation=1.2):
    data = request_data()
    data["floors"][0]["service_elevation_meters"] = service_elevation
    data["panel"]["elevation_meters"] = service_elevation
    data["target"].update(elevation_meters=target_elevation, wall_id=1)
    return data


def test_ceiling_at_wall_top_reaches_attached_device_with_exact_drop_length():
    request = RoutingRequest.model_validate(wall_target_request())
    route = generate_route(request, {2: ceiling_document()})

    assert route.horizontal_meters == pytest.approx(2)
    assert route.vertical_meters == pytest.approx(1.8)
    assert route.total_meters == pytest.approx(3.8)
    assert route.segments[-1].kind == "wall_drop"
    assert route.segments[-1].start.elevation_meters == 3
    assert route.segments[-1].end.elevation_meters == 1.2
    assert route.segments[-1].start.x == route.segments[-1].end.x == 2.5
    assert route.segments[-1].start.y == route.segments[-1].end.y == 1.5
    assert all(
        segment.kind == "ceiling_service"
        and segment.start.elevation_meters == segment.end.elevation_meters == 3
        and (segment.start.x == segment.end.x or segment.start.y == segment.end.y)
        for segment in route.segments[:-1]
    )


@pytest.mark.parametrize("service_elevation", [2.9, 2.999999])
def test_service_plane_below_wall_top_cannot_reach_device_through_wall(service_elevation):
    request = RoutingRequest.model_validate(wall_target_request(service_elevation=service_elevation))
    with pytest.raises(RoutingError, match="NO_ROUTE"):
        generate_route(request, {2: ceiling_document()})


def test_taller_intersecting_wall_remains_a_barrier_at_other_wall_top():
    data = ceiling_document().to_dict()
    data["walls"].append({
        **data["walls"][0],
        "id": 2,
        "start": {"x": 0, "y": 1.25},
        "end": {"x": 6.4, "y": 1.25},
        "length_meters": 6.4,
        "height_meters": 3.2,
    })
    request = RoutingRequest.model_validate(wall_target_request())
    with pytest.raises(RoutingError, match="NO_ROUTE"):
        generate_route(request, {2: canonical_geometry_from_dict(data)})


@pytest.mark.parametrize("bottom,top", [(2.8, 3), (3, 3.2)])
def test_explicit_obstacle_surface_at_ceiling_remains_blocking(bottom, top):
    data = wall_target_request()
    data["obstacles"] = [{
        "floor_id": 2, "min_x": 0, "max_x": 6.4,
        "min_y": 1.2, "max_y": 1.3, "bottom": bottom, "top": top,
    }]
    with pytest.raises(RoutingError, match="NO_ROUTE"):
        generate_route(RoutingRequest.model_validate(data), {2: ceiling_document()})


@pytest.mark.parametrize("floor_elevation", [-1.5, 3])
def test_wall_top_uses_floor_elevation_for_attached_device(floor_elevation):
    data = wall_target_request(
        service_elevation=floor_elevation + 3,
        target_elevation=floor_elevation + 1.2,
    )
    route = generate_route(
        RoutingRequest.model_validate(data),
        {2: ceiling_document(floor_elevation=floor_elevation)},
    )
    assert route.horizontal_meters == pytest.approx(2)
    assert route.vertical_meters == pytest.approx(1.8)
    assert route.total_meters == pytest.approx(3.8)
    assert route.segments[-1].start.elevation_meters == floor_elevation + 3
    assert route.segments[-1].end.elevation_meters == floor_elevation + 1.2


def test_multifloor_wall_tops_preserve_explicit_riser_and_both_wall_legs():
    data = wall_target_request()
    data["panel"].update(y=1.5, elevation_meters=1.2, wall_id=1)
    data["floors"].append({
        "floor_id": 3, "expected_layout_version": 1,
        "service_elevation_meters": 6, "offset_x": 0, "offset_y": 0,
    })
    data["target"].update(floor_id=3, elevation_meters=4.2)
    data["connectors"] = [{
        "id": "reviewed-riser", "from_floor_id": 2, "to_floor_id": 3, "x": 2, "y": 1,
    }]
    documents = {
        2: ceiling_document(),
        3: ceiling_document(floor_id=3, floor_elevation=3),
    }
    route = generate_route(RoutingRequest.model_validate(data), documents)
    assert route.segments[0].kind == "wall_rise"
    assert route.segments[-1].kind == "wall_drop"
    risers = [segment for segment in route.segments if segment.kind == "riser"]
    assert len(risers) == 1
    assert risers[0].connector_id == "reviewed-riser"
    assert risers[0].vertical_meters == 3
    assert route.horizontal_meters == pytest.approx(2.5)
    assert route.vertical_meters == pytest.approx(6.6)
    assert route.total_meters == pytest.approx(9.1)

    data["connectors"] = []
    with pytest.raises(RoutingError, match="NO_ROUTE"):
        generate_route(RoutingRequest.model_validate(data), documents)
