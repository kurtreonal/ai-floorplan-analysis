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
    terminals = {}
    members = 0
    for wire in active:
        for contact in wire.get('junction_attachments', []):
            members += 1
            index = contact['point_index']
            if not 0 <= index < len(wire['points']):
                raise ValueError('Junction vertex is unavailable.')
            junctions.setdefault(contact['junction_id'], []).append((wire, wire['points'][index]))
        for contact in wire.get('device_attachments', []):
            # Old symbol-only bindings do not establish which electrical/design
            # terminal is shared. Never merge their bounding boxes implicitly.
            if contact.get('terminal_id'):
                members += 1
                index = contact['point_index']
                if not 0 <= index < len(wire['points']):
                    raise ValueError('Terminal vertex is unavailable.')
                terminals.setdefault((contact['symbol_id'],contact['terminal_id']), []).append((wire,wire['points'][index]))
    if len(junctions)+len(terminals) > 4096 or members > 16384:
        raise ValueError('Wiring network resource limit reached.')
    for key, contacts in [(('junction',key),rows) for key,rows in junctions.items()] + [(('terminal',key),rows) for key,rows in terminals.items()]:
        if key[0] == 'junction' and len({w['id'] for w, _ in contacts}) < 2:
            raise ValueError('A junction requires at least two active wiring paths.')
        first, anchor = contacts[0]
        for wire, point in contacts[1:]:
            if (point != anchor or wire.get('elevation_meters') != first.get('elevation_meters')
                or wire.get('height_above_floor_meters') != first.get('height_above_floor_meters')
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
    wires = [dict(w, origin=(w.get('path_origin') or 'observed') if category == 'observed_wiring' else 'generated')
             for category in ('observed_wiring','generated_wiring') for w in document.get(category, [])
             if w.get('disposition') != 'rejected' and not w.get('suppression_reason')
             and (category!='generated_wiring' or w.get('disposition') in ('accepted','corrected','added'))]
    # Pending panel proposals are displayed but excluded from measured takeoff.
    # Their source-side junction may consequently have only one included member.
    # Remove that binding ONLY from this calculation projection, after validating
    # that its complete displayed node is sound. Saved topology stays untouched.
    selected={w['id'] for w in wires}
    omitted={w['id']:w for w in document.get('generated_wiring',[])
             if w['id'] not in selected and w.get('disposition')!='rejected' and not w.get('suppression_reason')}
    if omitted:
        contacts={}
        for wire in wires+list(omitted.values()):
            for attachment in wire.get('junction_attachments',[]):
                contacts.setdefault(attachment['junction_id'],[]).append((wire,attachment))
        projected=set()
        for identity,rows in contacts.items():
            if len({w['id'] for w,_ in rows if w['id'] in selected})!=1 or not any(w['id'] in omitted for w,_ in rows):continue
            node=[dict(w,junction_attachments=[a],device_attachments=[]) for w,a in rows]
            wire_networks(node)  # Conflicting positions/assignments must still fail.
            projected.add(identity)
        wires=[dict(w,junction_attachments=[a for a in w.get('junction_attachments',[])
                                            if a['junction_id'] not in projected]) for w in wires]
    networks = wire_networks(wires)
    groups = {}
    for wire in wires:
        key = (networks[wire['id']],wire['origin'],wire.get('wiring_legend_id'),wire.get('wiring_legend_name'),
               wire.get('installation_method','unknown'),wire.get('elevation_meters'),wire.get('circuit_id'),
               wire.get('height_above_floor_meters'),wire.get('conductor_count'))
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
