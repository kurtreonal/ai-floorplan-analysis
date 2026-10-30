"""Add dimension evidence without promoting OCR to calibrated measurements."""
import re
import cv2
import numpy as np
from app.ai.floor_plan_interpretation.candidate import CandidateCollection,OcrEvidence,PixelBounds,ScaleProposal,EvidenceRegion,AffineTransform
from app.ai.ocr.local_words import recognize_words

NUMBER=re.compile(r'^(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(mm|cm|m|millimeters?|millimetres?|meters?|metres?)?$',re.I)
UNITS={'mm':'millimeter','cm':'centimeter','m':'meter','millimeter':'millimeter','millimeters':'millimeter','millimetre':'millimeter','millimetres':'millimeter','meter':'meter','meters':'meter','metre':'meter','metres':'meter'}


def with_dimension_ocr(payload,rgb,*,region=None):
    x,y=(region.x,region.y) if region is not None else (0,0)
    image=rgb[y:y+region.height,x:x+region.width] if region is not None else rgb
    # Eight independently processed views must still fit the 2048-item envelope.
    evidence_limit=256
    words=recognize_words(image,max_items=max(0,evidence_limit-len(payload.ocr.items)))
    if not words:return payload
    regions=list(payload.regions)
    root=EvidenceRegion(id=f"region-{max([int(r.id.rsplit('-',1)[-1]) for r in regions]+[0])+1:04d}",kind='overview',
        bounds=PixelBounds(x=float(x),y=float(y),width=float(image.shape[1]),height=float(image.shape[0])),local_to_source=AffineTransform(a=1,b=0,c=0,d=1,e=float(x),f=float(y)))
    regions.append(root)
    evidence=list(payload.ocr.items)
    identity=max([int(item.id.rsplit('-',1)[-1]) for item in evidence]+[0])
    numeric=[]
    for word in words:
        identity+=1
        bounds=PixelBounds(x=word['x']+x,y=word['y']+y,width=word['width'],height=word['height'])
        item=OcrEvidence(id=f'ocr-{identity:04d}',region_id=root.id,bounds=bounds,text=word['text'],normalized_text=word['text'].lower())
        evidence.append(item)
        match=NUMBER.fullmatch(word['text'])
        if match and float(match[1].replace(',',''))>0:numeric.append((item,match))
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    lines=cv2.HoughLinesP(cv2.Canny(gray,60,180),1,np.pi/180,threshold=60,minLineLength=max(50,min(gray.shape)*.12),maxLineGap=8)
    spans=[]
    for line in (() if lines is None else lines[:,0]):
        x1,y1,x2,y2=map(float,line)
        if abs(y1-y2)>2:continue
        left,right=sorted((x1,x2)); baseline=(y1+y2)/2
        labels=[(item,match) for item,match in numeric if left<=item.bounds.x-x+item.bounds.width/2<=right and
            0<=baseline-(item.bounds.y-y+item.bounds.height)<=max(16,item.bounds.height*1.5)]
        # Multiple labels along a chain cannot each represent its full span.
        if len(labels)==1 and right-left>labels[0][0].bounds.width*2:spans.append((labels[0],right-left))
    scales=list(payload.scales.items)
    scale_index=max([int(item.id.rsplit('-',1)[-1]) for item in scales]+[0])
    seen={}
    for (item,match),length in spans:
        if item.id in seen:continue
        seen[item.id]=True
        unit=UNITS.get((match[2] or '').lower())
        scale_index+=1
        scales.append(ScaleProposal(id=f'scale-{scale_index:04d}',state='proposed' if unit else 'unknown',
            pixel_distance=length if unit else None,real_distance=float(match[1].replace(',','')) if unit else None,real_unit=unit,
            evidence_refs=(f'ocr:{item.id}',),ambiguity='unknown'))
        if len(scales)>=2000:break
    signals=payload.page.signals.model_copy(update={'dimensions':'visible' if spans else payload.page.signals.dimensions})
    truncated=payload.ocr.truncated or len(evidence)>=evidence_limit
    return type(payload).model_validate(payload.model_copy(update={'regions':tuple(regions),'ocr':CandidateCollection(state='partial' if truncated else 'completed',items=tuple(evidence),truncated=truncated),
        'scales':CandidateCollection(state='completed' if scales else 'empty',items=tuple(scales)),
        'page':payload.page.model_copy(update={'signals':signals})}).model_dump())
