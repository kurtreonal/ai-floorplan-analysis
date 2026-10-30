"""Bounded, resumable source inspection, not circuit completion or training.

Different local pixel methods inspect bounded device neighborhoods, including
already served devices with potentially missing path continuation.
Agreement is not confidence. New geometry must add source-supported path
coverage; an already contacted device can still have missing continuation.
Existing observations and approval are never replaced.
"""
from dataclasses import dataclass
from time import monotonic
import math
import re
import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload, ObservedRouteSegment, PixelPoint,
    WiringRecoveryReport, WiringRecoveryPass, WiringRecoveryDevice, CandidateWarning,
    ObservedJunction, ObservedJunctionMember,
)
from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence
from app.ai.floor_plan_interpretation.stroke_centerlines import stroke_paths

VERSION = 'targeted-source-recovery-v4'
METHODS = ('native_local_strokes', 'contrast_local_strokes')


@dataclass(frozen=True)
class RecoveryLimits:
    maximum_windows: int = 64
    maximum_seconds: float = 90
    maximum_paths: int = 256

    def __post_init__(self):
        if (type(self.maximum_windows) is not int or not 1 <= self.maximum_windows <= 512
            or not math.isfinite(self.maximum_seconds) or not 1 <= self.maximum_seconds <= 600
            or type(self.maximum_paths) is not int or not 1 <= self.maximum_paths <= 512):
            raise ValueError('Invalid recovery resource limits.')


def device_symbols(payload):
    return [s for s in payload.symbols.items if not re.search(
        r'home.?run|circuit.*notation|raceway conduit',
        s.training_legend.name if s.training_legend else s.observed_label or '', re.I)]


def eligible_symbols(payload):
    return [s for s in device_symbols(payload) if s.bounds]


def in_plan(payload, symbol):
    return any(r.kind == 'plan_region' and r.bounds and
        r.bounds.x <= symbol.center.x <= r.bounds.x+r.bounds.width and
        r.bounds.y <= symbol.center.y <= r.bounds.y+r.bounds.height for r in payload.regions)


def served_symbols(payload):
    return {c.to_ref.split(':',1)[1] for c in payload.observed_routes.connections
            if c.evidence_kind and c.ambiguity == 'unambiguous' and c.to_ref.startswith('symbol:')}


def audit_devices(payload, image, *, exhausted=False, failed=False):
    served = served_symbols(payload)
    ambiguous = {c.to_ref.split(':',1)[1] for c in payload.observed_routes.connections
                 if c.ambiguity == 'ambiguous' and c.to_ref.startswith('symbol:')}
    gray = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    padding=max(2,min(6,round(min(image.shape[:2])*.0015)))
    result = []
    for symbol in device_symbols(payload)[:512]:
        if symbol.id in served:
            state,reason = 'observed_recovered','source_supported_attachment'
        elif symbol.id in ambiguous:
            state,reason = 'unresolved_observed','ambiguous_contact'
        elif not symbol.bounds:
            state,reason = 'unresolved_observed','missing_symbol_bounds'
        elif not in_plan(payload, symbol):
            state,reason = 'unresolved_observed','outside_plan_scope'
        elif exhausted:
            state,reason = 'unresolved_observed','resource_limit'
        elif failed:
            state,reason = 'unresolved_observed','recovery_method_failed'
        else:
            box = symbol.bounds
            radius = max(3,round(min(box.width,box.height)))
            left,top = max(0,math.floor(box.x)-radius),max(0,math.floor(box.y)-radius)
            right,bottom = min(image.shape[1],math.ceil(box.x+box.width)+radius),min(image.shape[0],math.ceil(box.y+box.height)+radius)
            patch = gray[top:bottom,left:right].copy()
            patch[max(0,math.floor(box.y)-top-padding):math.ceil(box.y+box.height)-top+padding+1,
                  max(0,math.floor(box.x)-left-padding):math.ceil(box.x+box.width)-left+padding+1] = 255
            # This is an unresolved-evidence flag, never a wall/wire classifier.
            has_ink = int((patch < 180).sum()) >= max(12,radius)
            state,reason = ('unresolved_observed','partial_source_evidence') if has_ink else (
                'no_usable_observed_path','no_supported_path_after_search')
        result.append(WiringRecoveryDevice(symbol_id=symbol.id,state=state,reason=reason))
    return tuple(result)


def local_paths(payload, image, symbol, method):
    """Native-resolution window; integer translation is the ONLY transform."""
    box = symbol.bounds
    # Existing source spans provide drawing-specific spacing evidence. A glyph-
    # only window can clip the continuation before its next device even though
    # both devices already have valid contacts on other arms of the network.
    incident={c.from_ref for c in payload.observed_routes.connections
              if c.to_ref==f'symbol:{symbol.id}' and c.evidence_kind and c.ambiguity=='unambiguous'}
    context=max((math.hypot(p.x-symbol.center.x,p.y-symbol.center.y)
                 for r in payload.observed_routes.segments if f'segment:{r.id}' in incident
                 for p in r.points),default=0)
    radius = max(24,min(768,math.ceil(max(max(box.width,box.height)*8,context*2))))
    x,y = max(0,math.floor(symbol.center.x)-radius),max(0,math.floor(symbol.center.y)-radius)
    right,bottom = min(image.shape[1],math.ceil(symbol.center.x)+radius+1),min(image.shape[0],math.ceil(symbol.center.y)+radius+1)
    gray = cv2.cvtColor(image[y:bottom,x:right],cv2.COLOR_RGB2GRAY)
    if method == 'contrast_local_strokes':
        gray = cv2.createCLAHE(clipLimit=2,tileGridSize=(8,8)).apply(gray)
        mask = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,12)
        # Alternate structural-line separation: only the stronger stroke cores
        # survive. Native thin-wire proposals remain untouched in the first
        # method; contact/source gates still decide whether these are wires.
        mask = cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    else:
        _,mask = cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    scope = np.zeros_like(mask)
    refs = []
    for region in payload.regions:
        b = region.bounds
        if region.kind != 'plan_region' or not b or not (b.x <= symbol.center.x <= b.x+b.width and b.y <= symbol.center.y <= b.y+b.height): continue
        refs.append(f'region:{region.id}')
        scope[max(0,math.ceil(b.y)-y):max(0,min(bottom,math.floor(b.y+b.height)+1)-y),
              max(0,math.ceil(b.x)-x):max(0,min(right,math.floor(b.x+b.width)+1)-x)] = 255
    if not refs: return []
    mask &= scope
    for device in payload.symbols.items:
        b = device.bounds
        if not b: continue
        # Source outside the glyph remains intact; no arbitrary gap closing.
        mask[max(0,math.floor(b.y)-y-1):max(0,min(bottom,math.ceil(b.y+b.height)+2)-y),
             max(0,math.floor(b.x)-x-1):max(0,min(right,math.ceil(b.x+b.width)+2)-x)] = 0
    from app.ai.floor_plan_interpretation.automatic_wiring import _parallel_wall
    paths = []
    minimum = max(3,round(min(box.width,box.height)*.6))
    for chain in stroke_paths(mask,minimum_length=minimum,maximum_paths=128):
        points = tuple(PixelPoint(x=p[0]+x,y=p[1]+y) for p in chain)
        # Existing structural evidence is context, not a thickness-only rule.
        length = sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(points,points[1:]))
        structural = sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(points,points[1:])
            if _parallel_wall(((a.x,a.y),(b.x,b.y)),payload.walls.items,2,include_width=True))
        if structural > length*.8: continue
        paths.append((points,tuple(refs),'solid'))
    if method == 'contrast_local_strokes':
        # A different method, not repeated threshold lowering: collinear dash
        # evidence must pass both repeated-run and cross-stroke-direction gates.
        from app.ai.floor_plan_interpretation.automatic_wiring import _regular_dash_evidence, _dash_direction_evidence
        dash_mask = ((gray < 180).astype(np.uint8)*255) & scope
        for device in payload.symbols.items:
            b=device.bounds
            if b:
                dash_mask[max(0,math.floor(b.y)-y-1):max(0,min(bottom,math.ceil(b.y+b.height)+2)-y),
                          max(0,math.floor(b.x)-x-1):max(0,min(right,math.ceil(b.x+b.width)+2)-x)] = 0
        gap=max(3,round(min(box.width,box.height)*1.5))
        rows=cv2.HoughLinesP(dash_mask,1,math.pi/180,max(6,minimum),minLineLength=minimum*3,maxLineGap=gap)
        if rows is not None:
            for row in sorted({tuple(map(int,r[0])) for r in rows})[:128]:
                a,b=row[:2],row[2:]
                count=math.ceil(math.dist(a,b))+1
                xy=np.rint(np.linspace(a,b,count)).astype(int)
                samples=dash_mask[xy[:,1],xy[:,0]]>0
                if _regular_dash_evidence(samples,gap) and _dash_direction_evidence(a,b,samples,dash_mask):
                    points=(PixelPoint(x=a[0]+x,y=a[1]+y),PixelPoint(x=b[0]+x,y=b[1]+y))
                    paths.append((points,tuple(refs),'dashed'))
    return paths


def _duplicate(points, routes, image=None, *, symbols=(), line_style=None):
    # Coverage can belong to several existing strokes. This only rejects a
    # repeated geometry proposal; it never joins those strokes electrically.
    samples = [np.array([a.x,a.y])+(np.array([b.x,b.y])-np.array([a.x,a.y]))*t
               for a,b in zip(points,points[1:]) for t in np.linspace(0,1,9)]
    continuous=False
    if image is not None and samples:
        xy=np.rint(samples).astype(int)
        continuous=float((image[xy[:,1],xy[:,0]].mean(axis=1)<180).mean())>=.95
    # A local skeleton sees one dash as a solid stroke. Its different local
    # label must not duplicate the globally established dashed source run.
    eligible=[r for r in routes if line_style is None or r.line_style==line_style
              or (line_style=='solid' and r.line_style=='dashed' and continuous)]
    def covered(p):
        # Masked glyph interiors are not additional source-wire coverage.
        if any(s.bounds and s.bounds.x-2<=p[0]<=s.bounds.x+s.bounds.width+2
               and s.bounds.y-2<=p[1]<=s.bounds.y+s.bounds.height+2 for s in symbols):return True
        for route in eligible:
            for a,b in zip(route.points,route.points[1:]):
                start=np.array([a.x,a.y]);delta=np.array([b.x-a.x,b.y-a.y])
                t=np.clip(float((p-start)@delta/(delta@delta)),0,1)
                q=start+delta*t;distance=float(np.linalg.norm(p-q))
                if distance<=1:return True
                if image is None or distance>6:continue
                px,py=np.rint(p).astype(int);qx,qy=np.rint(q).astype(int)
                if distance<=3 and (image[py,px].mean()>=180 or image[qy,qx].mean()>=180):return True
                # Matching white dash gaps are not evidence of another path.
                # Visible stroke samples must still share one dark ink band.
                if image[py,px].mean()>=180 and image[qy,qx].mean()>=180:return True
                # Slightly different axes within ONE continuous ink band are
                # duplicate observations, not parallel physical conductors.
                xy=np.rint(np.linspace(p,q,max(3,math.ceil(distance)+1))).astype(int)
                if np.mean(image[xy[:,1],xy[:,0]].mean(axis=1)<180)>=.95:return True
                if image[xy[-1,1],xy[-1,0]].mean()>=180 and image[xy[0,1],xy[0,0]].mean()<180:
                    # An unsupported old axis beside this native stroke is
                    # coordinate uncertainty, not evidence for a SECOND wire.
                    # Keep it reviewable rather than inflate parallel routes.
                    return True
        return False
    return bool(eligible and samples and all(covered(p) for p in samples))


def _source_attachment(points, routes, image, *, endpoint_indices=None):
    """A native stroke END meets an existing source centerline, not a crossing.

    Own-stroke raster-band correction requires actual dark ink across the tiny
    contact. Multiple independent targets stay ambiguous, not nearest-wins.
    """
    choices=[]
    for index in endpoint_indices if endpoint_indices is not None else (0,len(points)-1):
        p=points[index]
        px,py=round(p.x),round(p.y)
        local=(image[max(0,py-8):py+9,max(0,px-8):px+9].mean(axis=2)<180).astype(np.uint8)
        radius=max(2,min(6,float(cv2.distanceTransform(local,cv2.DIST_L2,5).max())))
        for route in routes:
            for edge,(a,b) in enumerate(zip(route.points,route.points[1:])):
                dx,dy=b.x-a.x,b.y-a.y;l2=dx*dx+dy*dy
                t=max(0,min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/l2))
                q=PixelPoint(x=a.x+t*dx,y=a.y+t*dy)
                if math.hypot(p.x-q.x,p.y-q.y)>radius:continue
                xy=np.rint(np.linspace((p.x,p.y),(q.x,q.y),5)).astype(int)
                if np.mean(image[xy[:,1],xy[:,0]].mean(axis=1)<180)<.8:continue
                neighbor=points[1 if index==0 else index-1]
                incoming=np.array([q.x-neighbor.x,q.y-neighbor.y],dtype=float)
                incoming_length=float(np.linalg.norm(incoming))
                if incoming_length<=1e-9:continue
                incoming/=incoming_length
                trunk=np.array([dx,dy])/math.sqrt(l2)
                if abs(float(incoming@trunk))<.95:
                    # A fourth arm means an unmarked crossing, not a T. Inspect
                    # beyond the source endpoint on its incoming axis.
                    samples=np.rint(np.array([q.x,q.y])+np.arange(6,65)[:,None]*incoming).astype(int)
                    if (samples<0).any() or (samples[:,0]>=image.shape[1]).any() or (samples[:,1]>=image.shape[0]).any():continue
                    if np.mean(image[samples[:,1],samples[:,0]].mean(axis=1)<180)>.15:continue
                choices.append((route.id,index,edge,t,q))
    if len({(r,i) for r,i,_,_,_ in choices})!=1:return None
    return min(choices,key=lambda c:(c[2],c[3])) if choices else None


def _ends_at_device(points,symbol):
    box=symbol.bounds
    margin=max(2,min(box.width,box.height)*.4)
    for p,n in ((points[0],points[1]),(points[-1],points[-2])):
        if not (box.x-margin<=p.x<=box.x+box.width+margin and box.y-margin<=p.y<=box.y+box.height+margin):continue
        dx,dy=n.x-p.x,n.y-p.y;length=math.hypot(dx,dy)
        perpendicular=abs((symbol.center.x-p.x)*dy-(symbol.center.y-p.y)*dx)/length
        if perpendicular<=max(3,min(10,min(box.width,box.height)*.3)):return True
        # Proposal eligibility only. Offset fixture-side ports still require
        # the two-device, source-terminal/context gate in the contact audit.
        if re.search(r'troffer|fluorescent|downlight|ceiling light|lighting point',
                symbol.training_legend.name if symbol.training_legend else symbol.observed_label or '',re.I):
            return True
    return False


def _trim_to_network(points,symbol,routes,image):
    # Stop at the FIRST supported network contact; retaining a later dash tail
    # would draw a second parallel observation of the existing run.
    first=points[0];box=symbol.bounds
    margin=max(2,min(box.width,box.height)*.4)
    ordered=points if box.x-margin<=first.x<=box.x+box.width+margin and box.y-margin<=first.y<=box.y+box.height+margin else tuple(reversed(points))
    for last in range(1,len(ordered)):
        prefix=ordered[:last+1]
        attachment=_source_attachment(prefix,routes,image,endpoint_indices=(last,))
        if attachment:return prefix,attachment
    return points,None


def _join_source_trial(payload, route, contact):
    target_id,index,edge,t,point=contact
    segments=list(payload.observed_routes.segments)
    target=next(r for r in segments if r.id==target_id)
    target_points=list(target.points)
    if t<1e-8:vertex=edge;point=target_points[vertex]
    elif t>1-1e-8:vertex=edge+1;point=target_points[vertex]
    else:
        vertex=edge+1
        if len(target_points)>=512:return None
        target_points.insert(vertex,point)
    junctions=list(payload.observed_routes.junctions)
    if 0<t<1:
        junctions=[j.model_copy(update={'members':tuple(m.model_copy(update={'point_index':m.point_index+1})
            if m.segment_id==target_id and m.point_index>=vertex else m for m in j.members)}) for j in junctions]
    existing=next((j for j in junctions if any(m.segment_id==target_id and m.point_index==vertex for m in j.members)),None)
    points=list(route.points);points[index]=point
    if any(a==b for a,b in zip(points,points[1:])):return None
    route=route.model_copy(update={'points':tuple(points)})
    segments=[r.model_copy(update={'points':tuple(target_points)}) if r.id==target_id else r for r in segments]+[route]
    member=ObservedJunctionMember(segment_id=route.id,point_index=index)
    if existing:
        if len(existing.members)>=16:return None
        junctions=[j.model_copy(update={'members':j.members+(member,)}) if j.id==existing.id else j for j in junctions]
    else:
        number=max((int(j.id.split('-')[-1]) for j in junctions),default=0)+1
        junctions.append(ObservedJunction(id=f'junction-{number:04d}',members=(
            ObservedJunctionMember(segment_id=target_id,point_index=vertex),member),
            evidence_kind='source_corner_contact',evidence_refs=route.evidence_refs,ambiguity='clear'))
    return payload.model_copy(update={'document_state':'partial','observed_routes':payload.observed_routes.model_copy(update={
        'state':'partial','failure_reason':None,'segments':tuple(segments),'junctions':tuple(junctions)})})


def recover_wiring(payload, image, *, limits=None, check=lambda:None, checkpoint=lambda state:None, resume=None):
    limits = limits or RecoveryLimits()
    if image.shape[:2] != (payload.source_plane.height_pixels,payload.source_plane.width_pixels):
        raise ValueError('Recovery requires unchanged source coordinates.')
    base = payload
    devices = device_symbols(payload)
    symbols = sorted((s for s in eligible_symbols(payload) if in_plan(payload,s)),
                     key=lambda s:(s.center.y,s.center.x,s.id))
    target_ids={s.id for s in symbols}
    overflow=len(symbols)>512
    external_limit=image.shape[0]*image.shape[1]>12_000_000 or len(payload.symbols.items)>512 or sum(len(r.points)-1 for r in payload.observed_routes.segments)>4096
    if len(symbols)>512: symbols=symbols[:512]
    start=monotonic();spent=0.;cursor=0;method_index=0;passes=[];windows=0
    if resume:
        payload=FloorPlanInterpretationPayload.model_validate(resume['payload'])
        cursor=resume['cursor'];method_index=resume['method_index'];spent=resume['spent_seconds']
        passes=[WiringRecoveryPass.model_validate(p) for p in resume['passes']];windows=resume['windows']
    else:
        payload=with_device_contact_evidence(payload,image)
    def save():
        checkpoint(dict(payload=payload.model_dump(mode='json'),cursor=cursor,method_index=method_index,
            spent_seconds=spent+monotonic()-start,passes=[p.model_dump() for p in passes],windows=windows))
    save();check()
    reason='resource_limit' if external_limit else 'methods_exhausted'
    limit_reason='input_budget' if external_limit else None
    while method_index < len(METHODS) and not external_limit:
        method=METHODS[method_index]
        if len(passes)<=method_index: passes.append(WiringRecoveryPass(method=method,windows=0,added_paths=0,added_contacts=0))
        while cursor < len(symbols):
            if windows >= limits.maximum_windows or monotonic()-start >= limits.maximum_seconds or len(payload.observed_routes.segments)>=limits.maximum_paths:
                reason='resource_limit'
                limit_reason=('window_budget' if windows>=limits.maximum_windows else
                              'path_budget' if len(payload.observed_routes.segments)>=limits.maximum_paths else 'time_budget')
                break
            check()
            symbol=symbols[cursor]
            # One contact is not complete path coverage. Inspect both sides of
            # every device in a stable order, even if it already has a contact.
            if symbol.bounds is not None:
                old_contacts=len(payload.observed_routes.connections);added=0
                try: proposals=local_paths(payload,image,symbol,method)
                except (ValueError,cv2.error,MemoryError):
                    row=passes[method_index]
                    passes[method_index]=row.model_copy(update={'failed_windows':row.failed_windows+1})
                    proposals=[]
                for points,refs,*style in proposals:
                    check()
                    # Finish this bounded window before yielding. A time slice
                    # must never abandon the remainder of a partially accepted
                    # window and advance its resume cursor past missing spans.
                    if len(payload.observed_routes.segments)>=limits.maximum_paths:
                        reason='resource_limit';limit_reason='path_budget';break
                    if not _ends_at_device(points,symbol):continue
                    same_scope=[r for r in payload.observed_routes.segments if set(r.evidence_refs)&set(refs)]
                    if _duplicate(points,same_scope,image,symbols=symbols,line_style=style[0] if style else 'solid'): continue
                    identity=max((int(r.id.split('-')[-1]) for r in payload.observed_routes.segments),default=0)+1
                    points,attachment=_trim_to_network(points,symbol,same_scope,image)
                    if _duplicate(points,same_scope,image,symbols=symbols,line_style=style[0] if style else 'solid'):continue
                    if attachment:
                        q=attachment[-1]
                        if any(s.bounds.x-3<=q.x<=s.bounds.x+s.bounds.width+3 and s.bounds.y-3<=q.y<=s.bounds.y+s.bounds.height+3 for s in symbols):attachment=None
                    route=ObservedRouteSegment(id=f'segment-{identity:04d}',points=points,line_style=style[0] if style else 'solid',evidence_refs=refs,ambiguity='ambiguous')
                    trial=_join_source_trial(payload,route,attachment) if attachment else payload.model_copy(update={
                        'document_state':'partial','observed_routes':payload.observed_routes.model_copy(update={
                        'state':'partial','failure_reason':None,'segments':payload.observed_routes.segments+(route,)})})
                    if trial is None:continue
                    trial=with_device_contact_evidence(trial,image)
                    if not served_symbols(payload).issubset(served_symbols(trial)):continue
                    new=[c for c in trial.observed_routes.connections if c.from_ref==f'segment:{route.id}' and c.ambiguity=='unambiguous']
                    # Two distinct source ports, including the audited device,
                    # not one random leaf or a line near an unconnected glyph.
                    ids={c.to_ref.split(':',1)[1] for c in new if c.evidence_kind}
                    if symbol.id not in ids or (len(ids)<2 and attachment is None): continue
                    payload=FloorPlanInterpretationPayload.model_validate(trial.model_dump());added+=1
                row=passes[method_index]
                passes[method_index]=row.model_copy(update={'windows':row.windows+1,'added_paths':row.added_paths+added,
                    'added_contacts':row.added_contacts+max(0,len(payload.observed_routes.connections)-old_contacts)})
                windows+=1
            cursor+=1
            save();check()
            if reason=='resource_limit': break
        if reason=='resource_limit': break
        method_index+=1;cursor=0;save()
    if method_index==len(METHODS) and target_ids.issubset(served_symbols(payload)) and not external_limit:
        reason='converged';limit_reason=None
    if overflow or external_limit:reason='resource_limit'
    if not symbols or any(not s.bounds or not in_plan(payload,s) for s in devices):
        if reason=='converged':reason='methods_exhausted'
    from app.ai.floor_plan_interpretation.trace_cleanup import deduplicate_traces, with_terminal_continuations
    payload=with_device_contact_evidence(with_terminal_continuations(deduplicate_traces(payload),image),image)
    report=WiringRecoveryReport(version=VERSION,stop_reason=reason,limit_reason=limit_reason,passes=tuple(passes),
        unassessed_devices=max(0,len(devices)-512),
        devices=audit_devices(payload,image,exhausted=reason=='resource_limit',failed=any(p.failed_windows for p in passes)))
    warnings=tuple(w for w in payload.warnings if w.code!='wiring_recovery_status')
    if len(warnings)<256:
        warnings+=(CandidateWarning(code='wiring_recovery_status',severity='info',message=
            f'Targeted source recovery: {reason}; {windows} windows. No usable observed path is not proof that wiring is absent. Generated routes are separate proposals.'),)
    payload=FloorPlanInterpretationPayload.model_validate(payload.model_copy(update={'observed_routes':payload.observed_routes.model_copy(update={
        'recovery':report}),'warnings':warnings}).model_dump())
    save();check()
    # Walls, symbols, scale and original observations are owned by other stages.
    assert payload.walls==base.walls and payload.symbols==base.symbols
    return payload
