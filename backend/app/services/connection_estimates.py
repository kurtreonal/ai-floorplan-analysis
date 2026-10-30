"""Budget-only connection assumptions; never persist inferred junctions/geometry."""
from collections import Counter
from copy import deepcopy
from statistics import median
import re
from app.geometry.wire_network import wire_networks


def apply_connection_estimates(document,*,ceiling_height):
    prepared=deepcopy(document)
    proposals=[w for w in prepared.get('generated_wiring',[]) if w.get('assignment_state')=='unresolved'
        and w.get('disposition') in ('accepted','corrected','added') and not w.get('suppression_reason')]
    if not proposals:return prepared
    active=[w for w in prepared.get('observed_wiring',[]) if w.get('disposition')!='rejected' and not w.get('suppression_reason')]
    included=active+[w for w in prepared.get('generated_wiring',[]) if w.get('disposition') in ('accepted','corrected','added') and not w.get('suppression_reason')]
    networks=wire_networks(included)
    affected={networks[w['id']] for w in proposals}
    votes=Counter(w['installation_method'] for w in active if w.get('installation_method') in ('concealed_in_ceiling','concealed_under_floor'))
    method=votes.most_common(1)[0][0] if votes else 'concealed_in_ceiling'
    symbols={s['id']:s for s in prepared.get('symbols',[]) if s.get('disposition')!='rejected'}
    for network in affected:
        members=[w for w in included if networks[w['id']]==network]
        inherited=next((w['installation_method'] for w in members if w.get('installation_method') in ('concealed_in_ceiling','concealed_under_floor')),method)
        heights=[w['height_above_floor_meters'] for w in members if w.get('height_above_floor_meters') is not None]
        if not heights:heights=[w['height_above_floor_meters'] for w in active if w.get('installation_method')==inherited and w.get('height_above_floor_meters') is not None]
        height=median(heights) if heights else 0 if inherited=='concealed_under_floor' else ceiling_height
        for wire in members:
            if wire.get('installation_method') not in ('concealed_in_ceiling','concealed_under_floor'):
                wire['installation_method']=inherited
            if wire.get('height_above_floor_meters') is None and wire.get('elevation_meters') is None:
                wire.update(height_above_floor_meters=height,connection_height_assumed=True)
    for wire in proposals:
        wire.update(assignment_state=None,connection_assumed=True)
        attachments=list(wire.get('device_attachments',[]))
        endpoints=[(0,wire.get('source_device_id')),(len(wire['points'])-1,wire.get('target_id') if wire.get('target_kind')=='device' else None)]
        for index,identity in endpoints:
            symbol=symbols.get(identity)
            if not symbol:continue
            name=symbol.get('class_name') or symbol.get('name') or ''
            # A homerun mark is at route level, rather than a mounted device.
            if re.search(r'home.?run|circuit.*notation',name,re.I):continue
            if not any(a.get('point_index')==index for a in attachments):
                attachments.append(dict(point_index=index,symbol_id=identity))
            # Recognized panel equipment uses an editable budget assumption only
            # where the designer has supplied no individual mounting height.
            if re.search(r'\bpanel\s*board\b|\bpanelboard\b',name,re.I):
                if symbol.get('mounting_height_meters') is None:
                    symbol.update(mounting_height_meters=1.8,mounting_height_source='ved_default')
                if symbol.get('mounting_reference') not in ('device_center','box_bottom','connection_terminal'):
                    symbol['mounting_reference']='device_center'
        wire['device_attachments']=attachments
    return prepared
