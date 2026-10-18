"""Read-only physical paths from the saved canonical snapshot, not fresh CV."""
from decimal import Decimal, ROUND_HALF_UP
from app.geometry.route_measurement import measure_metric_network


def canonical_path_rows(document, extension=None):
    routes = {route.id: route for route in document.routes}
    details = {detail.route_id: detail for detail in extension.route_details} if extension else {}
    parents = {identity: identity for identity in routes}
    def root(identity):
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity
    contacts = {}
    for identity, detail in details.items():
        if identity not in routes: continue
        # Provenance belongs to each edge, not to physical connectivity. An
        # explicitly joined manual continuation must not duplicate a source span.
        # Distinct circuits and unspecified historical terminals stay separate.
        scope = (detail.circuit_id,)
        for contact in detail.device_connections or ():
            if contact.terminal_id:
                contacts.setdefault((*scope,'device',contact.symbol_id,contact.terminal_id), []).append(identity)
        # Older installation-drop routes have a precise parent provenance,
        # unlike two unspecified terminals on the same device bounding box.
        ref=detail.provenance_ref or ''
        if ref.endswith(':installation-connection'):
            parent=next((d.route_id for d in details.values() if d.provenance_ref==ref.removesuffix(':installation-connection')),None)
            if parent is not None: contacts.setdefault((*scope,'installation',parent),[]).extend([identity,parent])
        for contact in detail.junction_connections or ():
            contacts.setdefault((*scope,'junction',contact['junction_id']), []).append(identity)
    for members in contacts.values():
        for identity in members[1:]:
            a,b = root(members[0]),root(identity)
            parents[max(a,b)] = min(a,b)
    groups = {}
    for identity in routes: groups.setdefault(root(identity), []).append(identity)
    rows = []
    def point(p):
        return dict(floor_id=p.project_floor_id,x=p.x,y=p.y,elevation_meters=p.elevation_meters)
    for identities in groups.values():
        edges, missing = [], []
        for identity in identities:
            for a,b in zip(routes[identity].points,routes[identity].points[1:]):
                if a.project_floor_id != b.project_floor_id or a.project_floor_id != document.floor.project_floor_id:
                    missing.append('Inter-floor canonical edge has no explicit connector in this floor snapshot; excluded.')
                else:
                    # These are stored, reviewed metric points, not perspective
                    # clicks, smoothed tubes or inferred mounting elevations.
                    edges.append(dict(start=point(a),end=point(b),slope_supported=True))
        measured = measure_metric_network(edges)
        h, v = measured.horizontal_meters, measured.vertical_meters
        detail = details.get(identities[0])
        origins = sorted({details[i].route_kind if i in details else 'unresolved' for i in identities})
        origin = origins[0] if len(origins)==1 else 'mixed'
        rows.append(dict(kind='path',name=f'Reviewed wiring path — {origin} provenance; material unassigned',
            origin=origin,provenance_origins=origins,path_id=f'canonical:{identities[0]}',path_ids=identities,circuit_id=detail.circuit_id if detail else None,
            quantity=Decimal(str(measured.physical_meters)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),unit='meter',
            measurement_revision=measured.measurement_revision,
            horizontal_meters=h,vertical_meters=v,missing_vertical_inputs=sorted(set(missing)),
            basis='Saved canonical metric centerlines including stored drops/rises. Unique spans only within explicit device/junction-connected same-circuit groups; each route retains its provenance. Independent paths remain separate. No inferred material, conductor count, allowance or display offsets.'
                  + (' INCOMPLETE: unsupported inter-floor edges excluded.' if missing else '')))
    return rows
