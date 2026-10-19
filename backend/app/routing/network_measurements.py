"""Selected, explicit circuit geometry; not a purchase/engineering approval."""
from app.geometry.route_measurement import measure_metric_network
from app.geometry.canonical_takeoff import canonical_route_groups
from app.routing.circuit import CircuitMaterialPreview


def circuit_network_takeoff(request, planned, documents, *, extensions=None):
    # Use the SAME explicit route groups as canonical BOM. Legacy snapshots
    # without topology retain distinct route identities, including overlaps.
    groups = {floor: {identity: group[0] for group in canonical_route_groups(
        document, (extensions or {}).get(floor)) for identity in group}
        for floor, document in documents.items()}
    observed = []
    for assignment in request.observed_route_assignments:
        route = next(r for r in documents[assignment.floor_id].routes if r.id == assignment.route_id)
        config = next(c for c in request.floors if c.floor_id == assignment.floor_id)
        def point(p):
            return dict(floor_id=p.project_floor_id, x=p.x+config.offset_x, y=p.y+config.offset_y,
                        elevation_meters=p.elevation_meters)
        # Circuit assignment alone is not proof of a shared raceway. Only the
        # saved topology above can make two selected source pieces share scope.
        observed.extend(dict(start=point(a),end=point(b),slope_supported=True,
                             physical_path_id=f'observed:{assignment.floor_id}:{groups[assignment.floor_id][route.id]}')
                        for a,b in zip(route.points,route.points[1:]))
    generated = [s.model_dump(mode='json') for s in planned.segments]
    observed_length = measure_metric_network(observed)
    generated_length = measure_metric_network(generated)
    measured = measure_metric_network(observed+generated)
    h, v, total = measured.horizontal_meters, measured.vertical_meters, measured.physical_meters
    count = request.conductor_count
    return planned.model_copy(update={'planning_takeoff': CircuitMaterialPreview(
        measurement_revision=measured.measurement_revision,
        observed_meters=observed_length.physical_meters,generated_meters=generated_length.physical_meters,horizontal_meters=h,vertical_meters=v,
        conduit_meters=total,conductor_count=count,one_conductor_meters=total if count is not None else None,
        total_conductor_meters=total*count if count is not None else None)})
