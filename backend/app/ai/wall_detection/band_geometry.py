"""Fit already-qualified filled bands, not arbitrary image lines.

Cross-sections provide independent width/centre evidence. Corner blobs cannot
set the global wall width or create diagonal branches through a filled junction.
"""
import math
import cv2
import numpy as np

VERSION = 'qualified-band-centres-v2'


def refine_filled_bands(rows, mask, *, preserve_width=False):
    if len(rows)>512: return list(rows)
    height,width=mask.shape
    fitted=[]
    for row in rows:
        a,b=np.array(row[:2],float),np.array(row[2:4],float)
        span=float(np.linalg.norm(b-a))
        if not span:continue
        axis=(b-a)/span;normal=np.array([-axis[1],axis[0]])
        reach=max(3,math.ceil(row[4]*2))
        samples=[]
        for t in np.linspace(.05,.95,max(9,min(128,math.ceil(span/3)))):
            center=a+(b-a)*t
            xy=np.rint(center+np.arange(-reach,reach+1)[:,None]*normal).astype(int)
            valid=(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
            hits=np.zeros(len(xy),bool);hits[valid]=mask[xy[valid,1],xy[valid,0]]>0
            # A white channel separates nearby bands; do not cross it.
            if not hits[reach]:continue
            lo=hi=reach
            while lo>0 and hits[lo-1]:lo-=1
            while hi<len(hits)-1 and hits[hi+1]:hi+=1
            if lo==0 or hi==len(hits)-1:continue # unbounded junction/patch
            samples.append((center+normal*((lo+hi)/2-reach),hi-lo+1))
        if len(samples)<5:
            fitted.append(tuple(row));continue
        widths=np.array([s[1] for s in samples]);typical=float(np.percentile(widths,35))
        points=np.array([p for p,w in samples if .65*typical<=w<=1.5*typical])
        if len(points)<5:
            fitted.append(tuple(row));continue
        vx,vy,x,y=map(float,cv2.fitLine(points.astype(np.float32),cv2.DIST_L1,0,.01,.01).flatten())
        direction=np.array([vx,vy]);origin=np.array([x,y])
        if abs(float(direction@axis))<math.cos(math.radians(5)):
            fitted.append(tuple(row));continue
        endpoints=[origin+direction*float((p-origin)@direction) for p in (a,b)]
        normal=np.array([-direction[1],direction[0]])
        reach=max(3,math.ceil(typical*2))
        def band_width(point):
            xy=np.rint(point+np.arange(-reach,reach+1)[:,None]*normal).astype(int)
            valid=(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=0)&(xy[:,1]<height)
            hits=np.zeros(len(xy),bool);hits[valid]=mask[xy[valid,1],xy[valid,0]]>0
            if not hits[reach]:return 0
            lo=hi=reach
            while lo>0 and hits[lo-1]:lo-=1
            while hi<len(hits)-1 and hits[hi+1]:hi+=1
            return hi-lo+1
        for i in (0,1):
            toward=endpoints[1-i]-endpoints[i];toward/=np.linalg.norm(toward)
            if band_width(endpoints[i])>=typical*.65:continue
            # Trim thin dimension-stroke tails within this qualified band.
            for step in range(1,math.ceil(min(span*.25,typical*3))+1):
                probe=endpoints[i]+toward*step
                if band_width(probe)>=typical*.65:
                    endpoints[i]=probe;break
        # Never snap to global axes: rotations/skew and genuine angles survive.
        fitted.append((*map(int,np.rint(endpoints[0])),*map(int,np.rint(endpoints[1])),
                       row[4] if preserve_width else round(typical,2)))
    result=[]
    for row in fitted:
        a,b=np.array(row[:2],float),np.array(row[2:4],float);span=np.linalg.norm(b-a)
        axis=(b-a)/span
        # Reject only a compact oblique hypothesis inside an independently
        # observed multi-direction junction. Short isolated/angled walls survive.
        anchors=[]
        if span<=row[4]*4:
            for other in fitted:
                c,d=np.array(other[:2],float),np.array(other[2:4],float);length=np.linalg.norm(d-c)
                if length<max(span*2,other[4]*6):continue
                direction=(d-c)/length
                cosine=abs(float(direction@axis))
                if cosine>.94:continue
                # The blob may widen the junction, but cannot extrapolate an anchor.
                t=np.clip(((a+b)/2-c)@direction,0,length)
                if np.linalg.norm((a+b)/2-(c+direction*t))<=row[4]+other[4]:
                    anchors.append(direction)
            if any(abs(float(u@v))<.5 for u in anchors for v in anchors):continue
        result.append(row)
    return result
