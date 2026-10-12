"""Reviewable gang-count proposals; never rewrite the trained prediction.

No OCR is fabricated: the current CV helper's SYM_n tokens are not text.
The requested one-gang fallback applies only to an already identified gang
switch, never an unknown glyph, homerun, fan switch or three-way switch.
"""
import re
from app.ai.floor_plan_interpretation.candidate import (
    CandidateCollection, CandidateWarning, FloorPlanInterpretationPayload, SwitchGangProposal,
)

VERSION='provisional-switch-gang-count-v1'


def named_gang_count(name):
    value=re.search(r'\b(one|two|three|1|2|3)[ -]*gang\b',name,re.I)
    return {'one':1,'two':2,'three':3,'1':1,'2':2,'3':3}.get(value.group(1).lower()) if value else None


def with_switch_gang_proposals(payload):
    rows=[];defaults=[]
    for symbol in payload.symbols.items:
        training=getattr(symbol,'training_legend',None)
        name=training.name if training else symbol.observed_label or ''
        # Drawing-specific existing class wins; a generic family is not enough
        # to relabel a circuit annotation or special-function switch.
        if not re.search(r'\bgang\b',name,re.I) or not re.search(r'\bswitch\b',name,re.I):
            rows.append(symbol);continue
        count=named_gang_count(name);basis='model_prediction'
        readable=set()
        if symbol.bounds:
            b=symbol.bounds
            for text in payload.ocr.items:
                token=re.fullmatch(r'S\s*([123])',text.normalized_text.strip(),re.I)
                x=text.bounds.x+text.bounds.width/2;y=text.bounds.y+text.bounds.height/2
                if token and b.x<=x<=b.x+b.width and b.y<=y<=b.y+b.height:
                    readable.add(int(token.group(1)))
        if len(readable)==1:
            count=readable.pop();basis='source_text'
        elif len(readable)>1:
            # Conflicting readable designations require review, not a fallback.
            rows.append(symbol);continue
        if count is None:
            count=1;basis='user_requested_default';defaults.append(symbol.id)
        rows.append(symbol.model_copy(update={'gang_count_proposal':SwitchGangProposal(count=count,basis=basis)}))
    warnings=tuple(w for w in payload.warnings if w.code!='switch_gang_provisional_default')
    if defaults:
        if len(warnings)>=256:return payload
        warnings+=(CandidateWarning(code='switch_gang_provisional_default',severity='warning',
            entity_refs=tuple(f'symbol:{i}' for i in defaults[:64]),
            message='One gang is a user-requested provisional default, not a visually established count. Original predictions remain unchanged. Correct the gang count before final layout approval or training.'),)
    return FloorPlanInterpretationPayload.model_validate(payload.model_copy(update={
        'symbols':CandidateCollection(state=payload.symbols.state,items=tuple(rows),truncated=payload.symbols.truncated),
        'warnings':warnings}).model_dump())
