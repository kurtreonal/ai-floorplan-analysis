"""Repository-grounded DFD, with explicitly planned read-only Client flows."""
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent / "compact"
OUT.mkdir(exist_ok=True)
ROOT_PATH=OUT.parents[1]
W=1140
FONT={};SEQ=0;PAGES=[];MX=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','version':'24.7.17'})
def font(size,bold=False):
    k=(size,bold)
    if k not in FONT:FONT[k]=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
    return FONT[k]
def wrapped(value,width,size,bold=False):
    result=[]
    for para in value.split('\n'):
        line=''
        for word in para.split():
            candidate=(line+' '+word).strip()
            if line and font(size,bold).getlength(candidate)>width:
                result.append(line);line=word
            else:line=candidate
        result.append(line)
    assert all(font(size,bold).getlength(x)<=width for x in result),(value,width)
    return result
def cell(value,x,y,w,h,style,parent='1',px=0,py=0,cid=None):
    global SEQ
    SEQ+=1;cid=cid or f'c{SEQ}'
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':value,'vertex':'1','parent':parent,'style':style})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    return cid
def text(value,x,y,w,h,size=15,bold=False,align='left',parent='1',px=0,py=0,fill=False):
    lines=wrapped(value,w-8,size,bold);lh=size+4
    assert len(lines)*lh<=h+2,('Text overflow',value,h,len(lines)*lh)
    assert 0<=x and 0<=y and x+w<=W and y+h<=HEIGHT,('Outside canvas',value)
    cid=cell('\n'.join(lines),x,y,w,h,f'text;html=0;whiteSpace=wrap;fillColor={"#FFFFFF" if fill else "none"};strokeColor=none;fontColor=#000000;fontFamily=Arial;fontSize={size};fontStyle={1 if bold else 0};align={align};verticalAlign=middle;spacing=4;',parent,px,py)
    if fill:
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>');PEN.rectangle((x,y,x+w,y+h),fill='white')
    ty=y+(h-len(lines)*lh)/2
    for s in lines:
        fw=font(size,bold).getlength(s);tx=x+4 if align=='left' else x+(w-fw)/2
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}">{html.escape(s)}</text>')
        PEN.text((tx,ty),s,font=font(size,bold),fill='black');ty+=lh
    return cid
def line(points,dash=False,width=1.2):
    SVG.append('<path d="'+' '.join(('M' if i==0 else 'L')+f' {x} {y}' for i,(x,y) in enumerate(points))+f'" fill="none" stroke="black" stroke-width="{width}"'+(' stroke-dasharray="7 5"' if dash else '')+'/>')
    if not dash:PEN.line([tuple(p) for p in points],fill='black',width=2)
    else:
        for a,b in zip(points,points[1:]):
            length=math.dist(a,b)
            for t in range(0,math.ceil(length),12):
                end=min(t+7,length)
                PEN.line((a[0]+(b[0]-a[0])*t/length,a[1]+(b[1]-a[1])*t/length,a[0]+(b[0]-a[0])*end/length,a[1]+(b[1]-a[1])*end/length),fill='black',width=2)
def begin(name,height,subtitle):
    global ROOT,SVG,PEN,IMAGE,HEIGHT,NODES,FLOWS,LABELS
    HEIGHT=height;NODES={};FLOWS=[];LABELS=[]
    d=ET.SubElement(MX,'diagram',{'id':f'page-{len(PAGES)+1}','name':name})
    m=ET.SubElement(d,'mxGraphModel',{'dx':str(W),'dy':str(height),'grid':'1','gridSize':'10','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(W),'pageHeight':str(height),'background':'#FFFFFF'})
    ROOT=ET.SubElement(m,'root');ET.SubElement(ROOT,'mxCell',{'id':'0'});ET.SubElement(ROOT,'mxCell',{'id':'1','parent':'0'})
    IMAGE=Image.new('RGB',(W,height),'white');PEN=ImageDraw.Draw(IMAGE)
    SVG=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" role="img" aria-label="{html.escape(name)}"><rect width="{W}" height="{height}" fill="white"/>']
    text('Data Flow Diagram - VED Electrical Services',35,15,W-70,32,20,True)
    text('Level 1 | AI floor plan analysis, shared 2D/3D layouts and cost estimation',35,50,W-70,26,14)
    PAGES.append({'name':name,'height':height})
def node(cid,kind,label,x,y,w,h,number='',planned=False):
    NODES[cid]={'kind':kind,'label':label,'x':x,'y':y,'w':w,'h':h,'planned':planned,'number':number}
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':'','vertex':'1','parent':'1','style':'group;'})
    ET.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
    dash='dashed=1;' if planned else ''
    if kind=='store':
        # Open-ended Gane-Sarson data store; code compartment on the left.
        for pts in [[(x,y),(x+w,y)],[(x,y+h),(x+w,y+h)],[(x,y),(x,y+h)],[(x+54,y),(x+54,y+h)]]:
            cell('',min(p[0] for p in pts),min(p[1] for p in pts),max(abs(pts[1][0]-pts[0][0]),1),max(abs(pts[1][1]-pts[0][1]),1),'fillColor=#000000;strokeColor=none;',cid,x,y);line(pts)
        text(number,x+3,y+10,48,h-20,12,True,'center',cid,x,y)
        text(label,x+62,y+10,w-70,h-20,13,False,'center',cid,x,y)
    elif kind=='connector':
        cell(label,x,y,w,h,'ellipse;html=0;fillColor=#FFFFFF;strokeColor=#000000;fontFamily=Arial;fontSize=15;align=center;verticalAlign=middle;',cid,x,y)
        SVG.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="white" stroke="black"/>');PEN.ellipse((x,y,x+w,y+h),fill='white',outline='black')
        # native ellipse already owns its label; preview text only
        fw=font(15,True).getlength(label);PEN.text((x+(w-fw)/2,y+(h-19)/2),label,font=font(15,True),fill='black')
        SVG.append(f'<text x="{x+(w-fw)/2}" y="{y+(h-19)/2+15}" font-family="Arial" font-size="15" font-weight="700">{label}</text>')
    else:
        rounding=12 if kind=='process' else 0
        cell('',x,y,w,h,f'rounded={1 if rounding else 0};arcSize=8;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=1;{dash}',cid,x,y)
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rounding}" fill="white" stroke="black"'+(' stroke-dasharray="7 5"' if planned else '')+'/>')
        PEN.rounded_rectangle((x,y,x+w,y+h),radius=rounding,fill='white',outline='black',width=1)
        if kind=='process':
            line([(x,y+25),(x+w,y+25)])
            cell('',x,y+25,w,1,'fillColor=#000000;strokeColor=none;',cid,x,y)
            text(number,x,y+1,w,23,14,False,'center',cid,x,y)
            text(label,x+12,y+31,w-24,h-39,15,False,'center',cid,x,y)
        else:text(label,x+10,y+8,w-20,h-16,14,False,'center',cid,x,y)
    return cid
def flow(s,t,points,label,lx,ly,lw,dash=False,key=None,center_label=False):
    global SEQ
    assert s in NODES and t in NODES
    a,b=NODES[s],NODES[t];start,end=points[0],points[-1]
    SEQ+=1;fid=f'f{SEQ}'
    style='edgeStyle=none;rounded=0;html=0;endArrow=block;endFill=1;endSize=8;startArrow=none;strokeColor=#000000;strokeWidth=1.1;'
    style+=f'exitX={(start[0]-a["x"])/a["w"]};exitY={(start[1]-a["y"])/a["h"]};entryX={(end[0]-b["x"])/b["w"]};entryY={(end[1]-b["y"])/b["h"]};exitPerimeter=0;entryPerimeter=0;'+('dashed=1;' if dash else '')
    c=ET.SubElement(ROOT,'mxCell',{'id':fid,'value':'','edge':'1','parent':'1','source':s,'target':t,'style':style,'dataLabel':label})
    g=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=ET.SubElement(g,'Array',{'as':'points'})
    for x,y in points[1:-1]:ET.SubElement(arr,'mxPoint',{'x':str(x),'y':str(y)})
    line(points,dash)
    ex,ey=end;ax,ay=points[-2];dist=math.dist(end,points[-2]);ux,uy=(ex-ax)/dist,(ey-ay)/dist
    triangle=[(ex,ey),(ex-8*ux+4*uy,ey-8*uy-4*ux),(ex-8*ux-4*uy,ey-8*uy+4*ux)]
    SVG.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in triangle)+'" fill="black"/>');PEN.polygon(triangle,fill='black')
    label_lines=wrapped(label,lw-8,12)
    label_width=math.ceil(max(font(12).getlength(s) for s in label_lines))+8
    if center_label:lx+=(lw-label_width)/2
    lh=len(label_lines)*16+4
    text(label,lx,ly,label_width,lh,12,fill=True)
    FLOWS.append({'id':fid,'source':s,'target':t,'label':label,'points':points,'planned':dash,'key':key})
    LABELS.append((fid,(lx,ly,label_width,lh)))
def horizontal(s,t,y,label,dash=False,reverse=False,key=None):
    a,b=NODES[s],NODES[t]
    if a['x']<b['x']:x1=a['x']+a['w'];x2=b['x']
    else:x1=a['x'];x2=b['x']+b['w']
    left=min(x1,x2);width=abs(x2-x1)-28
    lines=len(wrapped(label,width-8,12));lh=lines*16+4
    flow(s,t,[(x1,y),(x2,y)],label,left+14,y-lh/2,width,dash,key,True)
def hit(rect,a,b):
    x,y,w,h=rect
    if a[0]==b[0]:return x<a[0]<x+w and max(min(a[1],b[1]),y)<min(max(a[1],b[1]),y+h)
    return y<a[1]<y+h and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w)
def intersection(a,b,c,d):
    ax,ay=a;bx,by=b;cx,cy=c;dx,dy=d
    if ay==by and cy==dy:return ay==cy and max(min(ax,bx),min(cx,dx))<=min(max(ax,bx),max(cx,dx))
    if ax==bx and cx==dx:return ax==cx and max(min(ay,by),min(cy,dy))<=min(max(ay,by),max(cy,dy))
    if ax==bx:return intersection(c,d,a,b)
    return min(ax,bx)<=cx<=max(ax,bx) and min(cy,dy)<=ay<=max(cy,dy)
def end(filename,caption):
    text(caption,35,HEIGHT-115,W-70,28,15,True,'center')
    text('Dashed Client flows are planned: sign-in and authorized saved layout / estimate viewing only.',35,HEIGHT-80,W-70,24,13)
    text('Repeated entity / store labels denote the same actor / data store. Original uploads stay unchanged.',35,HEIGHT-53,W-70,24,13)
    text('Client-to-project access rules require future implementation. Design reference: reference.pdf.',35,HEIGHT-27,W-70,23,12)
    segments=[(f['id'],a,b) for f in FLOWS for a,b in zip(f['points'],f['points'][1:])]
    for i,(fid,a,b) in enumerate(segments):
        assert a[0]==b[0] or a[1]==b[1]
        for other,c,d in segments[i+1:]:
            if fid!=other:assert not intersection(a,b,c,d),('Crossed flows',filename,fid,other)
        for nid,n in NODES.items():
            assert not hit((n['x'],n['y'],n['w'],n['h']),a,b),('Flow through node',fid,nid)
        for lid,rect in LABELS:
            if lid!=fid:assert not hit(rect,a,b),('Flow through label',fid,lid)
    for fid,rect in LABELS:
        for nid,n in NODES.items():assert not (rect[0]<n['x']+n['w'] and rect[0]+rect[2]>n['x'] and rect[1]<n['y']+n['h'] and rect[1]+rect[3]>n['y']),('Label through node',fid,nid)
    for i,(fid,rect) in enumerate(LABELS):
        for other,b in LABELS[i+1:]:
            assert not (rect[0]<b[0]+b[2] and rect[0]+rect[2]>b[0] and rect[1]<b[1]+b[3] and rect[1]+rect[3]>b[1]),('Overlapping labels',fid,other)
    for f in FLOWS:
        a,b=NODES[f['source']],NODES[f['target']]
        assert not (a['kind']=='entity' and b['kind']=='store')
        assert not (a['kind']=='store' and b['kind']=='entity')
        assert not (a['kind']=='store' and b['kind']=='store')
        if a['label'].startswith('Client'):
            assert b['number'] in {'0.0','1.0','4.0','6.0','4.1','6.1'}
            assert f['planned']
    for nid,n in NODES.items():
        if n['kind']=='process':
            assert any(f['source']==nid for f in FLOWS) and any(f['target']==nid for f in FLOWS)
    SVG.append('</svg>');PAGES[-1].update(nodes=NODES,flows=FLOWS,svg=''.join(SVG))
    IMAGE.save(OUT/(filename+'.png'));(OUT/(filename+'.svg')).write_text(PAGES[-1]['svg'],encoding='utf-8')
    print(filename,len(NODES),'nodes',len(FLOWS),'flows',flush=True)


# A complete Level 1 diagram on a single compact sheet.
begin('Level 1 - Complete Compact DFD',1485,'')
node('p1','process','Authentication and\nAccess Control',470,100,190,265,'1.0')
node('p2','process','Project and Floor\nPlan Management',470,405,190,100,'2.0')
node('p3','process','AI Analysis and\nDesigner Review',470,555,190,155,'3.0')
node('p4','process','Shared 2D / 3D\nLayout Management',470,760,190,150,'4.0')
node('p5','process','Electrical Routing\nand Measurements',470,960,190,100,'5.0')
node('p6','process','Materials and\nCost Estimation',470,1110,190,245,'6.0')
# Actors are repeated to keep independent data flows short and free of crossings.
for nid,label,y,h in [
 ('staff1','Admin / Designer',110,62),('client1','Client (planned)',190,62),('provider','OAuth / OIDC\nIdentity Provider',278,72),
 ('designer2','Electrical Designer',416,72),
 ('designer3','Electrical Designer',565,62),('admin3','Administrator',644,62),
 ('designer4','Electrical Designer',770,62),('client4','Client (planned)',846,62),
 ('designer5','Electrical Designer',975,72),
 ('designer6','Electrical Designer',1120,62),('client6','Client (planned)',1200,62),('admin6','Administrator',1280,62)]:
 node(nid,'entity',label,35,y,170,h,planned=nid.startswith('client'))
for nid,label,y,h,code in [
 ('s1','Users / roles /\naccess records',185,80,'D1'),
 ('s2','Projects / floors /\noriginal source files',415,80,'D2'),
 ('s2b','Original source\nfiles / metadata',565,62,'D2'),
 ('s3','Jobs / results /\nreviews / legends',644,62,'D3'),
 ('s4','Canonical layouts',793,70,'D4'),
 ('s4b','Canonical layouts',975,72,'D4'),
 ('s5','Saved route versions',1076,110,'D5'),
 ('s6','Materials / prices /\nestimate snapshots',1210,104,'D6')]:
 node(nid,'store',label,905,y,200,h,code)
# Every request/response and read/write is represented by a separate directional arrow.
for a,b,y,label,dash in [
 ('staff1','p1',128,'Sign-in request',False),('p1','staff1',156,'Session / access result',False),
 ('client1','p1',208,'Sign-in request',True),('p1','client1',236,'Read-only session / access result',True),
 ('p1','provider',297,'OIDC authorization request',False),('provider','p1',329,'Verified identity claims',False),
 ('p1','s1',207,'Identity record updates',False),('s1','p1',243,'User / role / authority data',False),
 ('designer2','p2',433,'Project details / uploaded plan',False),('p2','designer2',472,'Project / upload status',False),
 ('p2','s2',434,'Project / original file data',False),('s2','p2',474,'Saved source records',False),
 ('designer3','p3',583,'Analysis / review corrections',False),('p3','designer3',611,'Candidates / review status',False),
 ('admin3','p3',661,'Approved legend changes',False),('p3','admin3',690,'Legend / update status',False),
 ('p3','s2b',583,'Source / page selectors',False),('s2b','p3',611,'Original page data',False),
 ('p3','s3',661,'Job / review / legend updates',False),('s3','p3',690,'Saved evidence / legends',False),
 ('designer4','p4',788,'Layout edit / save / view request',False),('p4','designer4',816,'Saved layout / version',False),
 ('client4','p4',864,'Saved layout view request',True),('p4','client4',892,'Authorized 2D / 3D layout',True),
 ('p4','s4',814,'Canonical snapshot',False),('s4','p4',844,'Saved geometry / version',False),
 ('designer5','p5',993,'Panel / obstacles / route settings',False),('p5','designer5',1028,'Routes / measured lengths',False),
 ('p5','s4b',993,'Layout version selectors',False),('s4b','p5',1028,'Saved metric geometry',False),
 ('designer6','p6',1138,'Estimate request / material map',False),('p6','designer6',1166,'Saved estimate / total costs',False),
 ('client6','p6',1218,'Stored estimate view request',True),('p6','client6',1246,'Authorized captured cost estimate',True),
 ('admin6','p6',1298,'Material / price import selection',False),('p6','admin6',1326,'Catalog / price update status',False),
 ('p6','s5',1138,'Route version selectors',False),('s5','p6',1166,'Measured route version',False),
 ('p6','s6',1237,'Material / estimate snapshots',False),('s6','p6',1290,'Stored prices / estimates',False)]:
 horizontal(a,b,y,label,dash)
flow('p5','s5',[(660,1050),(790,1050),(790,1100),(905,1100)],'Saved route version',680,1041,210)
for a,b,y1,y2,label in [
 ('p1','p2',365,405,'Designer access'),
 ('p2','p3',505,555,'Source / page IDs'),
 ('p3','p4',710,760,'Approved geometry / scale'),
 ('p4','p5',910,960,'Canonical metric geometry'),
 ('p5','p6',1060,1110,'Routes / verified geometry')]:
 flow(a,b,[(565,y1),(565,y2)],label,586,(y1+y2)/2-10,280)
end('ved-dfd-compact','Complete Level 1 DFD - six connected processes on one sheet')

FILE=OUT/'ved-data-flow-diagram-compact-2026-10-12.drawio'
ET.indent(MX);ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE);assert len(parsed.findall('diagram'))==1
for d in parsed.findall('diagram'):
 cells=d.findall('.//mxCell');ids={c.attrib['id'] for c in cells}
 assert len(ids)==len(cells)
 for c in cells:
  if 'parent' in c.attrib:assert c.attrib['parent'] in ids
  if c.attrib.get('edge')=='1':assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in parsed.findall('.//mxCell'))
assert sorted(n['number'] for n in NODES.values() if n['kind']=='process')==['1.0','2.0','3.0','4.0','5.0','6.0']
client=[f for f in FLOWS if f['source'].startswith('client') or f['target'].startswith('client')]
assert len(client)==6 and all(f['planned'] for f in client)
assert {f['target'] for f in client if f['source'].startswith('client')}=={'p1','p4','p6'}
# The entire process backbone is connected, with no page continuation required.
assert {(f['source'],f['target']) for f in FLOWS if NODES[f['source']]['kind']=='process' and NODES[f['target']]['kind']=='process'}=={('p1','p2'),('p2','p3'),('p3','p4'),('p4','p5'),('p5','p6')}
report={'pages':1,'processes':6,'flows':len(FLOWS),'client_flows':6,'client_status':'Planned, read-only',
 'reference':'C:/Users/kupal/Downloads/reference.pdf','reference_pages_inspected':4,
 'flow_crossings':0,'flow_node_collisions':0,'flow_label_collisions':0,'label_label_collisions':0,'text_fit':'PASS','editable_xml':'PASS',
 'client_permissions':'PASS: sign-in, saved 2D/3D layout viewing, captured estimate viewing',
 'all_processes_connected':'PASS','process_inputs_and_outputs':'PASS','visual_review':'PENDING','editor_import':'NOT TESTED','downloads_copy':'PENDING'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'dfd-data.json').write_text(json.dumps([{k:v for k,v in p.items() if k!='svg'} for p in PAGES],indent=2),encoding='utf-8')
(OUT/'preview.html').write_text('<!doctype html><html><meta charset="utf-8"><title>VED compact DFD</title><style>body{margin:0;background:#eee}svg{display:block;max-width:1140px;width:100%;margin:auto;background:white}</style>'+PAGES[0]['svg']+'</html>',encoding='utf-8')
print(json.dumps(report,indent=2))
