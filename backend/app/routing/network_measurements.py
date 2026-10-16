"""Selected, explicit circuit geometry; not a purchase/engineering approval."""
from app.geometry.path_lengths import unique_metric_edges
from app.routing.circuit import CircuitMaterialPreview


def circuit_network_takeoff(request, planned, documents):
    observed = []
    for assignment in request.observed_route_assignments:
        route = next(r for r in documents[assignment.floor_id].routes if r.id == assignment.route_id)
        config = next(c for c in request.floors if c.floor_id == assignment.floor_id)
        def point(p):
            return dict(floor_id=p.project_floor_id, x=p.x+config.offset_x, y=p.y+config.offset_y,
                        elevation_meters=p.elevation_meters)
        observed.extend(dict(start=point(a),end=point(b)) for a,b in zip(route.points,route.points[1:]))
    generated = [s.model_dump(mode='json') for s in planned.segments]
    oh, ov = unique_metric_edges(observed)
    gh, gv = unique_metric_edges(generated)
    h, v = unique_metric_edges(observed+generated)
    total = h+v
    count = request.conductor_count
    return planned.model_copy(update={'planning_takeoff': CircuitMaterialPreview(
        observed_meters=oh+ov,generated_meters=gh+gv,horizontal_meters=h,vertical_meters=v,
        conduit_meters=total,conductor_count=count,one_conductor_meters=total if count is not None else None,
        total_conductor_meters=total*count if count is not None else None)})
