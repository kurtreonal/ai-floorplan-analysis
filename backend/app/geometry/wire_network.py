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


def takeoff_path_groups(document):
    """Only explicit junction components share physical spans in draft takeoff.

    Different provenance/material/installation groups remain separately costed.
    Shared circuit wording alone never proves a shared physical raceway.
    """
    wires = [dict(w, origin='observed' if category == 'observed_wiring' else 'generated')
             for category in ('observed_wiring','generated_wiring') for w in document.get(category, [])
             if w.get('disposition') != 'rejected' and not w.get('suppression_reason')]
    networks = wire_networks(wires)
    groups = {}
    for wire in wires:
        key = (networks[wire['id']],wire['origin'],wire.get('wiring_legend_id'),wire.get('wiring_legend_name'),
               wire.get('installation_method','unknown'),wire.get('elevation_meters'),wire.get('circuit_id'))
        groups.setdefault(key, []).append(wire)
    by_network = {}
    for key, group in groups.items(): by_network.setdefault(key[0], []).append(group)
    result = []
    from app.geometry.path_lengths import unique_paths_length
    for material_groups in by_network.values():
        flat = [w for group in material_groups for w in group]
        separate = sum(unique_paths_length([w['points'] for w in group]) for group in material_groups)
        physical = unique_paths_length([w['points'] for w in flat])
        if len(material_groups) > 1 and separate-physical > 1e-8:
            # Geometry is known; choosing which material owns its shared span
            # is not. Count the physical network once but block its pricing.
            result.append([dict(w,takeoff_material_conflict=True) for w in flat])
        else: result.extend(material_groups)
    return result
