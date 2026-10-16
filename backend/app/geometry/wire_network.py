"""Explicit draft junction topology; coincident pixels never imply connectivity."""


def wire_networks(wires):
    active = [w for w in wires if w.get('disposition') != 'rejected' and not w.get('suppression_reason')]
    parents = {w['id']: w['id'] for w in active}
    if len(parents) != len(active):
        raise ValueError('Duplicate wiring identity.')
    def root(identity):
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity
    junctions = {}
    members = 0
    for wire in active:
        for contact in wire.get('junction_attachments', []):
            members += 1
            index = contact['point_index']
            if not 0 <= index < len(wire['points']):
                raise ValueError('Junction vertex is unavailable.')
            junctions.setdefault(contact['junction_id'], []).append((wire, wire['points'][index]))
    if len(junctions) > 4096 or members > 16384:
        raise ValueError('Wiring network resource limit reached.')
    for contacts in junctions.values():
        if len({w['id'] for w, _ in contacts}) < 2:
            raise ValueError('A junction requires at least two active wiring paths.')
        first, anchor = contacts[0]
        for wire, point in contacts[1:]:
            if (point != anchor or wire.get('elevation_meters') != first.get('elevation_meters')
                or (wire.get('origin') == 'generated') != (first.get('origin') == 'generated')
                or wire.get('circuit_id') != first.get('circuit_id')
                or wire.get('installation_method', 'unknown') != first.get('installation_method', 'unknown')):
                raise ValueError('Joined paths require one anchor, elevation, circuit assignment and installation method.')
            a, b = root(first['id']), root(wire['id'])
            parents[max(a, b)] = min(a, b)
    return {identity: root(identity) for identity in parents}
