"""Source-backed device contacts; no proximity-only circuit completion.

Raw observed polylines stay unchanged. Contact anchors are separate proposals:
the final glyph-obscured lead is inferred geometry, not observed wire pixels.
"""
import math
import re
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload, ObservedRouteConnection, PixelPoint, CandidateWarning,
)

EVIDENCE_VERSION = 'source-device-ports-polyline-vertices-v4'


def with_device_contact_evidence(payload, image_rgb):
    if not isinstance(image_rgb,np.ndarray) or image_rgb.dtype!=np.uint8 or image_rgb.ndim!=3 or image_rgb.shape[2]!=3:
        raise ValueError('Device evidence requires source RGB pixels.')
    height, width = image_rgb.shape[:2]
    if (height, width) != (payload.source_plane.height_pixels, payload.source_plane.width_pixels):
        raise ValueError('Device evidence requires the unchanged source coordinate plane.')
    if (height*width>12_000_000 or len(payload.symbols.items)>512
        or sum(len(r.points)-1 for r in payload.observed_routes.segments)>4096):
        warning=CandidateWarning(code='device_contact_budget',severity='warning',
            message='Source contact evidence exceeded its bounded working budget; connections remain unresolved.')
        return payload.model_copy(update={'warnings':payload.warnings+(warning,)})
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    ink = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,max(31,round(min(width,height)*.09)) | 1,12)
    raw_ink = ink.copy()
    ink = cv2.dilate(ink,np.ones((3,3),np.uint8))
    padding = max(2,min(6,round(min(width,height)*.0015)))
    symbols = [s for s in payload.symbols.items if s.bounds and not re.search(
        r'home.?run|circuit.*notation|raceway conduit',
        s.training_legend.name if s.training_legend else s.observed_label or '',re.I)]

    def support(anchor, box, dashed, route, edge, forward):
        # Approach ink OUTSIDE the glyph, so the symbol itself cannot supply it.
        # Follow the observed polyline, including bends, and stop at its end.
        # A straight extrapolation can cross blank floor or unrelated strokes.
        distance=max(32,min(80,min(box.width,box.height)*2))
        vertices=(route.points[edge+1:] if forward else tuple(reversed(route.points[:edge+1])))
        current=np.array(anchor);parts=[]
        for vertex in vertices:
            target=np.array([vertex.x,vertex.y]);delta=target-current
            length=float(np.linalg.norm(delta))
            if length<=1e-8:continue
            step=min(distance,length)
            parts.append(current+np.linspace(0,step,math.ceil(step)+1)[:,None]*(delta/length))
            distance-=step
            if distance<=1e-8:break
            current=target
        if not parts:return False
        points=np.concatenate(parts)
        xy=np.rint(points).astype(int)
        # Curve tessellation and shared vertices may revisit a raster pixel;
        # repeated samples are not independent approach evidence.
        _,unique_indices=np.unique(xy,axis=0,return_index=True)
        unique_indices.sort();points=points[unique_indices];xy=xy[unique_indices]
        valid=(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
        outside=(points[:,0]<box.x-padding)|(points[:,0]>box.x+box.width+padding)|(points[:,1]<box.y-padding)|(points[:,1]>box.y+box.height+padding)
        xy=xy[valid&outside]
        if len(xy)<12:return False
        samples=ink[xy[:,1],xy[:,0]]>0
        return float(samples.mean()) >= (.35 if dashed else .80)

    def visible_terminal_contact(anchor, inward, length, box):
        # Dash extraction can trim an irregular final stroke. Require visible
        # source ink all the way to the glyph and repeated axial approach ink.
        max_gap=max(8,min(64,round(min(width,height)*.035)))
        if not (box.x-max_gap-padding<=anchor[0]<=box.x+box.width+max_gap+padding
                and box.y-max_gap-padding<=anchor[1]<=box.y+box.height+max_gap+padding):return False
        from app.ai.floor_plan_interpretation.automatic_wiring import (
            _regular_dash_evidence, _dash_direction_evidence,
        )
        distance=min(length,512.,min(width,height)*.5)
        if distance<32:return False
        end=anchor+inward*distance
        xy=np.rint(np.linspace(anchor,end,math.ceil(distance)+1)).astype(int)
        if ((xy<0).any() or (xy[:,0]>=width).any() or (xy[:,1]>=height).any()):return False
        samples=raw_ink[xy[:,1],xy[:,0]]>0
        if not _regular_dash_evidence(samples,max_gap):return False
        if not _dash_direction_evidence(anchor,end,samples,raw_ink):return False
        # Ray/box entry, with no diagonal corner or unrelated nearby port.
        outward=-inward;entry=0.;exit=float('inf')
        for coordinate,direction,low,high in zip(anchor,outward,
                (box.x,box.y),(box.x+box.width,box.y+box.height)):
            if abs(direction)<1e-8:
                if not low<=coordinate<=high:return False
            else:
                limits=sorted(((low-coordinate)/direction,(high-coordinate)/direction))
                entry=max(entry,limits[0]);exit=min(exit,limits[1])
        if not 0<entry<=exit or entry>max_gap+padding:return False
        # A regular earlier dash pattern cannot supply evidence for a blank
        # terminal gap. Such a connection remains unresolved.
        terminal=np.rint(anchor+outward*np.linspace(1,max(1,entry-padding),
            max(1,math.ceil(entry-padding)))[:,None]).astype(int)
        if not ((terminal>=0).all() and (terminal[:,0]<width).all() and (terminal[:,1]<height).all()):return False
        tail_support=float((raw_ink[terminal[:,1],terminal[:,0]]>0).mean())
        return tail_support>=.8

    proposals=[];unresolved_refs=set()
    for route in payload.observed_routes.segments:
        for edge,(first,last) in enumerate(zip(route.points,route.points[1:])):
            a=np.array([first.x,first.y],float);b=np.array([last.x,last.y],float)
            delta=b-a;length=float(np.linalg.norm(delta));axis=delta/length
            for symbol in symbols:
                box=symbol.bounds;center=np.array([symbol.center.x,symbol.center.y])
                along=float((center-a)@axis);projected=a+along*axis
                port=max(3,min(10,min(box.width,box.height)*.30))
                if np.linalg.norm(center-projected)>port:continue
                # The masked-boundary margin, not a nearest-device radius.
                margin=padding+5
                def near_box(p):
                    return box.x-margin<=p[0]<=box.x+box.width+margin and box.y-margin<=p[1]<=box.y+box.height+margin
                kind=None;anchor=None;phase=False
                start_contact = edge==0 and along<=port and (near_box(a) or
                    (route.line_style=='dashed' and visible_terminal_contact(a,axis,length,box)))
                end_contact = edge==len(route.points)-2 and along>=length-port and (near_box(b) or
                    (route.line_style=='dashed' and visible_terminal_contact(b,-axis,length,box)))
                if start_contact and support(a,box,route.line_style=='dashed',route,edge,True):
                    kind='symbol_occlusion' if np.linalg.norm(a-center)>2 else 'boundary_contact';anchor=a
                    phase=not near_box(a)
                elif end_contact and support(b,box,route.line_style=='dashed',route,edge,False):
                    kind='symbol_occlusion' if np.linalg.norm(b-center)>2 else 'boundary_contact';anchor=b
                    phase=not near_box(b)
                elif edge < len(route.points)-2 and abs(along-length) <= port and near_box(b):
                    # An interior vertex of a logical polyline is not a route
                    # endpoint. Check BOTH real approaches around that vertex;
                    # otherwise chaining spans would lose the inline device.
                    approaches=[support(b,box,route.line_style=='dashed',route,edge,forward)
                                for forward in (True,False)]
                    if all(approaches):
                        kind='inline_device';anchor=b
                    elif any(approaches):
                        unresolved_refs.update((f'segment:{route.id}',f'symbol:{symbol.id}'))
                elif port<along<length-port and near_box(projected):
                    # A device on a continuous run needs two independently
                    # supported approaches through its central port band.
                    approaches=[support(projected,box,route.line_style=='dashed',route,edge,forward)
                                for forward in (True,False)]
                    if all(approaches):
                        kind='inline_device';anchor=projected
                    elif any(approaches):
                        unresolved_refs.update((f'segment:{route.id}',f'symbol:{symbol.id}'))
                if kind:
                    proposals.append(dict(route=route,symbol=symbol,edge=edge,anchor=anchor,kind=kind,
                        distance=float(np.linalg.norm(anchor-center)),phase=phase))
    # Overlapping detector classes/ports are unresolved, not nearest-wins.
    connections=[];seen=set()
    for proposal in sorted(proposals,key=lambda p:(p['route'].id,p['edge'],p['distance'],p['symbol'].id)):
        route,symbol=proposal['route'],proposal['symbol']
        key=(route.id,symbol.id)
        if key in seen:continue
        seen.add(key)
        ambiguous=any(other['route'].id==route.id and other['symbol'].id!=symbol.id
            and np.linalg.norm(other['anchor']-proposal['anchor'])<=max(3,min(symbol.bounds.width,symbol.bounds.height)*.4)
            for other in proposals)
        connections.append(ObservedRouteConnection(id=f'connection-{len(connections)+1:04d}',
            from_ref=f'segment:{route.id}',to_ref=f'symbol:{symbol.id}',source_edge_index=proposal['edge'],
            path_anchor=PixelPoint(x=float(proposal['anchor'][0]),y=float(proposal['anchor'][1])),
            device_anchor=symbol.center,evidence_kind=proposal['kind'],evidence_refs=route.evidence_refs,
            ambiguity='ambiguous' if ambiguous else 'unambiguous'))
        if len(connections)>=2048:break
    routes=payload.observed_routes.model_copy(update={'connections':tuple(connections)})
    warnings=tuple(w for w in payload.warnings if w.code not in (
        'ambiguous_device_contacts','dash_phase_device_contact','source_supported_terminal_lead',
        'device_contact_approach_unresolved'))
    if unresolved_refs and len(warnings)<256:
        warnings=warnings+(CandidateWarning(code='device_contact_approach_unresolved',severity='warning',
            entity_refs=tuple(sorted(unresolved_refs))[:32],
            message='A device overlaps an observed path but one approach lacks sufficient source ink within that path. Inspect the unresolved contact before connecting it.'),)
    phase_refs=tuple(sorted({f"segment:{p['route'].id}" for p in proposals if p['phase']}))[:32]
    if phase_refs and len(warnings)<256:
        warnings=warnings+(CandidateWarning(code='source_supported_terminal_lead',severity='info',entity_refs=phase_refs,
            message='Repeated axial source dashes and visible terminal ink support a device attachment; the attachment lead remains separate from observed vertices and human approval.'),)
    if any(c.ambiguity=='ambiguous' for c in connections) and len(warnings)<256:
        warnings=warnings+(CandidateWarning(code='ambiguous_device_contacts',severity='warning',
            message='Overlapping device ports have source contact evidence but no unique association; inspect the device connections.'),)
    return FloorPlanInterpretationPayload.model_validate(payload.model_copy(update={'observed_routes':routes,'warnings':warnings}).model_dump())
