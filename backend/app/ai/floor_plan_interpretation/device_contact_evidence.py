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

EVIDENCE_VERSION = 'source-device-ports-v1'


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
    ink = cv2.dilate(ink,np.ones((3,3),np.uint8))
    padding = max(2,min(6,round(min(width,height)*.0015)))
    symbols = [s for s in payload.symbols.items if s.bounds and not re.search(
        r'home.?run|circuit.*notation|raceway conduit',
        s.training_legend.name if s.training_legend else s.observed_label or '',re.I)]

    def support(anchor, direction, box, dashed):
        # Approach ink OUTSIDE the glyph, so the symbol itself cannot supply it.
        distance=max(32,min(80,min(box.width,box.height)*2))
        points=np.array(anchor)+np.linspace(0,distance,math.ceil(distance)+1)[:,None]*direction
        xy=np.rint(points).astype(int)
        valid=(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
        outside=(points[:,0]<box.x-padding)|(points[:,0]>box.x+box.width+padding)|(points[:,1]<box.y-padding)|(points[:,1]>box.y+box.height+padding)
        xy=xy[valid&outside]
        if len(xy)<12:return False
        samples=ink[xy[:,1],xy[:,0]]>0
        return float(samples.mean()) >= (.35 if dashed else .80)

    proposals=[]
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
                kind=None;anchor=None
                if edge==0 and along<=port and near_box(a) and support(a,axis,box,route.line_style=='dashed'):
                    kind='symbol_occlusion' if np.linalg.norm(a-center)>2 else 'boundary_contact';anchor=a
                elif edge==len(route.points)-2 and along>=length-port and near_box(b) and support(b,-axis,box,route.line_style=='dashed'):
                    kind='symbol_occlusion' if np.linalg.norm(b-center)>2 else 'boundary_contact';anchor=b
                elif port<along<length-port and near_box(projected):
                    # A device on a continuous run needs two independently
                    # supported approaches through its central port band.
                    if support(projected,axis,box,route.line_style=='dashed') and support(projected,-axis,box,route.line_style=='dashed'):
                        kind='inline_device';anchor=projected
                if kind:
                    proposals.append(dict(route=route,symbol=symbol,edge=edge,anchor=anchor,kind=kind,
                        distance=float(np.linalg.norm(anchor-center))))
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
    warnings=payload.warnings
    if any(c.ambiguity=='ambiguous' for c in connections) and len(warnings)<256:
        warnings=warnings+(CandidateWarning(code='ambiguous_device_contacts',severity='warning',
            message='Overlapping device ports have source contact evidence but no unique association; inspect the device connections.'),)
    return FloorPlanInterpretationPayload.model_validate(payload.model_copy(update={'observed_routes':routes,'warnings':warnings}).model_dump())
