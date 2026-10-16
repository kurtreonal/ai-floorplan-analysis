"""Independent unassigned pixel alternatives, never an electrical circuit."""
from time import monotonic
from app.routing.graph import RoutingError


def propose_geometric_drafts(candidate,review,symbols,wires,existing,clearances,*,budget_seconds):
    from app.routing.draft_wiring import draft_path
    report=candidate.payload.observed_routes.recovery
    if report is None or report.stop_reason in ('running','resource_limit'):return existing,[]
    panel=[s for s in symbols if s[2]]
    if len(panel)!=1:return existing,['Geometric routing unresolved: choose one source panel; no circuit assignment was inferred.']
    panelsource,start,_=panel[0]
    states={d.symbol_id:d.state for d in report.devices}
    connected={a['symbol_id'] for w in wires if w.get('disposition')!='rejected' for a in w.get('device_attachments',[])}
    protected={w.get('target_id') for w in existing}|{w.get('source_device_id') for w in existing}
    walls=(review or {}).get('walls')
    if walls is None:walls=[w.model_dump() for w in candidate.payload.walls.items]
    walls=[w for w in walls if w.get('disposition')!='rejected']
    if len(walls)>128:return existing,['Geometric routing exceeds its obstacle budget; no walls were ignored.']
    bands=[((w['start']['x'],w['start']['y']),(w['end']['x'],w['end']['y']),max(2,float(w.get('estimated_thickness_pixels') or 6)/2)) for w in walls]
    result=list(existing);counter=max((int(w['id'].split('-')[-1]) for w in existing),default=0)
    deadline=monotonic()+budget_seconds;notes=[]
    for identity,goal,is_panel in sorted(symbols):
        if is_panel or identity in connected or identity in protected:continue
        if states.get(identity)!='no_usable_observed_path':
            notes.append(f'{identity}: source ink remains unresolved; no generated replacement was proposed.');continue
        if monotonic()>=deadline or len(result)-len(existing)>=8:notes.append('Geometric routing draft budget reached.');break
        region=next((r.bounds for r in candidate.payload.regions if r.kind=='plan_region' and all(
            r.bounds.x<=p[0]<=r.bounds.x+r.bounds.width and r.bounds.y<=p[1]<=r.bounds.y+r.bounds.height for p in (start,goal))),None)
        if region is None:continue
        try:
            points=draft_path(start,goal,(region.x,region.y,region.x+region.width,region.y+region.height),bands,
                endpoint_clearances=(clearances[panelsource],clearances[identity]))
        except RoutingError:
            notes.append(f'{identity}: no permitted geometric path through the supplied obstacles.');continue
        counter+=1
        if counter>9999:break
        result.append(dict(id=f'manual-route-{counter:04d}',disposition='unresolved',points=[dict(x=x,y=y) for x,y in points],
            completeness='partial',elevation_meters=None,line_style='unknown',installation_method='unknown',
            algorithm='astar',source_device_id=panelsource,target_id=identity,target_kind='device',assignment_state='unresolved'))
    if len(result)>len(existing):notes.append('Generated geometric alternatives only: circuit, routing level and electrical assignment unresolved. Excluded from metric/purchase takeoff. Cost: shortest permitted orthogonal source-pixel path; not an optimized multi-device installation.')
    return result,notes
