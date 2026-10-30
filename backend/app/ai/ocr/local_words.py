"""Bounded, offline text recognition. Coordinates always return to source pixels."""
import csv
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from tempfile import TemporaryDirectory
import cv2
from PIL import Image

VERSION='local-dimension-ocr-v1'


def _views(rgb):
    height,width=rgb.shape[:2]
    scale=min(3.,2200/max(width,height))
    views=[(cv2.resize(rgb,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC),0,0,scale)]
    # Ruling lines frequently join dimension digits into one unreadable block.
    # This derivative is OCR-only; detector inputs and originals remain intact.
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    ink=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,11)
    horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(40,width//18),1)))
    vertical=cv2.morphologyEx(ink,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(40,height//18))))
    clean=255-cv2.subtract(ink,cv2.bitwise_or(horizontal,vertical))
    views.append((cv2.cvtColor(cv2.resize(clean,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC),cv2.COLOR_GRAY2RGB),0,0,scale))
    blocks,_=cv2.findContours(cv2.dilate(255-clean,cv2.getStructuringElement(cv2.MORPH_RECT,(5,1))),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    patches=[]
    for contour in blocks:
        x,y,w,h=cv2.boundingRect(contour)
        if 7<=h<=60 and 1.3<=w/h<=14 and w<=240:
            patches.append((x,y,w,h))
    for x,y,w,h in sorted(patches,key=lambda box:(box[1],box[0]))[:24]:
        left,top=max(0,x-5),max(0,y-5)
        crop=rgb[top:min(height,y+h+5),left:min(width,x+w+5)]
        factor=min(3.,2200/max(crop.shape[:2]))
        large=cv2.resize(crop,None,fx=factor,fy=factor,interpolation=cv2.INTER_CUBIC)
        large=cv2.copyMakeBorder(large,24,24,24,24,cv2.BORDER_CONSTANT,value=(255,255,255))
        views.append((large,left-24/factor,top-24/factor,factor))
    if max(width,height)>2200:
        # Cover large sheets at useful text resolution, with a fixed work bound.
        edge=max(1400,math.ceil(math.sqrt(width*height/8)))
        for y in range(0,height,edge-120):
            for x in range(0,width,edge-120):
                crop=rgb[y:min(height,y+edge),x:min(width,x+edge)]
                factor=min(1.,2200/max(crop.shape[:2]))
                views.append((cv2.resize(crop,None,fx=factor,fy=factor),x,y,factor))
                if len(views)>=41:return views
    return views


def _recognize_words(rgb,*,max_items=2000):
    """No shell interpolation, network calls, model download or original-file edits."""
    if max_items<=0:return ()
    executable=shutil.which('tesseract')
    powershell=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not executable and (os.name!='nt' or not powershell.is_file()):return ()
    views=_views(rgb)
    with TemporaryDirectory(prefix='ved-local-ocr-') as temporary:
        paths=[]
        for index,(image,*_) in enumerate(views):
            path=Path(temporary)/f'view-{index}.png'
            Image.fromarray(image).save(path)
            paths.append(str(path))
        try:
            if executable:
                raw=[]
                deadline=time.monotonic()+40
                for index,path in enumerate(paths):
                    remaining=deadline-time.monotonic()
                    if remaining<=0:break
                    result=subprocess.run([executable,path,'stdout','--psm','11','tsv'],capture_output=True,text=True,timeout=min(8,remaining),check=True)
                    for word in csv.DictReader(io.StringIO(result.stdout),delimiter='\t'):
                        if word.get('text','').strip():raw.append(dict(image=index,text=word['text'],x=float(word['left']),y=float(word['top']),width=float(word['width']),height=float(word['height'])))
            else:
                script=Path(__file__).with_name('windows_words.ps1').read_text(encoding='utf-8')
                result=subprocess.run([str(powershell),'-NoProfile','-NonInteractive','-Command',script],
                    input=json.dumps(dict(paths=paths)),capture_output=True,text=True,encoding='utf-8',timeout=45,check=True,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                raw=json.loads(result.stdout.lstrip('\ufeff'))
        except (OSError,ValueError,subprocess.SubprocessError):return ()
    height,width=rgb.shape[:2]
    output=[]; by_text={}
    for word in raw[:20000]:
        index=word.get('image',-1)
        if not isinstance(index,int) or not 0<=index<len(views):continue
        _,offset_x,offset_y,scale=views[index]
        text=''.join(c for c in str(word.get('text','')) if ord(c)>=32).strip()[:200]
        if not text:continue
        x=max(0.,offset_x+float(word['x'])/scale); y=max(0.,offset_y+float(word['y'])/scale)
        w=min(float(word['width'])/scale,width-x); h=min(float(word['height'])/scale,height-y)
        if w<=0 or h<=0:continue
        if any(abs(item['x']-x)<max(4,w*.4) and abs(item['y']-y)<max(4,h*.4) for item in by_text.get(text,[])):continue
        item=dict(text=text,x=x,y=y,width=w,height=h)
        output.append(item);by_text.setdefault(text,[]).append(item)
    # Numeric evidence survives even on note-heavy sheets.
    output.sort(key=lambda item:(not any(c.isdigit() for c in item['text']),item['y'],item['x']))
    return tuple(output[:max_items])


def recognize_words(rgb,*,max_items=2000):
    try:return _recognize_words(rgb,max_items=max_items)
    except (OSError,ValueError,cv2.error,subprocess.SubprocessError):return ()
