"""Join only independently traced, continuously inked dashed-wire corners.

No proximity-only crossing joins. A wall-bank tail can be cut only when its
original pixels lack axial wire support and a supported perpendicular arm ends
at that same source corner. Never applied to saved review geometry.
"""
import math
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import PixelPoint,ObservedJunction,ObservedJunctionMember

def with_source_corners(payload,image):
    routes=payload.observed_routes
    if len(routes.segments)>128 or image.shape[0]*image.shape[1]>12_000_000:return payload
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY);raw=(gray<180).astype(np.uint8);band=cv2.dilate(raw,np.ones((3,3),np.uint8))
    items={r.id:r for r in routes.segments};junctions=list(routes.junctions);used=set()
    protected={(c.from_ref.split(':',1)[1],0 if c.source_edge_index==0 and c.path_anchor==items[c.from_ref.split(':',1)[1]].points[0] else len(items[c.from_ref.split(':',1)[1]].points)-1)
        for c in routes.connections if c.evidence_kind and c.path_anchor and c.from_ref.startswith('segment:') and c.from_ref.split(':',1)[1] in items}
    protected|={(m.segment_id,m.point_index) for j in junctions for m in j.members}
    def fraction(a,b,mask):
        xy=np.rint(np.linspace(a,b,max(3,math.ceil(float(np.linalg.norm(b-a)))+1))).astype(int)
        if (xy<0).any() or (xy[:,0]>=gray.shape[1]).any() or (xy[:,1]>=gray.shape[0]).any():return 0
        return float(mask[xy[:,1],xy[:,0]].mean())
    def continuous_corner(a,b):
        # Raster/Hough axes can sit just outside a rounded six-pixel stroke.
        # Require one actual thick-ink component; dilation never closes a gap.
        x0,y0=np.maximum(0,np.floor(np.minimum(a,b)-5)).astype(int)
        x1,y1=np.minimum([gray.shape[1],gray.shape[0]],np.ceil(np.maximum(a,b)+6)).astype(int)
        local=raw[y0:y1,x0:x1];core=(cv2.distanceTransform(local,cv2.DIST_L2,3)>=1.4).astype(np.uint8)
        _,labels=cv2.connectedComponents(core,8);yy,xx=np.indices(labels.shape);values=[]
        for point in (a,b):
            near=(xx+x0-point[0])**2+(yy+y0-point[1])**2<=9
            values.append(set(int(v) for v in labels[near] if v))
        return len(values[0]&values[1])==1
    for first in routes.segments:
        if first.line_style!='dashed' or len(items[first.id].points)!=2:continue
        # Preserve the incoming source axis and add only the tiny visible bend.
        endpoint=1
        if (first.id,endpoint) in protected or (first.id,endpoint) in used:continue
        a,b=np.array([[p.x,p.y] for p in items[first.id].points]);axis=b-a;size=float(np.linalg.norm(axis));axis/=size
        for second in routes.segments:
            if first.id==second.id or second.line_style!='dashed' or len(items[second.id].points)!=2 or not set(first.evidence_refs)&set(second.evidence_refs):continue
            c,d=np.array([[p.x,p.y] for p in items[second.id].points]);other=d-c
            if abs(float(axis@other))/np.linalg.norm(other)>.1:continue
            found=None
            for index,p in ((0,c),(1,d)):
                if (second.id,index) in protected or (second.id,index) in used:continue
                t=float((p-a)@axis);q=a+np.clip(t,0,size)*axis;distance=float(np.linalg.norm(p-b));tail=size-t
                clip=False
                if distance<=5:anchor=p
                elif 1<tail<=32 and np.linalg.norm(p-q)<=3:
                    wall_hit=any(abs(float(axis@np.array([w.end.x-w.start.x,w.end.y-w.start.y])))/max(1,math.hypot(w.end.x-w.start.x,w.end.y-w.start.y))<.5 and min(math.hypot(b[0]-w.start.x,b[1]-w.start.y),math.hypot(b[0]-w.end.x,b[1]-w.end.y))<32 for w in payload.walls.items)
                    if not wall_hit or fraction(q,b,raw)>.45 or fraction(q-axis*min(18,t),q,raw)<.8:continue
                    anchor=q;clip=True
                else:continue
                if fraction(p,anchor,raw)<.8 or fraction(p,anchor,band)<.99:continue
                if not clip and not continuous_corner(b,anchor):continue
                found=(index,p,anchor,clip);break
            if found is None:continue
            index,p,anchor,clip=found;point=PixelPoint(x=float(anchor[0]),y=float(anchor[1]));current=items[first.id]
            points=(*current.points[:-1],point) if clip or np.linalg.norm(anchor-b)<.01 else (*current.points,point)
            if len(points)>2 and points[-1]==points[-2]:points=points[:-1]
            target=list(items[second.id].points);target[index]=point
            if target[0]==target[1]:continue
            items[first.id]=current.model_copy(update={'points':points});items[second.id]=items[second.id].model_copy(update={'points':tuple(target)})
            number=max((int(j.id.split('-')[-1]) for j in junctions),default=0)+1
            junctions.append(ObservedJunction(id=f'junction-{number:04d}',members=(ObservedJunctionMember(segment_id=first.id,point_index=len(points)-1),ObservedJunctionMember(segment_id=second.id,point_index=index)),evidence_kind='source_corner_contact',evidence_refs=first.evidence_refs,ambiguity='clear'))
            used|={(first.id,len(points)-1),(second.id,index)};break
    return payload.model_copy(update={'observed_routes':routes.model_copy(update={'segments':tuple(items[r.id] for r in routes.segments),'junctions':tuple(junctions)})})
