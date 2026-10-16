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
        legend=legends.get(explicit_id) if explicit_id is not None else None if drawing_specific else patterns.get(
            'solid' if lighting and automatic and style in ('solid','dashed') else style)
        wire.update(line_style=style, wiring_legend_id=legend.id if legend else None,
                    wiring_legend_name=legend.name if legend else None,
                    installation_method=("concealed_under_floor" if legend.name.startswith(
                        "Raceway conduit concealed under floor") else "concealed_in_ceiling") if legend else "unknown")
    # A continuous solid terminal curve does not change a dashed parent run's
    # installation convention. Only source-backed recovery junctions supply
    # this context; arbitrary nearby paths and human assignments are untouched.
    by_id={w['id']:w for w in document['observed_wiring']}
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
        if wire.get('assignment_state')=='unresolved':
            wire.update(wiring_legend_id=None,wiring_legend_name=None,installation_method='unknown')
            continue
        explicit_id=wire.get('wiring_legend_id')
        legend=legends.get(explicit_id) if explicit_id is not None else None if drawing_specific else (
            patterns.get('solid') if lighting and wire.get('disposition')=='unresolved' else None)
        wire.update(wiring_legend_id=legend.id if legend else None,
                    wiring_legend_name=legend.name if legend else None,
                    installation_method=("concealed_under_floor" if legend.name.startswith(
                        "Raceway conduit concealed under floor") else "concealed_in_ceiling") if legend else "unknown")
    return document
