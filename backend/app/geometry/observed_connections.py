"""Canonical installation connections, not a second viewer-side route graph."""


def observed_connection_routes(wires, symbols, symbol_ids, *, floor_id, floor_elevation, scale, provenance):
    active=[w for w in wires if w['disposition'] in ('accepted','corrected','added')]
    version4=any(w.get('source_evidence_required') or any(
        a.get('provenance')=='source_supported_proposal' or a['point_index'] not in (0,len(w['points'])-1)
        for a in w.get('device_attachments',[])) for w in active)
    routes=[];details=[];drops=set()
    for wire in active:
        identity=len(routes)+1
        points=[dict(project_floor_id=floor_id,x=round(p['x']/scale,9),y=round(p['y']/scale,9),
            elevation_meters=wire['elevation_meters']) for p in wire['points']]
        source_points=list(points)
        connections=[];branches=[]
        for attachment in wire.get('device_attachments',[]):
            symbol=symbols[attachment['symbol_id']]
            index=attachment['point_index'];service=source_points[index]
            mounted={**service,'elevation_meters':float(floor_elevation)+symbol['mounting_height_meters']}
            if version4:
                anchor={k:mounted[k] for k in ('x','y','elevation_meters')}
                binding=dict(symbol_id=symbol_ids[symbol['id']],point_index=index,anchor=anchor)
                connections.append(binding)
                key=(symbol['id'],wire['elevation_meters'])
                if mounted != service and key not in drops:
                    branches.append((service,mounted,{**binding,'point_index':1}));drops.add(key)
            elif mounted != service:
                if index==0:points.insert(0,mounted)
                else:points.append(mounted)
        routes.append(dict(id=identity,points=points))
        detail=dict(route_id=identity,route_kind='observed',provenance_ref=f'{provenance}:wiring:{wire["id"]}')
        if version4:detail['device_connections']=connections
        details.append(detail)
        for service,mounted,binding in branches:
            child=len(routes)+1
            routes.append(dict(id=child,points=[dict(service),dict(mounted)]))
            details.append(dict(route_id=child,route_kind='observed',
                provenance_ref=f'{provenance}:wiring:{wire["id"]}:installation-connection',device_connections=[binding]))
    return routes,details,version4
