"""Approved catalog line-pattern semantics, not conductor or price inference."""
from copy import deepcopy
import re

from sqlalchemy import select

from app.models import SymbolLegend
from app.services.pdf_legend_catalog import is_wiring_legend


def annotate_wiring(session, candidate, review=None, *, drawing_name=None):
    """Enrich a COPY; never rewrite immutable candidate/review evidence.

    The owner authorized reuse of these approved meanings on similar drawings.
    An explicit active wiring legend wins over the generic pattern match.
    """
    legends={row.id:row for row in session.scalars(select(SymbolLegend).where(
        SymbolLegend.is_active.is_(True), SymbolLegend.name.like("Raceway conduit concealed %")))
        if is_wiring_legend(row.name)}
    patterns={}
    for row in sorted(legends.values(),key=lambda row:row.id):
        style="dashed" if row.name.startswith("Raceway conduit concealed under floor") else "solid"
        patterns.setdefault(style,row)
    # Source intent sets a preview default, never conductor specifications.
    # Explicit drawing/manual legend assignments still win, including floor runs.
    title=' '.join([drawing_name or '', *(item.text for item in candidate.payload.ocr.items)])
    lighting=bool(re.search(r'lighting|light[\s_-]*layout',title,re.I))
    source={w.id:w for w in candidate.payload.observed_routes.segments}
    drawing_specific=any(w.code=='drawing_legend_required' for w in candidate.payload.warnings)
    methods={'concealed_under_floor':'dashed','concealed_in_ceiling':'solid'}
    document=deepcopy(review) if review is not None else {}
    if "observed_wiring" not in document:
        document["observed_wiring"]=[dict(id=w.id, disposition="unresolved",
            points=[p.model_dump() for p in w.points], completeness="partial",
            elevation_meters=None, line_style=w.line_style) for w in source.values()]
    for wire in document["observed_wiring"]:
        original=source.get(wire["id"])
        style=wire.get("line_style","unknown")
        if style=="unknown" and original:
            style=original.line_style
        explicit_id=wire.get("wiring_legend_id")
        # Never silently replace a drawing-specific mapping whose catalog
        # entry became inactive/unavailable with a generic different entry.
        automatic=wire.get('disposition','unresolved')=='unresolved'
        # A designer extension inherits its network's installation independently
        # of its stroke style. Reclassifying an unknown/solid stroke here used to
        # break a valid junction immediately before saving it.
        method=wire.get('installation_method') if not automatic or wire.get('path_origin')=='manual' else None
        legend=legends.get(explicit_id) if explicit_id is not None else None if drawing_specific else patterns.get(
            methods.get(method) or ('solid' if lighting and automatic and style in ('solid','dashed') else style))
        wire.update(line_style=style, wiring_legend_id=legend.id if legend else None,
                    wiring_legend_name=legend.name if legend else None,
                    installation_method=("concealed_under_floor" if legend.name.startswith(
                        "Raceway conduit concealed under floor") else "concealed_in_ceiling") if legend else method if method in methods else "unknown")
    # A continuous solid terminal curve does not change a dashed parent run's
    # installation convention. Only source-backed recovery junctions supply
    # this context; arbitrary nearby paths and human assignments are untouched.
    by_id={w['id']:w for w in document['observed_wiring']}
    # New source-backed box continuations share their established parent route's
    # placement. A short solid bend is not a new ceiling circuit. Designer edits,
    # explicit heights/circuits and historical attachment records always win.
    nodes={}
    for contact in candidate.payload.observed_routes.connections:
        if contact.route_node_id and contact.evidence_kind and contact.ambiguity=='unambiguous':
            nodes.setdefault(contact.route_node_id,set()).add(contact.from_ref.split(':',1)[1])
    groups=[]
    for members in nodes.values():
        joined=set(members);others=[]
        for group in groups:
            if group&joined:joined|=group
            else:others.append(group)
        groups=others+[joined]
    for group in groups:
        members=[by_id[identity] for identity in group if identity in by_id]
        if not members or any(w.get('disposition','unresolved')!='unresolved' or w.get('path_origin')=='manual' or w.get('circuit_id') or w.get('height_above_floor_meters') is not None or w.get('elevation_meters') is not None for w in members):continue
        parent=max(members,key=lambda w:sum(((b.x-a.x)**2+(b.y-a.y)**2)**.5 for a,b in zip(source[w['id']].points,source[w['id']].points[1:])))
        for child in members:
            for key in ('wiring_legend_id','wiring_legend_name','installation_method'):child[key]=parent.get(key)
    for junction in candidate.payload.observed_routes.junctions:
        parent=by_id.get(junction.members[0].segment_id)
        if not parent:continue
        for member in junction.members[1:]:
            child=by_id.get(member.segment_id)
            if child and child.get('disposition','unresolved')=='unresolved':
                for key in ('wiring_legend_id','wiring_legend_name','installation_method'):child[key]=parent.get(key)
    # Generated paths inherit a connected trace's type in the router. Client
    # copies cannot inject catalog names or arbitrary engineering meanings.
    for wire in document.get("generated_wiring",[]):
        unresolved=wire.get('assignment_state')=='unresolved'
        if unresolved and wire.get('disposition')=='unresolved':
            shared={a['junction_id'] for a in wire.get('junction_attachments',[])}
            parents=[parent for parent in document['observed_wiring'] if parent.get('disposition')!='rejected' and any(a['junction_id'] in shared for a in parent.get('junction_attachments',[]))]
            keys=('installation_method','wiring_legend_id','wiring_legend_name','circuit_id','height_above_floor_meters','elevation_meters')
            if parents and len({tuple(parent.get(key) for key in keys) for parent in parents})==1:
                for key in keys:
                    if key in parents[0]:wire[key]=parents[0][key]
        method=wire.get('installation_method')
        explicit_id=wire.get('wiring_legend_id')
        legend=legends.get(explicit_id) if explicit_id is not None else None if drawing_specific else (
            patterns.get(methods[method]) if method in methods else
            patterns.get('solid') if not unresolved and lighting and wire.get('disposition')=='unresolved' else None)
        wire.update(wiring_legend_id=legend.id if legend else None,
                    wiring_legend_name=legend.name if legend else None,
                    installation_method=("concealed_under_floor" if legend.name.startswith(
                        "Raceway conduit concealed under floor") else "concealed_in_ceiling") if legend else method if method in methods else "unknown")
    return document
