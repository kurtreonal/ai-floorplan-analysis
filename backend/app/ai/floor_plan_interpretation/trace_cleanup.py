"""Source-only proposal cleanup; never called on saved designer geometry."""
import math
import re
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import PixelPoint, CandidateWarning
from app.ai.floor_plan_interpretation.stroke_centerlines import stroke_paths

VERSION = 'source-terminal-curves-exact-overlap-v1'


def extend_existing_dashes(payload,image):
    """Recover omitted ends of an already supported dashed source run.

    The ordinary detector remains unchanged. Require the complete proposed
    extension to pass the existing axial/contrast/parallel-boundary gates.
    """
    from app.ai.floor_plan_interpretation.automatic_wiring import (
        _dash_span,_dash_direction_evidence,_source_dash_contrast,
        _parallel_dash_boundaries,_trim_crossing_ends,
    )
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY);h,w=gray.shape
    if h*w>12_000_000:return payload
    block=max(31,round(min(w,h)*.09))|1
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,block,12)
    support=cv2.dilate(ink,np.ones((3,3),np.uint8));result=[]
    gap=max(8,min(64,round(min(w,h)*.035)))
    for route in payload.observed_routes.segments:
        if route.line_style!='dashed' or len(route.points)!=2:result.append(route);continue
        a,b=np.array([[p.x,p.y] for p in route.points],dtype=float)
        contacts=[c.path_anchor for c in payload.observed_routes.connections
                  if c.from_ref==f'segment:{route.id}' and c.path_anchor and c.ambiguity=='unambiguous']
        bound_start=any(math.hypot(p.x-a[0],p.y-a[1])<.5 for p in contacts)
        bound_end=any(math.hypot(p.x-b[0],p.y-b[1])<.5 for p in contacts)
        if bound_start and bound_end:result.append(route);continue
        axis=b-a;length=float(np.linalg.norm(axis));axis/=length
        if min(abs(axis[0]),abs(axis[1]))>.01:result.append(route);continue
        # Do not keep an isolated wall-bank hit as a dangling wire tail.
        xy=np.rint(np.linspace(a,b,math.ceil(length)+1)).astype(int)
        xy[:,0]=np.clip(xy[:,0],0,w-1);xy[:,1]=np.clip(xy[:,1],0,h-1)
        clipped_a,clipped_b=_trim_crossing_ends(a,b,support[xy[:,1],xy[:,0]]>0,ink,payload.walls.items)
        c=a if bound_start else np.asarray(clipped_a,dtype=float)
        d=b if bound_end else np.asarray(clipped_b,dtype=float)
        if np.linalg.norm(d-c)>=length*.5 and max(np.linalg.norm(c-a),np.linalg.norm(d-b))<=96:
            a,b=c,d;length=float(np.linalg.norm(b-a));axis=(b-a)/length
            route=route.model_copy(update={'points':(PixelPoint(x=float(a[0]),y=float(a[1])),PixelPoint(x=float(b[0]),y=float(b[1])))})
        regions=[r.bounds for r in payload.regions if r.kind=='plan_region' and f'region:{r.id}' in route.evidence_refs]
        low,high=0.,length
        # Bound each endpoint search independently in the selected source view.
        for _ in range(256):
            first=a+axis*(low-1);last=a+axis*(high+1)
            if not bound_start and low>-256 and any(r.x<=first[0]<=r.x+r.width and r.y<=first[1]<=r.y+r.height for r in regions):low-=1
            if not bound_end and high<length+256 and any(r.x<=last[0]<=r.x+r.width and r.y<=last[1]<=r.y+r.height for r in regions):high+=1
        xy=np.rint(a+np.linspace(low,high,math.ceil(high-low)+1)[:,None]*axis).astype(int)
        if (xy<0).any() or (xy[:,0]>=w).any() or (xy[:,1]>=h).any():result.append(route);continue
        samples=support[xy[:,1],xy[:,0]]>0;span=_dash_span(samples,gap,allow_crossing_islands=True)
        if span:
            lo,hi=span;c,d=xy[lo],xy[hi-1];selected=samples[lo:hi]
            c,d=_trim_crossing_ends(c,d,selected,ink,payload.walls.items)
            if bound_start:c=a
            if bound_end:d=b
            start=float((np.asarray(c)-a)@axis);end=float((np.asarray(d)-a)@axis)
            if (start<=2 and end>=length-2 and (start<=-12 or end>=length+12)
                    and _dash_direction_evidence(xy[lo],xy[hi-1],selected,ink)
                    and _source_dash_contrast(xy[lo],xy[hi-1],selected,gray)
                    and not _parallel_dash_boundaries(xy[lo],xy[hi-1],selected,ink)):
                route=route.model_copy(update={'points':(PixelPoint(x=float(c[0]),y=float(c[1])),PixelPoint(x=float(d[0]),y=float(d[1])))})
        result.append(route)
    return payload.model_copy(update={'observed_routes':payload.observed_routes.model_copy(update={'segments':tuple(result)})})


def deduplicate_traces(payload):
    routes=payload.observed_routes
    removed={};kept=[]
    def length(route):
        return sum(math.hypot(b.x-a.x,b.y-a.y) for a,b in zip(route.points,route.points[1:]))
    def covered(a,b,target):
        start=np.array([a.x,a.y],dtype=float);axis=np.array([b.x-a.x,b.y-a.y],dtype=float);size=float(np.linalg.norm(axis));axis/=size
        normal=np.array([-axis[1],axis[0]]);intervals=[]
        for c,d in zip(target.points,target.points[1:]):
            ends=np.array([[c.x,c.y],[d.x,d.y]])-start
            if max(abs(ends@normal))>.25:continue
            lo,hi=sorted(ends@axis);intervals.append((float(lo),float(hi)))
        end=0.
        for lo,hi in sorted(intervals):
            if hi<end:continue
            if lo>end+.25:return False
            end=max(end,hi)
            if end>=size-.25:return True
        return False
    for route in sorted(routes.segments,key=lambda r:(-length(r),r.id)):
        vertices=[route.points[m.point_index] for j in routes.junctions for m in j.members if m.segment_id==route.id]
        target=next((other for other in kept if other.line_style==route.line_style
            and set(other.evidence_refs)&set(route.evidence_refs)
            and all(covered(a,b,other) for a,b in zip(route.points,route.points[1:]))
            and all(any(p==q for q in other.points) for p in vertices)),None)
        if target:removed[route.id]=target
        else:kept.append(route)
    if not removed:return payload
    refs={f'segment:{identity}' for identity in removed}
    warnings=tuple(w for w in payload.warnings if not refs.intersection(w.entity_refs))
    if len(warnings)<256:
        warnings+=(CandidateWarning(code='duplicate_source_trace',severity='info',
            message='Contained observations of the same source stroke omitted: '+', '.join(sorted(removed))+'. Separate branches and source junctions are preserved.'),)
    junctions=[]
    originals={r.id:r for r in routes.segments}
    for junction in routes.junctions:
        members=[]
        for member in junction.members:
            if member.segment_id in removed:
                target=removed[member.segment_id];p=originals[member.segment_id].points[member.point_index]
                member=member.model_copy(update={'segment_id':target.id,'point_index':target.points.index(p)})
            if member not in members:members.append(member)
        if len(members)>1:junctions.append(junction.model_copy(update={'members':tuple(members)}))
    return payload.model_copy(update={'warnings':warnings,'observed_routes':routes.model_copy(update={
        'segments':tuple(r for r in routes.segments if r.id not in removed),
        'connections':tuple(c for c in routes.connections if c.from_ref not in refs and c.to_ref not in refs),
        'junctions':tuple(junctions)})})


def with_terminal_continuations(payload,image):
    """Retain small visible bends between a trace end and a device boundary.

    Trace unchanged ink outside glyphs. No gap closing, straight-line device
    guesses, wall shortcuts or circuit assignment. Multiple devices stay open.
    """
    if image.shape[0]*image.shape[1]>12_000_000:return payload
    symbols=[s for s in payload.symbols.items if s.bounds and not re.search(
        r'home.?run|circuit.*notation|raceway|conduit',
        s.training_legend.name if s.training_legend else s.observed_label or '',re.I)]
    plan_refs={f'region:{r.id}' for r in payload.regions if r.kind=='plan_region'}
    protected={m.segment_id for j in payload.observed_routes.junctions for m in j.members}
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY);height,width=gray.shape
    band=cv2.dilate((gray<180).astype(np.uint8),np.ones((3,3),np.uint8))
    replacements={};windows=0
    for route in payload.observed_routes.segments:
        if route.id in protected:continue
        points=list(route.points)
        for index in (0,len(points)-1):
            if windows>=128:break
            point=points[index];neighbor=points[1 if index==0 else index-1]
            if not (0<=point.x<width and 0<=point.y<height):continue
            if any(c.from_ref==f'segment:{route.id}' and c.path_anchor and
                   math.hypot(c.path_anchor.x-point.x,c.path_anchor.y-point.y)<.5
                   for c in payload.observed_routes.connections):continue
            choices=[]
            for symbol in symbols:
                box=symbol.bounds;radius=min(96,max(24,max(box.width,box.height)*.8))
                if math.hypot(point.x-symbol.center.x,point.y-symbol.center.y)>radius:continue
                route_scopes=set(route.evidence_refs)&plan_refs
                symbol_scopes=set(symbol.evidence_refs)&plan_refs
                if route_scopes and symbol_scopes and not route_scopes&symbol_scopes:continue
                if not any(r.kind=='plan_region' and f'region:{r.id}' in route_scopes
                    and r.bounds.x<=symbol.center.x<=r.bounds.x+r.bounds.width
                    and r.bounds.y<=symbol.center.y<=r.bounds.y+r.bounds.height for r in payload.regions):continue
                if windows>=128:break
                windows+=1
                x=max(0,math.floor(min(point.x,box.x))-7);y=max(0,math.floor(min(point.y,box.y))-7)
                right=min(width,math.ceil(max(point.x,box.x+box.width))+8);bottom=min(height,math.ceil(max(point.y,box.y+box.height))+8)
                mask=(gray[y:bottom,x:right]<180).astype(np.uint8)*255
                for device in symbols:
                    b=device.bounds
                    left,top=max(0,math.floor(b.x)-x),max(0,math.floor(b.y)-y)
                    r,t=min(right-x,math.ceil(b.x+b.width)-x+1),min(bottom-y,math.ceil(b.y+b.height)-y+1)
                    if left<r and top<t:mask[top:t,left:r]=0
                for wall in payload.walls.items:
                    cv2.line(mask,(round(wall.start.x)-x,round(wall.start.y)-y),
                        (round(wall.end.x)-x,round(wall.end.y)-y),0,max(2,round(wall.estimated_thickness_pixels or 2)))
                p=np.array([point.x,point.y]);incoming=p-np.array([neighbor.x,neighbor.y])
                for chain in stroke_paths(mask,minimum_length=4,maximum_paths=64):
                    chain=np.asarray(chain)+[x,y]
                    for ordered in (chain,chain[::-1]):
                        end=ordered[-1]
                        if not (box.x-6<=end[0]<=box.x+box.width+6 and box.y-6<=end[1]<=box.y+box.height+6):continue
                        # Thinning retracts a thick stroke's cut end. Restore
                        # only its short, continuously inked boundary stub.
                        yy,xx=np.nonzero(mask)
                        pixels=np.column_stack((xx+x,yy+y))
                        box_distance=np.hypot(np.maximum(0,np.maximum(box.x-pixels[:,0],pixels[:,0]-box.x-box.width)),
                            np.maximum(0,np.maximum(box.y-pixels[:,1],pixels[:,1]-box.y-box.height)))
                        candidates=pixels[(box_distance<=2)&(np.linalg.norm(pixels-end,axis=1)<=6)]
                        for target in sorted(candidates,key=lambda v:float(np.linalg.norm(v-end))):
                            if float((end-ordered[-2])@(target-end))<=0:continue
                            bridge=np.rint(np.linspace(end,target,8)).astype(int)-[x,y]
                            if (mask[bridge[:,1],bridge[:,0]]>0).mean()<.95:continue
                            ordered=np.vstack((ordered,target));end=target;break
                        for edge,(a,b) in enumerate(zip(ordered,ordered[1:])):
                            delta=b-a;size=float(delta@delta)
                            if not size:continue
                            t=max(0,min(1,float((p-a)@delta/size)));q=a+t*delta
                            if np.linalg.norm(p-q)>3 or float(incoming@(end-p))<=0:continue
                            bridge=np.rint(np.linspace(p,q,5)).astype(int)
                            if (band[bridge[:,1],bridge[:,0]]>0).mean()<.8:continue
                            # Correct the at-most-three-pixel raster-axis
                            # offset instead of drawing an out-and-back spur.
                            lead=[q,*ordered[edge+1:]]
                            lead=[v for i,v in enumerate(lead) if not i or np.linalg.norm(v-lead[i-1])>1e-6]
                            distance=sum(float(np.linalg.norm(b-a)) for a,b in zip(lead,lead[1:]))
                            if 3<=distance<=radius and len(lead)+len(points)<=512:
                                choices.append((symbol.id,distance,lead))
            if len({c[0] for c in choices})!=1:continue
            _,_,lead=min(choices,key=lambda c:c[1])
            vertices=[PixelPoint(x=float(v[0]),y=float(v[1])) for v in lead]
            if index==0:points=list(reversed(vertices))+points[1:]
            else:points=points[:-1]+vertices
            replacements[route.id]=route.model_copy(update={'points':tuple(points)})
            # Prepending changes the last endpoint's index.
            if index==0 and len(points)!=len(route.points):break
    if not replacements:return payload
    routes=payload.observed_routes.model_copy(update={
        'segments':tuple(replacements.get(r.id,r) for r in payload.observed_routes.segments),
        'connections':tuple(c for c in payload.observed_routes.connections if c.evidence_kind is None)})
    return payload.model_copy(update={'observed_routes':routes})
