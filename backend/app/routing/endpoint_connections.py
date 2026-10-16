"""Advisory endpoint contacts, never crossing-based junctions or circuit merging."""
from copy import deepcopy
import math
import re


def apply_source_contacts(candidate, document, *, preserve_source=True):
    """Adapt pixel-supported proposals, preserving raw candidates and user edits."""
    result = deepcopy(document)
    if result.get('approved_for_layout'):return result
    observed = getattr(candidate.payload,'observed_routes',None)
    if observed is None:return result
    contacts = [c for c in observed.connections
                if c.evidence_kind is not None and c.ambiguity == 'unambiguous']
    predictions = {s.id:s for s in candidate.payload.symbols.items}
    saved_symbols = {s['id']:s for s in result.get('symbols', [])}
    source_routes = {w.id:w for w in observed.segments}
    parameters = getattr(getattr(candidate,'provenance',None),'inference_parameters', ())
    # The strict source-evidence contract began at v7. New algorithm revisions
    # must not silently re-enable the historical proximity-only adapter.
    legacy_versions = {f'raw-source-device-port-evidence-v{n}' for n in range(1,7)}
    strict = any(p.name == 'wiring-evidence-version'
        and p.value.startswith('raw-source-device-port-evidence-v')
        and p.value not in legacy_versions for p in parameters)
    for wire in result.get('observed_wiring', []):
        source = source_routes.get(wire['id'])
        if strict:wire['source_evidence_required'] = source is not None
        if (source is None or wire.get('disposition','unresolved') != 'unresolved'
            or wire.get('device_attachments') or wire.get('auto_connect_disabled_endpoints')
            or wire['points'] != [p.model_dump() for p in source.points]):continue
        selected=[]
        for contact in contacts:
            if contact.from_ref != f"segment:{wire['id']}":continue
            identity=contact.to_ref.split(':',1)[1];symbol=saved_symbols.get(identity,{})
            if symbol.get('disposition') == 'rejected':continue
            center = symbol.get('center') or predictions[identity].center.model_dump()
            if center != contact.device_anchor.model_dump():continue
            selected.append((contact,identity,center))
        points=[];attachments=[]
        def append(point):
            if not points or points[-1] != point:points.append(dict(point))
            return len(points)-1
        for edge in range(len(source.points)-1):
            a,b=source.points[edge],source.points[edge+1]
            delta=(b.x-a.x,b.y-a.y);length2=delta[0]**2+delta[1]**2
            insertions=[]
            for contact,identity,center in selected:
                if contact.source_edge_index != edge:continue
                anchor=contact.path_anchor
                t=((anchor.x-a.x)*delta[0]+(anchor.y-a.y)*delta[1])/length2
                insertions.append((max(0,min(1,t)),contact,identity,center))
            if not points:points.append(a.model_dump())
            insertions.sort(key=lambda item:(item[0],item[2]))
            for t,contact,identity,center in insertions:
                if preserve_source and t<=1e-8:
                    if edge==0 and center!=points[0]:
                        points.insert(0,dict(center));index=0
                    else:index=len(points)-1;points[index]=dict(center)
                elif (preserve_source and t>=1-1e-8 and edge<len(source.points)-2
                      and contact.evidence_kind=='inline_device'):
                    # A chained path can have a device exactly at an interior
                    # vertex. Adapt only its glyph-core interval on BOTH arms;
                    # do not turn the entire next arm into a long diagonal or
                    # flatten a new out-and-back attachment branch into it.
                    symbol=predictions[identity]
                    following=source.points[edge+2]
                    outgoing=(following.x-b.x,following.y-b.y)
                    incoming_length=math.sqrt(length2)
                    outgoing_length=math.hypot(*outgoing)
                    half=min(8,min(symbol.bounds.width,symbol.bounds.height)*.3,
                             incoming_length/4,outgoing_length/4)
                    append(dict(x=b.x-half*delta[0]/incoming_length,
                                y=b.y-half*delta[1]/incoming_length))
                    index=append(center)
                    append(dict(x=b.x+half*outgoing[0]/outgoing_length,
                                y=b.y+half*outgoing[1]/outgoing_length))
                elif preserve_source and t>=1-1e-8:
                    append(b.model_dump());index=append(center)
                elif preserve_source:
                    # Keep the visible line on its original axis; only the
                    # small glyph-core interval is adapted through the port.
                    symbol=predictions[identity];half=min(8,min(symbol.bounds.width,symbol.bounds.height)*.3)
                    length=math.sqrt(length2);step=min(t,1-t,half/length)
                    append(dict(x=a.x+(t-step)*delta[0],y=a.y+(t-step)*delta[1]))
                    index=append(center)
                    append(dict(x=a.x+(t+step)*delta[0],y=a.y+(t+step)*delta[1]))
                elif t<=1e-8:index=len(points)-1;points[index]=dict(center)
                elif t>=1-1e-8:
                    points.append(dict(center));index=len(points)-1
                else:
                    points.append(dict(center));index=len(points)-1
                attachments.append(dict(symbol_id=identity,point_index=index,
                    provenance='source_supported_proposal',source_connection_id=contact.id,
                    source_candidate_run_id=candidate.provenance.candidate_run_id,
                    geometry_version='source_preserving_v1' if preserve_source else 'center_replace_v0',
                    evidence_kind=contact.evidence_kind,observed_anchor=contact.path_anchor.model_dump()))
            # The next original vertex remains unless this edge's end was attached.
            if not insertions or insertions[-1][0]<1-1e-8:append(b.model_dump())
        if attachments and not any(a==b for a,b in zip(points,points[1:])):
            wire.update(points=points,device_attachments=attachments)
    return result


def connect_touching_endpoints(candidate, document):
    result = apply_source_contacts(candidate, document)
    if result.get('approved_for_layout'):
        return result  # Approved historical geometry is not silently rewritten.
    predictions = {s.id: s for s in candidate.payload.symbols.items}
    saved = {s['id']: s for s in result.get('symbols', [])}
    symbols = []
    for identity in sorted(set(predictions) | set(saved)):
        source, symbol = predictions.get(identity), saved.get(identity, {})
        if symbol.get('disposition') == 'rejected':
            continue
        name = symbol.get('class_name') or (source.training_legend.name if source and source.training_legend
                                           else source.observed_label if source else '') or ''
        if re.search(r'home.?run|circuit.*notation|raceway conduit', name, re.I):
            continue
        center = symbol.get('center') or (source.center.model_dump() if source else None)
        if not center:
            continue
        bounds = source.bounds if source else None
        box = None if bounds is None else dict(x=bounds.x+center['x']-source.center.x,
            y=bounds.y+center['y']-source.center.y, width=bounds.width, height=bounds.height)
        symbols.append((identity, center, box))
    wires = result.get('observed_wiring', []) + result.get('generated_wiring', [])
    for wire in wires:
        if wire.get('disposition') == 'rejected' or wire.get('suppression_reason'):
            continue
        if wire.get('source_evidence_required'):
            continue
        points = wire['points']
        attachments = wire.get('device_attachments', [])
        occupied = {a['point_index'] for a in attachments}
        for index in (0, len(points)-1):
            if index in occupied or index in wire.get('auto_connect_disabled_endpoints', []):
                continue
            p, adjacent = points[index], points[1 if index == 0 else index-1]
            length = math.hypot(p['x']-adjacent['x'], p['y']-adjacent['y'])
            if not length:
                continue
            choices = []
            for identity, center, box in symbols:
                if any(a['symbol_id'] == identity for a in attachments) or center == adjacent:
                    continue
                circuit = wire.get('circuit_id') or wire.get('circuit_ref')
                if circuit and any(other.get('disposition') != 'rejected' and not other.get('suppression_reason')
                    and (other.get('circuit_id') or other.get('circuit_ref')) not in (None, circuit)
                    and any(a['symbol_id'] == identity for a in other.get('device_attachments', [])) for other in wires):
                    continue
                distance = math.hypot(p['x']-center['x'], p['y']-center['y'])
                tolerance = max(2, min(8, min(box['width'], box['height'])*.3)) if box else 2
                if box:
                    if not (box['x']-2 <= p['x'] <= box['x']+box['width']+2
                            and box['y']-2 <= p['y'] <= box['y']+box['height']+2):
                        continue
                    # Glyph tips/nearby grids are not independent device ports.
                    perpendicular = abs((center['x']-p['x'])*(adjacent['y']-p['y'])
                                        -(center['y']-p['y'])*(adjacent['x']-p['x']))/length
                    if perpendicular > tolerance:
                        continue
                elif distance > tolerance:
                    continue
                choices.append((distance, identity, center))
            choices.sort(key=lambda item: (item[0], item[1]))
            if not choices or (len(choices)>1 and abs(choices[0][0]-choices[1][0]) < 1):
                continue
            _, identity, center = choices[0]
            points[index] = dict(center)
            attachments = [*attachments, dict(symbol_id=identity, point_index=index)]
        if attachments:
            wire['device_attachments'] = attachments
    return result
