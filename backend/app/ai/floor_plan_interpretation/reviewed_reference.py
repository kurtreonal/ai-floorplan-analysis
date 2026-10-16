"""Source-bound manual replacement drafts, never detector or training truth."""
from copy import deepcopy


def _manual_replacement(document, key, prefix, extra=()):
    rows = document.get(key, [])
    manual = [row for row in rows if row['id'].startswith(prefix)]
    automatic = [row for row in rows if not row['id'].startswith(prefix)] + list(extra)
    return bool(automatic and manual
                and all(row['disposition'] == 'rejected' for row in automatic))


def has_manual_wiring_replacement(document):
    """Explicitly removing ALL automatic paths and adding manual paths is intent.

    Merely adding one wire must not disable the ordinary automatic workflow.
    Include rejected manual paths so deleting one never resurrects it.
    """
    return _manual_replacement(document or {}, 'observed_wiring', 'manual-wiring-',
                               (document or {}).get('generated_wiring', []))


def inherit_manual_reference(candidate, previous_candidate, previous_document):
    """Keep only complete manual replacements on the exact same source plane.

    Caller enforces floor-plan/page identity. Never reuse detector IDs, symbol
    anchors, approvals, scale, or inferred circuits across runs. Changed drawing
    regions fail closed even when they share the full-page coordinate plane.
    """
    if (candidate.provenance.source_sha256 != previous_candidate.provenance.source_sha256
            or candidate.payload.source_plane != previous_candidate.payload.source_plane
            or [(r.kind, r.bounds) for r in candidate.payload.regions if r.kind == 'plan_region']
            != [(r.kind, r.bounds) for r in previous_candidate.payload.regions if r.kind == 'plan_region']):
        return {}
    result = {}
    if has_manual_wiring_replacement(previous_document):
        result['observed_wiring'] = [dict(id=w.id, disposition='rejected',
            points=[p.model_dump() for p in w.points], completeness='partial',
            elevation_meters=None, line_style=w.line_style)
            for w in candidate.payload.observed_routes.segments]
        result['observed_wiring'] += deepcopy([w for w in previous_document['observed_wiring']
                                              if w['id'].startswith('manual-wiring-')])
        result['generated_wiring'] = []
    if _manual_replacement(previous_document, 'walls', 'manual-wall-'):
        result['walls'] = [dict(id=w.id, disposition='rejected',
            start=w.start.model_dump(), end=w.end.model_dump())
            for w in candidate.payload.walls.items]
        result['walls'] += deepcopy([w for w in previous_document['walls']
                                    if w['id'].startswith('manual-wall-')])
    return result


def inherit_review_draft(candidate, previous_candidate, previous_document):
    """Rebase source-bound corrections by exact evidence, never nearest device.

    Raw candidates remain immutable and separately available. Unmatched human
    geometry is kept as manual draft geometry; it is not detector truth. No
    layout, circuit, measurement or dataset approval crosses the run boundary.
    """
    if (candidate.provenance.source_sha256 != previous_candidate.provenance.source_sha256
            or candidate.payload.source_plane != previous_candidate.payload.source_plane
            or [(r.kind, r.bounds) for r in candidate.payload.regions if r.kind == 'plan_region']
            != [(r.kind, r.bounds) for r in previous_candidate.payload.regions if r.kind == 'plan_region']):
        return {}
    fields = {'walls': ('start', 'end'), 'rooms': ('boundary',),
              'symbols': ('center',), 'observed_wiring': ('points',)}
    attached_symbols = {a['symbol_id'] for key in ('observed_wiring', 'generated_wiring')
        for w in previous_document.get(key, []) if w['disposition'] != 'rejected'
        for a in w.get('device_attachments', []) if w.get('disposition') != 'unresolved'
        or a.get('provenance') != 'source_supported_proposal'}
    mounted_walls = {s['mounting_wall_id'] for s in previous_document.get('symbols', [])
        if s.get('mounting_wall_id') and s['disposition'] != 'rejected'}
    for wire in previous_document.get('generated_wiring', []):
        if wire.get('disposition') in ('corrected', 'added'):
            attached_symbols.add(wire['source_device_id'])
            if wire.get('target_kind') == 'device': attached_symbols.add(wire['target_id'])
    result, identities = {}, {}
    def rows(payload, key):
        return (payload.observed_routes.segments if key == 'observed_wiring'
                else getattr(payload, key).items)
    def evidence(item, key):
        value = item.model_dump(mode='json')
        signature = {field: value[field] for field in fields[key]}
        if key == 'symbols':
            signature['class_id'] = value.get('catalog_class_id')
            signature['legend_entry'] = (value.get('training_legend') or {}).get('legend_entry')
            signature['observed_label'] = value.get('observed_label')
        return signature
    for key in fields:
        if key not in previous_document:
            continue
        current, previous = list(rows(candidate.payload, key)), list(rows(previous_candidate.payload, key))
        lookup = {item.id: item for item in previous}
        defaults = []
        for item in current:
            value = item.model_dump(mode='json')
            row = {'id': item.id, 'disposition': 'unresolved',
                   **{field: value[field] for field in fields[key]}}
            if key == 'rooms': row['name'] = value.get('label')
            if key == 'walls' and value.get('estimated_thickness_pixels') is not None:
                row['estimated_thickness_pixels']=value['estimated_thickness_pixels']
            if key == 'symbols': row['symbol_legend_id'] = None
            if key == 'observed_wiring':
                row.update(completeness='partial', elevation_meters=None, line_style=value['line_style'])
            defaults.append(row)
        prefix = 'manual-wiring-' if key == 'observed_wiring' else f'manual-{key[:-1]}-'
        counter = max([int(row['id'][-4:]) for row in previous_document[key]
                       if row['id'].startswith(prefix)] or [0])
        claimed = set()
        for saved in previous_document[key]:
            # Unresolved unedited machine observations are fresh proposals, not
            # corrections. Explicit metadata/position changes still survive.
            old = lookup.get(saved['id'])
            edited = old is None or any(saved.get(f) != old.model_dump(mode='json').get(f) for f in fields[key])
            edited |= key == 'symbols' and (saved.get('symbol_legend_id') is not None or saved.get('custom_unit_price') is not None)
            edited |= key == 'symbols' and any(saved.get(f) is not None for f in ('mounting_height_meters', 'mounting_wall_id'))
            edited |= key == 'observed_wiring' and bool(saved.get('device_attachments') or
                saved.get('junction_attachments') or saved.get('circuit_id') or saved.get('auto_connect_disabled_endpoints') or saved.get('elevation_meters') is not None
                or saved.get('completeness', 'partial') != 'partial')
            if key == 'observed_wiring' and old is not None and saved['disposition']=='unresolved':
                attachments=saved.get('device_attachments', [])
                junctions=saved.get('junction_attachments',[])
                if ((attachments or junctions) and all(a.get('provenance')=='source_supported_proposal' for a in attachments)
                    and all(a.get('source_candidate_run_id') for a in junctions)
                    and not saved.get('auto_connect_disabled_endpoints') and saved.get('elevation_meters') is None
                    and not saved.get('circuit_id')
                    and saved.get('completeness','partial')=='partial'):
                    from app.routing.endpoint_connections import apply_source_contacts
                    baseline=apply_source_contacts(previous_candidate,{'observed_wiring':[dict(
                        id=old.id,disposition='unresolved',points=[p.model_dump() for p in old.points])]},
                        preserve_source=all(a.get('geometry_version')=='source_preserving_v1' for a in attachments))
                    if baseline['observed_wiring'][0]['points']==saved['points']:
                        edited=False # Machine proposals are not human corrections.
            edited |= (key == 'symbols' and saved['id'] in attached_symbols) or (key == 'walls' and saved['id'] in mounted_walls)
            if key=='walls' and saved.get('estimated_thickness_pixels') is not None and old is not None:
                edited |= saved['estimated_thickness_pixels']!=old.estimated_thickness_pixels
            # Unfinished editing defaulted AI walls to accepted without a human
            # approval. Regenerate those untouched snapshots in NEW proposals.
            unchanged_wall_snapshot=(key=='walls' and saved['disposition']=='accepted'
                and not previous_document.get('approved_for_layout')
                and not previous_document.get('review_complete'))
            if (saved['disposition']=='unresolved' or unchanged_wall_snapshot) and not edited:
                matches = [item for item in current if old is not None and evidence(item, key) == evidence(old, key)]
                if len(matches) == 1:
                    identities[saved['id']] = matches[0].id
                continue
            matches = [i for i, item in enumerate(current) if i not in claimed
                       and old is not None and evidence(item, key) == evidence(old, key)]
            row = deepcopy(saved)
            if len(matches) == 1:
                index = matches[0]; claimed.add(index)
                row['id'] = current[index].id
                defaults[index] = row
            else:
                if not row['id'].startswith(prefix):
                    counter += 1
                    if counter > 9999: raise ValueError('Draft identity limit exceeded')
                    row['id'] = f'{prefix}{counter:04d}'
                defaults.append(row)
            identities[saved['id']] = row['id']
        result[key] = defaults
    # Complete replacement intent also suppresses new alternatives, including
    # when a fresh scan produces no observed traces at all.
    result.update(inherit_manual_reference(candidate, previous_candidate, previous_document))
    result.setdefault('generated_wiring', [])
    for saved in previous_document.get('generated_wiring', []):
        if saved['disposition'] not in ('corrected', 'added', 'rejected'):
            continue
        source, target = identities.get(saved['source_device_id']), identities.get(saved['target_id'])
        if source and target:
            result['generated_wiring'].append({**deepcopy(saved), 'source_device_id': source, 'target_id': target})
    for key in ('observed_wiring', 'generated_wiring'):
        for wire in result.get(key, []):
            if 'device_attachments' in wire:
                wire['device_attachments'] = [{**attachment, 'symbol_id': identities[attachment['symbol_id']]}
                    for attachment in wire['device_attachments'] if attachment['symbol_id'] in identities]
    for symbol in result.get('symbols', []):
        if symbol.get('mounting_wall_id'):
            symbol['mounting_wall_id'] = identities.get(symbol['mounting_wall_id'])
    return result
