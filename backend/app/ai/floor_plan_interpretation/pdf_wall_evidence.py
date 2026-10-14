"""Reject only source-identified repeated hatch strokes, never all angled walls."""
import json
import math

import cv2
import numpy as np

from app.ai.floor_plan_interpretation.candidate import CandidateCollection, CandidateWarning

VERSION='regular-vector-hatch-wall-separation-v1'


def _hatch_observation(wall, index, gray):
    a=np.array([wall.start.x,wall.start.y]);b=np.array([wall.end.x,wall.end.y])
    length=float(np.linalg.norm(b-a));axis=(b-a)/length;normal=np.array([-axis[1],axis[0]])
    radius=max(8,min(gray.shape)*.025)
    box=[min(a[0],b[0])-radius,min(a[1],b[1])-radius,
         max(a[0],b[0])+radius,max(a[1],b[1])+radius]
    rows=index.query(box)
    if len(rows)>4096:return None
    groups={}
    midpoint=(a+b)/2
    for obj in rows:
        commands=obj.get('commands',())
        if (len(commands)!=2 or not obj.get('stroke') or obj.get('fill_mode')
                or obj.get('dash_array') or obj.get('clip_paths') or obj.get('level')):continue
        first,last=commands
        if first[0]!=2 or last[0]!=0 or last[3]:continue
        c=np.array(first[1:3]);d=np.array(last[1:3]);delta=d-c
        distance=float(np.linalg.norm(delta))
        if distance<8 or abs(float(delta@normal))/distance>math.sin(math.radians(1)):continue
        lo,hi=sorted(float((p-midpoint)@axis) for p in (c,d))
        if not lo<=0<=hi:continue
        offset=float((c-midpoint)@normal)
        if abs(offset)>radius:continue
        style=(obj.get('stroke_width'),tuple(obj.get('stroke_color') or ()),tuple(obj['transform'][:4]))
        groups.setdefault(style,[]).append((offset,lo,hi,obj['id']))
    for observations in groups.values():
        # Not merely parallel lines: a densely regular family, and this actual
        # candidate must coincide with one of its independently exported strokes.
        offsets=sorted(set(round(o[0],1) for o in observations))
        gaps=np.diff(offsets)
        if len(offsets)<8 or len(gaps)<7:continue
        positive=gaps[gaps>1]
        if len(positive)<7 or np.max(positive)>np.min(positive)*1.5:continue
        # Raster consolidation may center a thin hatch "band" between its
        # exported strokes. Bound that allowance by the detected band itself.
        center_tolerance=max(1.5,(wall.estimated_thickness_pixels or 3)*.35)
        if not any(abs(offset)<=center_tolerance and lo<=-length*.40 and hi>=length*.40
                   for offset,lo,hi,_ in observations):continue
        # A filled structural band stays eligible even among repeated lines.
        half=max(3,(wall.estimated_thickness_pixels or 6)*.45)
        points=(a+np.linspace(.1,.9,32)[:,None]*(b-a))[:,None,:]
        points=points+np.linspace(-half,half,11)[None,:,None]*normal
        xy=np.rint(points).astype(int)
        valid=(xy[...,0]>=0)&(xy[...,0]<gray.shape[1])&(xy[...,1]>=0)&(xy[...,1]<gray.shape[0])
        if not valid.all():continue
        density=float((gray[xy[...,1],xy[...,0]]<185).mean())
        if density>=.45:continue
        return dict(start=wall.start.model_dump(),end=wall.end.model_dump(),
                    primitive_ids=sorted(o[3] for o in observations)[:32],
                    regular_parallel_count=len(offsets),band_ink_fraction=round(density,5))
    return None


def with_pdf_wall_evidence(payload, image_rgb, index):
    gray=cv2.cvtColor(image_rgb,cv2.COLOR_RGB2GRAY)
    kept=[];suppressed=[]
    for wall in payload.walls.items:
        evidence=_hatch_observation(wall,index,gray)
        if evidence:suppressed.append(evidence)
        else:kept.append(wall)
    if not suppressed:return payload
    # Keep the original primitive geometry and suppressions as machine evidence.
    warnings=tuple(CandidateWarning(code='pdf_repeated_hatch_wall',severity='info',
        message='Repeated source hatch stroke excluded from wall proposals: '+json.dumps(e,separators=(',',':')))
        for e in suppressed)
    if len(payload.warnings)+len(warnings)>256:return payload
    return type(payload).model_validate(payload.model_copy(update={
        'walls':CandidateCollection(state='partial',items=tuple(kept),truncated=payload.walls.truncated),
        'rooms':CandidateCollection(state='unavailable'),
        'warnings':payload.warnings+warnings,'document_state':'partial'}).model_dump())
