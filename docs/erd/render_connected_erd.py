"""Export the connected layout as an editable one-page draw.io ERD and previews."""
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
D=json.loads((OUT/'connected-layout.json').read_text())
SCHEMA=json.loads((OUT/'schema-metadata.json').read_text())
TABLES={t['name']:t for t in SCHEMA['tables']}
W,H=D['width'],D['height']
BOXES=D['boxes'];EDGES={e['id']:e for e in D['edges']}
ROUTES=D['routes'];CONTS=D['continuations']
FONTDIR=Path('C:/Windows/Fonts')
fonts={}
def font(size,bold=False):
    key=(size,bold)
    if key not in fonts:fonts[key]=ImageFont.truetype(str(FONTDIR/('arialbd.ttf' if bold else 'arial.ttf')),size)
    return fonts[key]

def segments(points):return list(zip(points,points[1:]))
def intersect(a,b,c,d):
    ax,ay=a;bx,by=b;cx,cy=c;dx,dy=d
    if ay==by and cy==dy:
        return ay==cy and max(min(ax,bx),min(cx,dx))<=min(max(ax,bx),max(cx,dx))
    if ax==bx and cx==dx:
        return ax==cx and max(min(ay,by),min(cy,dy))<=min(max(ay,by),max(cy,dy))
    if ax==bx:return intersect(c,d,a,b)
    return min(ax,bx)<=cx<=max(ax,bx) and min(cy,dy)<=ay<=max(cy,dy)

all_segments=[]
for rid,r in ROUTES.items():
    all_segments += [(rid,a,b) for a,b in segments(r['points'])]
for rid,ports in CONTS.items():
    for p in ports:
        all_segments.append((rid,p['end'],[v*8 for v in p['point']]))
crossings=[]
for i,(rid,a,b) in enumerate(all_segments):
    assert a[0]==b[0] or a[1]==b[1], (rid,a,b)
    for rid2,c,d in all_segments[i+1:]:
        if rid!=rid2 and intersect(a,b,c,d):crossings.append((rid,rid2))
assert not crossings,crossings

def rect_hits_segment(rect,a,b):
    x,y,w,h=rect
    if a[0]==b[0]:return x<a[0]<x+w and max(min(a[1],b[1]),y)<min(max(a[1],b[1]),y+h)
    return y<a[1]<y+h and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w)

for rid,a,b in all_segments:
    for n,box in BOXES.items():
        assert not rect_hits_segment((box['x'],box['y'],box['w'],box['h']),a,b),('Line through table',rid,n)

mx=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','version':'24.7.17'})
diagram=ET.SubElement(mx,'diagram',{'id':'ved-connected-erd','name':'Complete ERD'})
model=ET.SubElement(diagram,'mxGraphModel',{'dx':str(W),'dy':str(H),'grid':'1','gridSize':'8','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(W),'pageHeight':str(H),'background':'#FFFFFF'})
root=ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',{'id':'0'});ET.SubElement(root,'mxCell',{'id':'1','parent':'0'})
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Complete VED Electrical Services entity relationship diagram"><rect width="{W}" height="{H}" fill="white"/>']
im=Image.new('RGB',(W,H),'white');pen=ImageDraw.Draw(im)
counter=0

def shape(value,x,y,w,h,*,size=13,bold=False,fill='white',border=True,parent='1',cid=None,px=0,py=0,align='left',rotate=False):
    global counter
    counter+=1
    cid=cid or f'v{counter}'
    s=f'rounded=0;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={"#555555" if border else "none"};fontFamily=Arial;fontSize={size};fontColor=#111111;fontStyle={1 if bold else 0};align={align};verticalAlign=middle;spacing=4;'
    if rotate:s+='rotation=90;'
    c=ET.SubElement(root,'mxCell',{'id':cid,'value':value,'vertex':'1','parent':parent,'style':s})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    stroke='#555' if border else 'none'
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>')
    pen.rectangle((x,y,x+w,y+h),fill=fill,outline='#555555' if border else None,width=1)
    lines=value.split('\n');lh=size+3
    assert len(lines)*lh<=h+4,('Text height',value,h)
    for idx,line in enumerate(lines):
        fw=font(size,bold).getlength(line)
        assert fw<=w-6,('Text width',line,w,fw)
        tx=x+4 if align=='left' else x+(w-fw)/2
        ty=y+(h-len(lines)*lh)/2+idx*lh
        svg.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="#111">{html.escape(line)}</text>')
        pen.text((tx,ty),line,font=font(size,bold),fill='#111111')
    return cid

def path(points,width=1.4):
    svg.append('<path d="'+' '.join(('M' if i==0 else 'L')+f' {x} {y}' for i,(x,y) in enumerate(points))+f'" fill="none" stroke="#222" stroke-width="{width}"/>')
    pen.line([tuple(p) for p in points],fill='#222222',width=2)

def marker(end,nextpoint,kind):
    ex,ey=end;nx,ny=nextpoint
    dist=math.hypot(nx-ex,ny-ey)
    ux,uy=(nx-ex)/dist,(ny-ey)/dist
    vx,vy=-uy,ux
    def p(a,b=0):return (ex+a*ux+b*vx,ey+a*uy+b*vy)
    def bar(a):path([p(a,-5),p(a,5)],1)
    def circle(a):
        cx,cy=p(a)
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="white" stroke="#222"/>')
        pen.ellipse((cx-3,cy-3,cx+3,cy+3),fill='white',outline='#222222')
    if kind=='many':
        for v in (-5,0,5):path([p(0,v),p(10)],1)
        circle(15)
    elif kind=='optional':bar(4);circle(12)
    else:bar(4);bar(9)

shape('VED ELECTRICAL SERVICES',120,28,1800,46,size=30,bold=True,border=False)
shape('COMPLETE ENTITY RELATIONSHIP DIAGRAM',120,78,2100,54,size=36,bold=True,border=False)
shape('33 tables  |  303 columns  |  60 relationships  |  Verified against the live XAMPP database',120,140,2200,32,size=20,border=False)
shape('PK = primary key     FK R## = foreign key / relationship ID     ? = nullable field',2420,32,1340,34,size=18,border=False)
shape('Match each R## line to the FK row with the same ID. Lines connect tables, not workflows.',2420,71,1340,32,size=17,border=False)
shape('Matching boxed C-R## labels continue the SAME relationship without a crossing.',2420,108,1340,32,size=17,border=False)
shape('Crow\'s foot = zero or many     Double bar = exactly one     Circle + bar = zero or one',2420,145,1340,32,size=17,border=False)

# All table groups exist before edges; the graph can be edited in diagrams.net.
for name,b in BOXES.items():
    group=ET.SubElement(root,'mxCell',{'id':'table-'+name,'value':'','vertex':'1','parent':'1','style':'group;connectable=1;','erdTable':name})
    ET.SubElement(group,'mxGeometry',{'x':str(b['x']),'y':str(b['y']),'width':str(b['w']),'height':str(b['h']),'as':'geometry'})

# Draw relationship lines under the table graphics.
for rid,r in ROUTES.items():
    e=EDGES[rid]
    a,b=BOXES[e['child']],BOXES[e['parent']]
    start,end=r['source']['end'],r['target']['end']
    style='edgeStyle=none;rounded=0;html=0;strokeColor=#222222;strokeWidth=1.3;'
    style+=f'startArrow={"ERzeroToOne" if e["unique"] else "ERzeroToMany"};endArrow={"ERone" if e["required"] else "ERzeroToOne"};startSize=10;endSize=10;'
    style+=f'exitX={(start[0]-a["x"])/a["w"]};exitY={(start[1]-a["y"])/a["h"]};entryX={(end[0]-b["x"])/b["w"]};entryY={(end[1]-b["y"])/b["h"]};exitPerimeter=0;entryPerimeter=0;'
    c=ET.SubElement(root,'mxCell',{'id':'edge-'+rid,'value':'','edge':'1','parent':'1','source':'table-'+e['child'],'target':'table-'+e['parent'],'style':style,'erdRelationship':rid})
    geometry=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
    points=ET.SubElement(geometry,'Array',{'as':'points'})
    for x,y in r['points'][1:-1]:ET.SubElement(points,'mxPoint',{'x':str(x),'y':str(y)})
    path(r['points'])
    marker(r['points'][0],r['points'][1],'optional' if e['unique'] else 'many')
    marker(r['points'][-1],r['points'][-2],'one' if e['required'] else 'optional')

field_count=0
for name,b in BOXES.items():
    t=TABLES[name];x,y=b['x'],b['y'];parent='table-'+name
    shape(name,x,y,360,28,bold=True,size=14,fill='#F0F0F0',parent=parent,px=x,py=y,align='center')
    fks={e['column']:e['id'] for e in EDGES.values() if e['child']==name}
    for i,c in enumerate(t['columns']):
        key='PK' if c['name'] in t['primary_key'] else ''
        if c['name'] in fks:key+=('/' if key else '')+'FK '+fks[c['name']]
        cy=y+28+i*24
        shape(key,x,cy,86,24,size=11,parent=parent,px=x,py=y)
        shape(c['name']+(' ?' if c['nullable'] else ''),x+86,cy,274,24,size=13,parent=parent,px=x,py=y)
        field_count+=1
    if name=='interpretation_releases':
        shape('No declared foreign keys.',x,y+b['h']+10,360,28,size=14,border=False)

# Place one explicit relationship ID on a clear segment of each direct connector.
label_rects=[]
for rid,r in ROUTES.items():
    candidates=[]
    for a,b in segments(r['points']):
        length=abs(a[0]-b[0])+abs(a[1]-b[1])
        if a[1]==b[1] and length>=70:
            for fraction in (.5,.25,.75):
                cx=a[0]+(b[0]-a[0])*fraction
                candidates.append((cx-14,a[1]-7,28,14,False))
        elif a[0]==b[0] and length>=70:
            for fraction in (.5,.25,.75):
                cy=a[1]+(b[1]-a[1])*fraction
                candidates.append((a[0]-7,cy-14,14,28,True))
    chosen=None
    for x,y,w,h,vertical in candidates:
        rect=(x,y,w,h)
        if any(rect_hits_segment(rect,a,b) for rr,a,b in all_segments if rr!=rid):continue
        if any(x<rx+rw and x+w>rx and y<ry+rh and y+h>ry for rx,ry,rw,rh in label_rects):continue
        if any(x<bb['x']+bb['w'] and x+w>bb['x'] and y<bb['y']+bb['h'] and y+h>bb['y'] for bb in BOXES.values()):continue
        chosen=(x,y,w,h,vertical);break
    assert chosen,('No label space',rid)
    x,y,w,h,vertical=chosen;label_rects.append((x,y,w,h))
    # Native edge labels follow their edge; the preview uses the exact chosen spot.
    label=ET.SubElement(root,'mxCell',{'id':'label-'+rid,'value':rid,'vertex':'1','parent':'edge-'+rid,
         'style':f'text;html=0;align=center;verticalAlign=middle;resizable=0;points=[];fontFamily=Arial;fontSize=10;fillColor=#FFFFFF;strokeColor=none;rotation={90 if vertical else 0};'})
    # Relative edge label placement is derived from cumulative route length.
    points=r['points'];total=sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in segments(points));walk=0;at=None
    cx,cy=x+w/2,y+h/2
    for a,b in segments(points):
        length=abs(a[0]-b[0])+abs(a[1]-b[1])
        if min(a[0],b[0])<=cx<=max(a[0],b[0]) and min(a[1],b[1])<=cy<=max(a[1],b[1]):
            at=walk+abs(cx-a[0])+abs(cy-a[1]);break
        walk+=length
    assert at is not None
    geo=ET.SubElement(label,'mxGeometry',{'x':str(at/total*2-1),'y':'0','width':'28','height':'14','relative':'1','as':'geometry'})
    ET.SubElement(geo,'mxPoint',{'x':'-14','y':'-7','as':'offset'})
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>')
    pen.rectangle((x,y,x+w,y+h),fill='white')
    if not vertical:
        fw=font(10).getlength(rid)
        svg.append(f'<text x="{cx}" y="{cy+3.5}" text-anchor="middle" font-family="Arial" font-size="10">{rid}</text>')
        pen.text((cx-fw/2,cy-6),rid,font=font(10),fill='#111')
    else:
        svg.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" transform="rotate(90 {cx} {cy})" font-family="Arial" font-size="10">{rid}</text>')
        temp=Image.new('RGB',(28,14),'white');td=ImageDraw.Draw(temp);fw=font(10).getlength(rid);td.text((14-fw/2,1),rid,font=font(10),fill='#111');temp=temp.rotate(-90,expand=True);im.paste(temp,(round(x),round(y)))

for rid,ports in CONTS.items():
    for index,p in enumerate(ports):
        cx,cy=[v*8 for v in p['point']]
        ex,ey=p['end']
        # Continue with an explicit matching tag. No remote table duplication.
        eid=f'continuation-{rid}-{index}'
        e=EDGES[rid]
        start_arrow=('ERzeroToOne' if e['unique'] else 'ERzeroToMany') if index==0 else ('ERone' if e['required'] else 'ERzeroToOne')
        c=ET.SubElement(root,'mxCell',{'id':eid,'value':'','edge':'1','parent':'1','style':f'edgeStyle=none;endArrow=none;startArrow={start_arrow};startSize=10;strokeColor=#222222;strokeWidth=1.3;'})
        geo=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
        ET.SubElement(geo,'mxPoint',{'x':str(ex),'y':str(ey),'as':'sourcePoint'})
        ET.SubElement(geo,'mxPoint',{'x':str(cx),'y':str(cy),'as':'targetPoint'})
        path([(ex,ey),(cx,cy)])
        marker((ex,ey),(cx,cy),('optional' if e['unique'] else 'many') if index==0 else ('one' if e['required'] else 'optional'))
        tag_rect=(cx-23,cy-9,46,18)
        assert not any(rect_hits_segment(tag_rect,a,b) for rr,a,b in all_segments if rr!=rid), ('Continuation collision',rid)
        shape('C-'+rid,cx-23,cy-9,46,18,size=10,bold=True,align='center')

# Add a compact continuation key in unused lower-left space, on the SAME canvas.
lx,ly=200,BOXES['interpretation_page_outcomes']['y']
shape('CONTINUATION KEY',lx,ly,1040,32,size=20,bold=True,border=False)
shape('Match the two C-R## boxes. These complete the same foreign-key relationship.',lx,ly+36,1040,28,size=15,border=False)
for i,(rid,ports) in enumerate(CONTS.items()):
    e=EDGES[rid]
    value=f'C-{rid}   {e["child"]}.{e["column"]}  →  {e["parent"]}.id'
    # ASCII arrow for dependable font support in draw.io.
    value=value.replace('→','->')
    shape(value,lx,ly+76+i*25,1120,25,size=12,border=False)
shape('Only database-enforced relationships are shown. Original tables and field names are preserved.',120,H-74,W-240,30,size=17,border=False)

svg.append('</svg>')
ET.indent(mx)
ET.ElementTree(mx).write(OUT/'ved-electrical-erd.drawio',encoding='utf-8',xml_declaration=True)
(OUT/'ved-electrical-erd.svg').write_text(''.join(svg),encoding='utf-8')
im.save(OUT/'ved-electrical-erd.png')
im.thumbnail((1500,1800));im.save(OUT/'connected-overview.png')
html_preview='''<!doctype html><html lang="en"><meta charset="utf-8"><title>VED — complete connected ERD</title><style>body{margin:0;font-family:Arial;background:#e8e8e8;color:#111}header{padding:16px;background:white;position:sticky;top:0}button{padding:7px 15px;margin-left:8px}main{overflow:auto;padding:20px}#sheet{display:block;background:white;width:100%;height:auto}body.actual #sheet{width:3864px} @media print{header{display:none}main{overflow:visible;padding:0}#sheet{width:100%}}</style><header><strong>VED Electrical Services — Complete ERD</strong><button onclick="document.body.classList.remove('actual')">Fit whole diagram</button><button onclick="document.body.classList.add('actual')">Readable size · scroll to explore</button><span> One canvas · 33 tables · 60 relationships</span></header><main>'''+''.join(svg).replace('<svg ','<svg id="sheet" ',1)+'</main></html>'
(OUT/'ved-electrical-erd-preview.html').write_text(html_preview,encoding='utf-8')
assert len(ET.parse(OUT/'ved-electrical-erd.drawio').findall('diagram'))==1
assert len(BOXES)==33 and field_count==303 and len(ROUTES)+len(CONTS)==60
report={'pages':1,'tables':33,'columns':303,'foreign_keys':60,'direct_relationships':len(ROUTES),'continuation_pairs':len(CONTS),
        'relationship_crossings':0,'connector_table_collisions':0,'directly_connected_tables':32,
        'standalone_table':'interpretation_releases (no declared foreign keys)','xml_parse':'PASS','text_fit':'PASS',
        'diagrams_net_editor_import':'NOT TESTED'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
