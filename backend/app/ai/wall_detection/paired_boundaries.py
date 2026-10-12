"""Recover outlined partitions anchored to qualified walls, not arbitrary edges.

Two sustained narrow ink banks with a clear interior are independent wall
evidence. Their spacing, support and structural contact are required together;
single grid/wiring strokes and free-floating fixture rectangles do not qualify.
"""
import math
import cv2
import numpy as np

CONFIGURATION = dict(version='anchored-paired-boundaries-v1', maximum_lines=768,
                     maximum_pairs=16384, minimum_support=.90, maximum_white_run=3)


def recover_paired_boundaries(rgb, seeds, scope, symbols=()):
    if not seeds or len(seeds)>300:
        return []
    h,w=scope.shape
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                             cv2.THRESH_BINARY_INV,max(31,round(min(h,w)*.09))|1,12)
    ink[scope==0]=0
    # Only fixture interiors are exclusions. Blanket symbol bounding boxes can
    # erase real walls near switches/homerun annotations.
    import re
    for symbol in symbols:
        b=symbol.bounds
        training=getattr(symbol,'training_legend',None)
        name=training.name if training else symbol.observed_label or ''
        if b and re.search(r'troffer|fluorescent|downlight|ceiling light',name,re.I):
            ink[max(0,math.floor(b.y)):min(h,math.ceil(b.y+b.height)),
                max(0,math.floor(b.x)):min(w,math.ceil(b.x+b.width))]=0
    widths=[s[4] for s in seeds if math.dist(s[:2],s[2:4])>=s[4]*8]
    if not widths:return []
    typical=float(np.median(widths))
    if not math.isfinite(typical):return []
    minimum=max(4,typical*.45);maximum=min(typical*1.5,min(w,h)*.025)
    min_span=max(24,typical*8)
    lines=cv2.HoughLinesP(ink,1,math.pi/360,max(12,round(min_span*.4)),
                         minLineLength=round(min_span),maxLineGap=2)
    if lines is None:return []
    rows=sorted(tuple(map(int,r)) for r in lines[:,0])
    if len(rows)>CONFIGURATION['maximum_lines']:return []
    recovered=[];pairs=0
    def anchored(point,axis):
        for s in seeds:
            a,b=np.array(s[:2],float),np.array(s[2:4],float);v=b-a;length=np.linalg.norm(v)
            if length<s[4]*6:continue
            direction=v/length
            if abs(float(axis@direction))>.9:continue
            t=float((point-a)@direction)
            if -s[4]/2<=t<=length+s[4]/2 and np.linalg.norm(point-(a+direction*t))<=s[4]/2+2:
                return True
        return False
    for i,row in enumerate(rows):
        a,b=np.array(row[:2],float),np.array(row[2:4],float);length=np.linalg.norm(b-a)
        if length<min_span:continue
        axis=(b-a)/length;normal=np.array([-axis[1],axis[0]])
        for other in rows[i+1:]:
            c,d=np.array(other[:2],float),np.array(other[2:4],float);v=d-c;span=np.linalg.norm(v)
            if not span or abs(float(v/span@axis))<math.cos(math.radians(1)):continue
            offsets=np.array([(p-a)@normal for p in (c,d)])
            spacing=float(np.mean(offsets))
            if not minimum<=abs(spacing)<=maximum or np.ptp(offsets)>1.5:continue
            lo=max(0,min(float((p-a)@axis) for p in (c,d)))
            hi=min(length,max(float((p-a)@axis) for p in (c,d)))
            if hi-lo<max(min_span,abs(spacing)*8):continue
            pairs+=1
            if pairs>CONFIGURATION['maximum_pairs']:return []
            start=a+axis*lo+normal*spacing/2;end=a+axis*hi+normal*spacing/2
            points=np.linspace(start,end,max(2,math.ceil(hi-lo)+1))
            banks=[]
            for side in (-1,1):
                xy=np.rint(points+normal*side*spacing/2).astype(int)
                probes=np.stack([xy+np.rint(normal*j).astype(int) for j in (-1,0,1)])
                probes[...,0]=np.clip(probes[...,0],0,w-1);probes[...,1]=np.clip(probes[...,1],0,h-1)
                banks.append((ink[probes[...,1],probes[...,0]]>0).any(axis=0))
            supported=banks[0]&banks[1]
            if supported.mean()<CONFIGURATION['minimum_support']:continue
            # A paired opening must never be filled by averaging the endpoints.
            run=longest=0
            for hit in supported:
                run=0 if hit else run+1;longest=max(longest,run)
            if longest>CONFIGURATION['maximum_white_run']:continue
            inset=max(2,abs(spacing)*.15)
            offsets=np.arange(-abs(spacing)/2+inset,abs(spacing)/2-inset+1)
            cores=np.rint(np.array([points+normal*offset for offset in offsets])).astype(int)
            # A window/frame has additional sustained longitudinal banks inside
            # the strip. It is not a blank outlined partition or a wall fill.
            if (ink[cores[...,1],cores[...,0]]>0).mean(axis=1).max()>.20:continue
            # Hough often ends at a grid crossing or tile-sized fragment. Follow
            # both observed banks, stopping at the first real white opening.
            for index,origin in enumerate((start.copy(),end.copy())):
                sign=-1 if index==0 else 1
                last=origin;gap=0
                for step in range(1,max(h,w)):
                    point=origin+axis*sign*step
                    probes=np.rint(np.array([point+normal*(side*spacing/2+j)
                        for side in (-1,1) for j in (-1,0,1)])).astype(int)
                    if (probes<0).any() or (probes[:,0]>=w).any() or (probes[:,1]>=h).any():break
                    hit=(ink[probes[:,1],probes[:,0]]>0).reshape(2,3).any(axis=1).all()
                    gap=0 if hit else gap+1
                    if gap>CONFIGURATION['maximum_white_run']:break
                    if hit:last=point
                if index==0:start=last
                else:end=last
            if anchored(start,axis) or anchored(end,axis):
                recovered.append((*map(float,start),*map(float,end),abs(spacing)))
    # No near-line averaging: keep the longest duplicate observation at its
    # observed centre and require overlapping intervals on that same axis.
    kept=[]
    for row in sorted(recovered,key=lambda r:(-math.dist(r[:2],r[2:4]),r)):
        a,b=np.array(row[:2]),np.array(row[2:4]);v=b-a;length=np.linalg.norm(v);axis=v/length
        duplicate=False
        for prior in [*seeds,*kept]:
            c,d=np.array(prior[:2]),np.array(prior[2:4]);u=d-c;span=np.linalg.norm(u)
            if abs(float(axis@u/span))<.999:continue
            t=sorted(float((p-c)@u/span) for p in (a,b))
            distance=max(abs(float(u[0]*(p-c)[1]-u[1]*(p-c)[0]))/span for p in (a,b))
            overlap=max(0,min(span,t[1])-max(0,t[0]))
            if distance<=max(1,min(prior[4],row[4])*.25) and overlap>=min(length,span)*.70:
                duplicate=True;break
        if not duplicate:kept.append(row)
    return sorted(kept)
