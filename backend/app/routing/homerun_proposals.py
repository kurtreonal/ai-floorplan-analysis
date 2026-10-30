"""Bounded A* proposals for power homeruns with an unambiguous in-view panel.

These are generated alternatives, not detected copper, circuit assignments or
billable observed spans. Existing edited paths and removal tombstones win.
"""
import re
from time import monotonic
from app.routing.graph import RoutingError


def propose(candidate, review, existing, *, budget_seconds=1):
    from app.routing.draft_wiring import draft_path
    payload = candidate.payload
    saved = {s['id']:s for s in (review or {}).get('symbols',[])}
    predictions = {s.id:s for s in payload.symbols.items}
    symbols = []
    for identity in saved if review and 'symbols' in review else predictions:
        s, p = saved.get(identity,{}), predictions.get(identity)
        if s.get('disposition')=='rejected': continue
        name = s.get('class_name') or (p.observed_label or (p.training_legend.name if p.training_legend else '') if p else '')
        center = s.get('center') or (p.center.model_dump() if p else None)
        if center: symbols.append((identity,name,center))
    panels = [s for s in symbols if re.search(r'\bpanel\s*board\b',s[1],re.I) and not re.search(r'home.?run|fire|alarm|security|data|cctv',s[1],re.I)]
    homes = [s for s in symbols if re.search(r'home.?run',s[1],re.I) and not re.search(r'cctv|security|datacom|telephone|monitor',s[1],re.I)]
    walls = (review or {}).get('walls',[w.model_dump() for w in payload.walls.items])
    walls = [w for w in walls if w.get('disposition')!='rejected']
    if len(walls)>128: return existing,['Homerun routing: obstacle budget exceeded; no walls were ignored.']
    bands=[((w['start']['x'],w['start']['y']),(w['end']['x'],w['end']['y']),max(2,float(w.get('estimated_thickness_pixels') or 6)/2)) for w in walls]
    result,notes = list(existing),[]
    def pristine(wire):
        return (wire.get('algorithm')=='astar' and wire.get('disposition')=='unresolved'
            and not wire.get('device_attachments') and not wire.get('junction_attachments') and not wire.get('suppression_reason'))
    protected={w.get('source_device_id') for w in existing if not pristine(w)}
    replaceable={w.get('source_device_id'):i for i,w in enumerate(existing)
        if pristine(w) and w.get('source_device_id') not in protected}
    counter=max((int(w['id'].rsplit('-',1)[-1]) for w in existing if re.fullmatch(r'manual-route-\d+',w['id'])),default=0)
    deadline=monotonic()+budget_seconds
    for identity,name,point in homes[:32]:
        if identity in protected: continue
        if monotonic()>deadline or len(result)-len(existing)>=8: break
        region=next((r.bounds for r in payload.regions if r.kind=='plan_region' and r.bounds.x<=point['x']<=r.bounds.x+r.bounds.width and r.bounds.y<=point['y']<=r.bounds.y+r.bounds.height),None)
        choices=[p for p in panels if region and region.x<=p[2]['x']<=region.x+region.width and region.y<=p[2]['y']<=region.y+region.height]
        if len(choices)!=1:
            notes.append(f'{identity}: select a plan containing one compatible power panel before proposing its homerun.');continue
        panel_id,_,goal=choices[0]
        # Prefer the existing explicit homerun contact, not its glyph centre.
        # This aligns a generated continuation without claiming newly observed
        # copper or merging circuits merely because lines are nearby.
        observed=(review or {}).get('observed_wiring', [])
        contacts=[(wire,wire['points'][a['point_index']]) for wire in observed
            if wire.get('disposition')!='rejected' and not wire.get('suppression_reason')
            for a in wire.get('device_attachments', []) if a['symbol_id']==identity
            and a['point_index'] in (0,len(wire['points'])-1)]
        # A source homerun leader ends at the arrow, not at the circuit label's
        # centre. Bind its exact source endpoint to the generated continuation.
        source_contacts=[]
        for contact in payload.observed_routes.connections:
            if contact.to_ref!=f'symbol:{identity}' or not contact.route_node_id or contact.ambiguity!='unambiguous':continue
            wire=next((w for w in observed if f"segment:{w['id']}"==contact.from_ref and w.get('disposition','unresolved')=='unresolved' and not w.get('suppression_reason') and not w.get('auto_connect_disabled_endpoints')),None)
            if not wire:continue
            matches=[i for i in (0,len(wire['points'])-1) if wire['points'][i]==contact.path_anchor.model_dump()]
            if len(matches)==1:source_contacts.append((wire,matches[0]))
        contacts.extend((wire,wire['points'][index]) for wire,index in source_contacts)
        anchors={(p['x'],p['y']) for _,p in contacts}
        if len(anchors)>1:
            notes.append(f'{identity}: choose the intended homerun terminal before routing.');continue
        start=next(iter(anchors)) if anchors else (point['x'],point['y'])
        metadata={}
        for key in ('installation_method','line_style','wiring_legend_id','wiring_legend_name','circuit_id','height_above_floor_meters','elevation_meters'):
            values={w.get(key) for w,_ in contacts if w.get(key) is not None and w.get(key)!='unknown'}
            if len(values)==1: metadata[key]=next(iter(values))
        # A written panel reference must match the actual panel label, not proximity.
        reference=re.search(r'\b(?:to|panel)\s*[:#-]?\s*([A-Z]{1,4}[-\d]*)\b',name)
        if reference and reference[1] not in ('HOMERUN','TO') and not re.search(r'(?<!\w)'+re.escape(reference[1])+r'(?!\w)',choices[0][1]):
            notes.append(f'{identity}: written panel identity is not resolved; no panel was guessed.');continue
        try:
            points=draft_path(start,(goal['x'],goal['y']),
                (region.x,region.y,region.x+region.width,region.y+region.height),bands,endpoint_clearances=(12,40))
        except RoutingError:
            notes.append(f'{identity}: no permitted wall-safe orthogonal route to the panel.');continue
        counter+=1
        if counter>9999 or len(result)>=2048: break
        replacement=replaceable.get(identity)
        proposal=dict(id=existing[replacement]['id'] if replacement is not None else f'manual-route-{counter:04d}',disposition='unresolved',points=[dict(x=x,y=y) for x,y in points],
            completeness='partial',elevation_meters=None,installation_method='unknown',line_style='unknown',
            algorithm='astar',source_device_id=identity,target_id=panel_id,target_kind='device',assignment_state='unresolved')
        proposal.update(metadata)
        if source_contacts:
            used={a['junction_id'] for w in observed+result for a in w.get('junction_attachments',[])}
            junction=next((a['junction_id'] for wire,index in source_contacts for a in wire.get('junction_attachments',[]) if a['point_index']==index),None)
            if junction is None:junction=next((f'junction-{n:04d}' for n in range(1,10000) if f'junction-{n:04d}' not in used),None)
            if junction is None:continue
            proposal['junction_attachments']=[dict(junction_id=junction,point_index=0)]
            for wire,index in source_contacts:
                if not any(a['point_index']==index for a in wire.get('junction_attachments',[])):
                    wire['junction_attachments']=[*wire.get('junction_attachments',[]),dict(junction_id=junction,point_index=index)]
        elif not contacts and start==(point['x'],point['y']):
            proposal['device_attachments']=[dict(symbol_id=identity,point_index=0,terminal_id='design-anchor')]
        if replacement is not None: result[replacement]=proposal
        else: result.append(proposal)
    if len(result)>len(existing): notes.append('Homerun A* proposals use the shortest permitted orthogonal grid path. Review circuit, terminals and service level; proposals remain separate from observed quantities.')
    return result,notes
