"""Enlarge text in the user's embedded native charts without changing their design."""
import base64
import copy
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from urllib.parse import quote, unquote
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

OUT = Path(__file__).resolve().parent / 'larger-text'
OUT.mkdir(exist_ok=True)
SOURCES = [Path(f'C:/Users/kupal/Downloads/Gantt Chart-{n}.drawio.png') for n in (1, 2)]
SCALE = 3
FONTS = {}
NEW_SIZE = {11:14,12:16,13:17,14:19,16:21,20:26,21:27,22:28}


def font(size,bold=False,scale=1):
    k=(size,bold,scale)
    if k not in FONTS:
        FONTS[k]=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),round(size*scale))
    return FONTS[k]


def style(cell):
    return dict(part.split('=',1) for part in cell.get('style','').split(';') if '=' in part)


def setstyle(cell,key,value):
    s=cell.get('style','')
    pattern=rf'(?<!\w){re.escape(key)}=[^;]*;'
    if re.search(pattern,s):s=re.sub(pattern,f'{key}={value};',s)
    else:s+=f'{key}={value};'
    cell.set('style',s)


def extract(path,name):
    with Image.open(path) as im:
        root=ET.fromstring(unquote(im.info['mxfile']))
    d=next(d for d in root.findall('diagram') if d.get('name')==name)
    m=d.find('mxGraphModel')
    if m is None:m=ET.fromstring(unquote(zlib.decompress(base64.b64decode(d.text),-15).decode()))
    return copy.deepcopy(m)


def wrap(value,width,size,bold):
    lines=[]
    for para in value.split('\n'):
        line=''
        for word in para.split():
            candidate=(line+' '+word).strip()
            if line and font(size,bold).getlength(candidate)>width:
                lines.append(line);line=word
            else:line=candidate
        lines.append(line)
    return lines


def root_for(diagrams):
    root=ET.Element('mxfile',host='app.diagrams.net',type='device',pages=str(len(diagrams)))
    for number,model in diagrams:
        d=ET.SubElement(root,'diagram',id=f'gantt-larger-text-{number}',name=f'Gantt Chart {number}')
        d.append(copy.deepcopy(model))
    return root


report={'source_files':{},'pages':[],'design_preserved':'PENDING','visual_review':'PENDING','downloads_copy':'PENDING','drawio_editor_import':'NOT TESTED'}
diagrams=[]
for number,path in enumerate(SOURCES,1):
    report['source_files'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    old=extract(path,str(number))
    model=copy.deepcopy(old)
    before={c.get('id'):c for c in old.findall('.//mxCell')}
    cells=model.findall('.//mxCell')
    byid={c.get('id'):c for c in cells}
    changed=[]
    for c in cells:
        if not c.get('value'):continue
        s=style(c)
        original=int(s.get('fontSize',12))
        # Addresses need a smaller increase to remain inside the unchanged rows.
        size=13 if original==11 and s.get('fontStyle')!='1' else NEW_SIZE[original]
        # Original hard wraps were sized for smaller fonts; reflow the same words.
        if '\n' in c.get('value'):c.set('value',' '.join(c.get('value').split()))
        setstyle(c,'fontSize',size)
        # Keep horizontal inset; remove invisible vertical padding to fit larger type.
        setstyle(c,'spacing',0)
        setstyle(c,'spacingLeft',3 if original==11 and s.get('fontStyle')!='1' else 5)
        setstyle(c,'spacingRight',3 if original==11 and s.get('fontStyle')!='1' else 5)
        changed.append({'id':c.get('id'),'text':c.get('value'),'before':original,'after':size})

    def geometry(c):
        g=c.find('mxGeometry')
        if g is None:return None
        x,y=float(g.get('x',0)),float(g.get('y',0))
        parent=c.get('parent')
        visited=set()
        while parent in byid:
            assert parent not in visited
            visited.add(parent)
            p=byid[parent];pg=p.find('mxGeometry')
            if pg is not None:x+=float(pg.get('x',0));y+=float(pg.get('y',0))
            parent=p.get('parent')
        return (x,y,float(g.get('width',0)),float(g.get('height',0)))

    visible=[c for c in cells if c.get('vertex')=='1' and c.get('style')!='group;' and c.find('mxGeometry') is not None]
    boxes=[geometry(c) for c in visible]
    minx,miny=min(g[0] for g in boxes),min(g[1] for g in boxes)
    maxx,maxy=max(g[0]+g[2] for g in boxes),max(g[1]+g[3] for g in boxes)
    width,height=math.ceil(maxx-minx)+2,math.ceil(maxy-miny)+2
    image=Image.new('RGB',(width*SCALE,height*SCALE),'white')
    pen=ImageDraw.Draw(image)
    text_fits=[]
    for c in visible:
        s=style(c)
        x,y,w,h=geometry(c)
        x,y=x-minx+1,y-miny+1
        if not c.get('value'):
            fill=s.get('fillColor','#FFFFFF')
            stroke=s.get('strokeColor','#555555')
            if fill=='none':fill=None
            if stroke=='none':stroke=None
            pen.rectangle((round(x*SCALE),round(y*SCALE),round((x+w)*SCALE),round((y+h)*SCALE)),fill=fill,outline=stroke,width=max(1,round(float(s.get('strokeWidth',1))*SCALE)))
            continue
        size=int(s['fontSize']);bold=s.get('fontStyle')=='1'
        left=float(s.get('spacingLeft',0));right=float(s.get('spacingRight',0))
        lines=wrap(c.get('value'),w-left-right,size,bold)
        line_h=size*1.2
        assert all(font(size,bold).getlength(line)<=w-left-right for line in lines),('Horizontal overflow',c.get('value'),w,size)
        assert len(lines)*line_h<=h+.2,('Vertical overflow',c.get('value'),h,size,lines)
        ty=y+(h-len(lines)*line_h)/2
        for line in lines:
            length=font(size,bold).getlength(line)
            tx=x+left if s.get('align')=='left' else x+(w-length)/2
            # Anchor by font ascender: consistent with the cell's centered line box.
            pen.text((round(tx*SCALE),round(ty*SCALE)),line,font=font(size,bold,SCALE),fill=s.get('fontColor','#000000'),anchor='lt')
            ty+=line_h
        text_fits.append(c.get('id'))

    # Every geometry, label, bar and non-text style is identical to the attached source.
    assert len(cells)==len(before)
    for c in cells:
        b=before[c.get('id')]
        assert {k:v for k,v in c.attrib.items() if k not in {'style','value'}}=={k:v for k,v in b.attrib.items() if k not in {'style','value'}}
        assert ' '.join(c.get('value','').split())==' '.join(b.get('value','').split())
        cg,bg=c.find('mxGeometry'),b.find('mxGeometry')
        assert (ET.tostring(cg) if cg is not None else None)==(ET.tostring(bg) if bg is not None else None)
        if not c.get('value'):assert c.get('style')==b.get('style')
        else:
            bs,ns=style(b),style(c)
            for k in set(bs)|set(ns):
                if k not in {'fontSize','spacing','spacingLeft','spacingRight'}:assert bs.get(k)==ns.get(k)
    assert all(v['after']>v['before'] for v in changed)
    diagrams.append((number,model))
    single=root_for([(number,model)])
    pngmeta=PngImagePlugin.PngInfo()
    pngmeta.add_text('mxfile',quote(ET.tostring(single,encoding='unicode')))
    target=OUT/f'Gantt Chart-{number}-Larger Text.drawio.png'
    image.save(target,pnginfo=pngmeta,dpi=(300,300))
    # A lightweight preview is for visual QA only; delivery retains 3x detail.
    image.resize((width,height),Image.Resampling.LANCZOS).save(OUT/f'preview-{number}.png')
    report['pages'].append({'page':number,'labels_enlarged':len(changed),'font_changes':dict(sorted({str(v['before'])+(' address' if v['after']==13 else ''):v['after'] for v in changed}.items())),'text_fit':'PASS','text_cells_checked':len(text_fits),'geometry_identical':'PASS','wording_identical':'PASS','non_text_styles_identical':'PASS','original_design_bounds':[width,height],'export_pixels':list(image.size),'changed_labels':changed})

root=root_for(diagrams)
ET.indent(root)
target=OUT/'Gantt Charts-Larger Text.drawio'
ET.ElementTree(root).write(target,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(target)
assert len(parsed.findall('diagram'))==2
for d in parsed.findall('diagram'):
    cells=d.findall('.//mxCell');ids={c.get('id') for c in cells}
    assert len(ids)==len(cells)
    assert all(c.get('parent','0') in ids for c in cells)
for number,_ in diagrams:
    with Image.open(OUT/f'Gantt Chart-{number}-Larger Text.drawio.png') as png:
        embedded=ET.fromstring(unquote(png.info['mxfile']))
        assert len(embedded.findall('diagram'))==1
        assert embedded.find('diagram').get('id')==f'gantt-larger-text-{number}'
report['design_preserved']='PASS'
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='pages'}|{'pages':[{k:v for k,v in p.items() if k!='changed_labels'} for p in report['pages']]},indent=2))
