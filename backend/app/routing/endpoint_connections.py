"""Advisory endpoint contacts, never crossing-based junctions or circuit merging."""
from copy import deepcopy
import math
import re


def connect_touching_endpoints(candidate, document):
    result = deepcopy(document)
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
