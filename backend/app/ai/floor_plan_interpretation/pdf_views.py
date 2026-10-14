"""Conservative floor-view proposals from native captions and visual anchors.

Only captioned multi-view sheets with independently visible long image banks
are scoped automatically. These are partial, reviewable regions, not proof of
building boundaries. Missing/ambiguous evidence retains the raster fallback.
"""
import math
import re

from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion

VERSION = 'caption-and-image-bank-views-v1'
MAX_VIEWS = 8
FLOOR = re.compile(r'^(?:GROUND(?: FLOOR)?|MEZZANINE(?: FLOOR)?|BASEMENT(?: \d+)?(?: FLOOR)?|'
                   r'(?:FIRST|SECOND|THIRD|FOURTH|[0-9]+(?:ST|ND|RD|TH)?) FLOOR)$',re.I)


def propose_pdf_views(evidence):
    """Return no automatic scopes rather than invent a crop on uncertain sheets."""
    width,height=(evidence['source_plane'][k] for k in ('width_pixels','height_pixels'))
    texts=[o for o in evidence['objects'] if o.get('text')]
    labels=[]
    for obj in texts:
        label=' '.join(obj['text'].split())
        if not FLOOR.fullmatch(label):continue
        a,b,c,d=obj['bounds'];font=max(1,d-b)
        layout=next((t for t in texts if re.search(r'\bLAYOUT\b',t['text'],re.I)
            and abs(t['bounds'][0]-a)<font*2 and 0<=t['bounds'][1]-d<font*3),None)
        if layout:labels.append((obj,label))
    labels.sort(key=lambda row:(row[0]['bounds'][0],row[0]['bounds'][1]))
    if not 2<=len(labels)<=MAX_VIEWS:return ()
    # Long sheet dividers identify separate columns; they do NOT become walls.
    dividers={0.,float(width)}
    for obj in evidence['objects']:
        commands=obj.get('commands',())
        if len(commands)!=2 or not obj.get('stroke') or obj.get('dash_array'):continue
        a,b=commands
        if a[0]==2 and b[0]==0 and abs(a[1]-b[1])<1 and abs(a[2]-b[2])>height*.5:
            dividers.add((a[1]+b[1])/2)
    dividers=sorted(dividers)
    result=[]
    for caption,label in labels:
        a,top,c,_=caption['bounds'];center=(a+c)/2
        left=max(v for v in dividers if v<center)
        right=min(v for v in dividers if v>center)
        # Views in the same column need a stronger classifier; do not merge them.
        if any(left<(other['bounds'][0]+other['bounds'][2])/2<right
               for other,_ in labels if other is not caption):return ()
        banks=[]
        for obj in evidence['objects']:
            if obj['type']!=3:continue
            x,y,x2,y2=obj['bounds'];w,h=x2-x,y2-y
            if (min(w,h)>0 and max(w,h)/min(w,h)>=8 and max(w,h)>=min(width,height)*.07
                    and left<=x<x2<=right and 0<=y<y2<top):banks.append(obj)
        if len(banks)<2:return ()
        x=min(o['bounds'][0] for o in banks);y=min(o['bounds'][1] for o in banks)
        x2=max(o['bounds'][2] for o in banks);y2=max(o['bounds'][3] for o in banks)
        padding=max(3,min(x2-x,y2-y)*.12)
        x=max(math.ceil(left+1),math.floor(x-padding));y=max(0,math.floor(y-padding))
        x2=min(math.floor(right-1),math.ceil(x2+padding));y2=min(math.floor(top-1),math.ceil(y2+padding))
        if min(x2-x,y2-y)<64:return ()
        region=DrawingRegion(x=x,y=y,width=x2-x,height=y2-y)
        result.append(dict(label=label,region=region,caption_object_id=caption['id'],
                           anchor_object_ids=[o['id'] for o in banks],state='proposed_partial'))
    return tuple(result)


def view_summary(views):
    return [dict(label=v['label'],region=v['region'].model_dump(),state=v['state'],
                 caption_object_id=v['caption_object_id'],anchor_object_ids=v['anchor_object_ids']) for v in views]
