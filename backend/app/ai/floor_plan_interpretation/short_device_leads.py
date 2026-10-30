"""Bounded source-ink evidence for curved outlet links and homerun leaders.

Only thick, continuous ink OUTSIDE known glyphs qualifies. Thin wall banks,
proximity, label strokes and missing spans cannot establish a connection.
Source vertices remain distinct from glyph-obscured attachment proposals.
"""
import math
import re
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import ObservedRouteSegment, ObservedRouteConnection, PixelPoint
from app.ai.floor_plan_interpretation.stroke_centerlines import stroke_paths

VERSION='short-curved-source-device-leads-v1'

def with_short_device_leads(payload,image):
    if image.shape[0]*image.shape[1]>12_000_000 or len(payload.symbols.items)>512:return payload
    def name(s):return s.training_legend.name if s.training_legend else s.observed_label or ''
    def home(s):return bool(re.search(r'home.?run',name(s),re.I))
    symbols=[s for s in payload.symbols.items if s.bounds and (home(s) or
        re.search(r'outlet|receptacle',name(s),re.I) and not re.search(r'data|telephone|voice|computer|split|switched',name(s),re.I))]
    regions=[r for r in payload.regions if r.kind=='plan_region']
    def common_regions(a,b):
        return tuple(f'region:{r.id}' for r in regions if all(r.bounds.x<=s.center.x<=r.bounds.x+r.bounds.width and r.bounds.y<=s.center.y<=r.bounds.y+r.bounds.height for s in (a,b)))
    pairs=[]
    for i,a in enumerate(symbols):
        for b in symbols[:i]:
            distance=math.hypot(a.center.x-b.center.x,a.center.y-b.center.y)
            if not (home(a) and home(b)) and 8<distance<128 and common_regions(a,b):
                pairs.append((distance,a,b))
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY);height,width=gray.shape
    routes=list(payload.observed_routes.segments);connections=list(payload.observed_routes.connections)
    counter=max((int(r.id.split('-')[-1]) for r in routes),default=0)
    def point_distance(p,a,b):
        delta=b-a;size=float(delta@delta);return float(np.linalg.norm(p-(a+max(0,min(1,float((p-a)@delta/size)))*delta))) if size else float(np.linalg.norm(p-a))
    for _,first,last in sorted(pairs,key=lambda p:(p[0],p[1].id,p[2].id))[:64]:
        if len(routes)>=1024 or len(connections)>2046:break
        if any(c.to_ref==f'symbol:{first.id}' and any(d.to_ref==f'symbol:{last.id}' and d.from_ref==c.from_ref for d in connections) for c in connections):continue
        boxes=[s.bounds for s in (first,last)]
        left=max(0,math.floor(min(b.x for b in boxes))-32);top=max(0,math.floor(min(b.y for b in boxes))-32)
        right=min(width,math.ceil(max(b.x+b.width for b in boxes))+32);bottom=min(height,math.ceil(max(b.y+b.height for b in boxes))+32)
        raw=(gray[top:bottom,left:right]<180).astype(np.uint8)
        mask=(cv2.distanceTransform(raw,cv2.DIST_L2,3)>=1.8).astype(np.uint8)*255
        for symbol in payload.symbols.items:
            b=symbol.bounds
            if b is None:continue
            x0,y0=max(0,math.floor(b.x)-left),max(0,math.floor(b.y)-top)
            x1,y1=min(right-left,math.ceil(b.x+b.width)-left+1),min(bottom-top,math.ceil(b.y+b.height)-top+1)
            if x0<x1 and y0<y1:mask[y0:y1,x0:x1]=0
        def touches(point,symbol):
            b=symbol.bounds;q=np.array([np.clip(point[0],b.x,b.x+b.width),np.clip(point[1],b.y,b.y+b.height)])
            if np.linalg.norm(point-q)>5:return False
            bridge=np.rint(np.linspace(point,q,12)).astype(int)-[left,top]
            if (bridge<0).any() or (bridge[:,0]>=raw.shape[1]).any() or (bridge[:,1]>=raw.shape[0]).any():return False
            return (raw[bridge[:,1],bridge[:,0]]>0).mean()>=.95
        options=[]
        for path in stroke_paths(mask,minimum_length=5,maximum_paths=64):
            points=np.asarray(path,dtype=float)+[left,top]
            if touches(points[0],last) and touches(points[-1],first):points=points[::-1]
            if not (touches(points[0],first) and touches(points[-1],last)):continue
            length=sum(float(np.linalg.norm(b-a)) for a,b in zip(points,points[1:]));direct=float(np.linalg.norm(points[-1]-points[0]))
            if not (8<=length<=160 and direct*1.08<length and len(points)<=512):continue
            # Another recognised glyph on this chain makes the association ambiguous.
            if any(s.id not in (first.id,last.id) and s.bounds and any(touches(p,s) for p in (points[0],points[-1])) for s in symbols):continue
            if all(any(point_distance(p,np.array([a.x,a.y]),np.array([b.x,b.y]))<=2 for r in routes for a,b in zip(r.points,r.points[1:])) for p in points):continue
            options.append((length,points))
        if not options:continue
        # Multiple disjoint ink paths are not resolved by picking a convenient one.
        if len(options)>1:continue
        _,points=options[0];counter+=1
        refs=common_regions(first,last)
        styles={r.line_style for c in connections if c.to_ref in (f'symbol:{first.id}',f'symbol:{last.id}') for r in routes if c.from_ref==f'segment:{r.id}' and r.line_style!='unknown'}
        route=ObservedRouteSegment(id=f'segment-{counter:04d}',line_style=next(iter(styles)) if len(styles)==1 else 'solid',
            points=tuple(PixelPoint(x=float(p[0]),y=float(p[1])) for p in points),evidence_refs=refs,ambiguity='clear')
        routes.append(route)
        for symbol,index in ((first,0),(last,len(route.points)-1)):
            connections.append(ObservedRouteConnection(id=f'connection-{len(connections)+1:04d}',from_ref=f'segment:{route.id}',to_ref=f'symbol:{symbol.id}',
                source_edge_index=0 if index==0 else index-1,path_anchor=route.points[index],device_anchor=symbol.center,
                route_node_id=f'source-node.{symbol.id}',evidence_kind=None if home(symbol) else 'boundary_contact',evidence_refs=refs,ambiguity='unambiguous'))
    return payload.model_copy(update={'observed_routes':payload.observed_routes.model_copy(update={'segments':tuple(routes),'connections':tuple(connections)})})
