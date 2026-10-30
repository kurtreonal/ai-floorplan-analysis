"""Repository-grounded DFD, with explicitly planned read-only Client flows."""
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
ROOT_PATH=OUT.parents[1]
W=1700
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
    text('VED ELECTRICAL SERVICES',40,20,W-80,30,18,True)
    text(name,40,58,W-80,44,28,True)
    text(subtitle,40,109,W-80,30,15)
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
        text(number,x+3,y+10,48,h-20,15,True,'center',cid,x,y)
        text(label,x+62,y+10,w-70,h-20,15,False,'center',cid,x,y)
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
            line([(x,y+35),(x+w,y+35)])
            cell('',x,y+35,w,1,'fillColor=#000000;strokeColor=none;',cid,x,y)
            text(number,x,y+4,w,27,18,False,'center',cid,x,y)
            text(label,x+12,y+47,w-24,h-59,19,False,'center',cid,x,y)
        else:text(label,x+10,y+8,w-20,h-16,17,False,'center',cid,x,y)
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
    label_lines=wrapped(label,lw-8,14)
    label_width=math.ceil(max(font(14).getlength(s) for s in label_lines))+8
    if center_label:lx+=(lw-label_width)/2
    lh=len(label_lines)*18+4
    text(label,lx,ly,label_width,lh,14,fill=True)
    FLOWS.append({'id':fid,'source':s,'target':t,'label':label,'points':points,'planned':dash,'key':key})
    LABELS.append((fid,(lx,ly,label_width,lh)))
def horizontal(s,t,y,label,dash=False,reverse=False,key=None):
    a,b=NODES[s],NODES[t]
    if a['x']<b['x']:x1=a['x']+a['w'];x2=b['x']
    else:x1=a['x'];x2=b['x']+b['w']
    left=min(x1,x2);width=abs(x2-x1)-28
    lines=len(wrapped(label,width-8,14));lh=lines*18+4
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
    text(caption,40,HEIGHT-115,W-80,38,17,True,'center')
    text('Dashed Client flows are planned. Client access is limited to sign-in and authorized saved layout / estimate viewing.',40,HEIGHT-72,W-80,27,14)
    text('Reference style: REFERENCES.pdf | Same entity/store code denotes the same entity/store across pages.',40,HEIGHT-40,W-80,25,13)
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

# Context: one whole-system process; no internal data stores.
begin('Context Diagram - Level 0',1140,'Current VED workflow with the requested, future Client role')
node('system','process','VED Electrical Services\nAI Floor Plan Analysis,\n2D/3D Layout and\nCost Estimation System',600,180,430,810,'0.0')
node('admin','entity','Administrator',50,235,250,125)
node('designer','entity','Electrical Designer',50,440,250,225)
node('client','entity','Client\n(planned, read-only)',50,735,250,230,planned=True)
node('oidc','entity','OAuth / OIDC\nIdentity Provider',1240,485,280,145)
horizontal('admin','system',260,'Sign-in / catalog / authority / inspection requests',key='admin-in')
horizontal('system','admin',330,'Access / catalog / authority / inspection results',key='admin-out')
horizontal('designer','system',470,'Sign-in / project details / original plan data',key='designer-in-a')
horizontal('system','designer',520,'Access / project / analysis status',key='designer-out-a')
horizontal('designer','system',580,'Review / layout / routing / estimate inputs',key='designer-in-b')
horizontal('system','designer',635,'Proposals / saved layouts / routes / estimates',key='designer-out-b')
for a,b,y,label,key in [('client','system',760,'Sign-in request','client-auth-in'),('system','client',800,'Access result / session','client-auth-out'),('client','system',840,'Saved 2D/3D layout view request','client-layout-in'),('system','client',880,'Authorized saved 2D/3D layouts','client-layout-out'),('client','system',920,'Stored estimate view request','client-cost-in'),('system','client',955,'Authorized captured cost estimate','client-cost-out')]:horizontal(a,b,y,label,True,key=key)
horizontal('system','oidc',520,'OAuth/OIDC authorization request',key='oidc-in')
horizontal('oidc','system',580,'Verified external identity claims',key='oidc-out')
end('dfd-context','Context diagram of VED Electrical Services')

# Level 1A: platform, original input and advisory evidence.
begin('Data Flow Diagram - Level 1, Part A',1820,'1.0 Access | 2.0 Projects and originals | 3.0 Analysis and Designer review')
node('p1','process','Authenticate and\nauthorize access',750,190,390,420,'1.0')
node('p2','process','Manage projects\nand floor plan input',750,720,390,300,'2.0')
node('p3','process','Analyze floor plans\nand review proposals',750,1160,390,480,'3.0')
for nid,label,x,y,w,h in [('a1','Administrator',60,208,190,115),('d1','Electrical Designer',60,350,190,88),('c1','Client (planned)',60,486,190,98),('provider','OAuth/OIDC Provider',1400,225,240,110),('d2','Electrical Designer',60,754,190,95),('a2','Administrator',60,920,190,75),('d3','Electrical Designer',60,1270,190,105),('a3','Administrator',60,1490,190,92)]:node(nid,'entity',label,x,y,w,h,planned=nid=='c1')
node('store1','store','Identity and\naccess records',1400,465,240,100,'D1')
node('store2','store','Project / floor /\nsource metadata',1400,740,240,115,'D2')
node('store3a','store','Unchanged\noriginal files',1400,900,240,100,'D3')
node('store4','store','Processing / review /\nlegend records',1400,1200,240,140,'D4')
node('store3b','store','Unchanged\noriginal files',1400,1440,240,115,'D3')
node('geometry-out','connector','G',925,1660,40,40)
for a,b,y,label,dash in [('a1','p1',226,'Sign-in request',False),('p1','a1',250,'Access result / session',False),('a1','p1',278,'Dataset approver authority update',False),('p1','a1',304,'Authority assignment status',False),('d1','p1',370,'Sign-in request',False),('p1','d1',416,'Access result / session',False),('c1','p1',516,'Sign-in request',True),('p1','c1',566,'Access result / read-only scope',True),('p1','provider',252,'Authorization request',False),('provider','p1',302,'Verified identity claims',False),('p1','store1',495,'Identity / authority updates',False),('store1','p1',540,'User / role / access records',False),('d2','p2',780,'Project/floor details and original plan',False),('p2','d2',825,'Project IDs / upload validation status',False),('a2','p2',940,'Project inspection request',False),('p2','a2',976,'Project / floor metadata',False),('p2','store2',768,'Project / source metadata',False),('store2','p2',817,'Saved project / source records',False),('p2','store3a',925,'Validated original file bytes',False),('store3a','p2',974,'Original identity / storage result',False),('d3','p3',1300,'Analysis options / review corrections',False),('p3','d3',1346,'Candidates / job status / review version',False),('a3','p3',1514,'Approved symbol legend changes',False),('p3','a3',1564,'Legend catalog / update status',False),('p3','store4',1237,'Job / candidate / review records',False),('store4','p3',1298,'Saved evidence / approved legends',False),('p3','store3b',1474,'Selected source / page identifiers',False),('store3b','p3',1534,'Original source page data',False)]:horizontal(a,b,y,label,dash)
flow('p2','p3',[(945,1020),(945,1160)],'Source/page IDs and processing request',970,1070,370)
flow('p3','geometry-out',[(945,1640),(945,1660)],'Designer-approved geometry and scale',990,1646,400,key='geometry-handoff-out')
end('dfd-level1-a','Level 1, Part A - continuation G connects to Part B, process 4.0')

# Level 1B: one shared canonical source and authoritative estimate snapshots.
begin('Data Flow Diagram - Level 1, Part B',1780,'4.0 Saved 2D/3D layouts | 5.0 Electrical routes | 6.0 Materials and estimates')
node('geometry-in','connector','G',925,160,40,40)
node('p4','process','Build and serve\nsaved 2D/3D layouts',750,230,390,330,'4.0')
node('p5','process','Calculate and\npersist electrical routes',750,730,390,290,'5.0')
node('p6','process','Manage materials and\ncalculate / serve estimates',750,1150,390,460,'6.0')
for nid,label,y,h in [('d4','Electrical Designer',270,110),('c4','Client (planned)',435,95),('d5','Electrical Designer',785,120),('d6','Electrical Designer',1190,115),('c6','Client (planned)',1360,95),('a6','Administrator',1510,90)]:node(nid,'entity',label,60,y,190,h,planned=nid.startswith('c'))
node('store5a','store','Canonical layouts\nand route versions',1400,266,240,125,'D5')
node('store5b','store','Canonical layouts\nand route versions',1400,796,240,135,'D5')
node('store6','store','Materials / prices /\nestimate snapshots',1400,1190,240,150,'D6')
node('store5c','store','Canonical layouts\nand route versions',1400,1460,240,135,'D5')
flow('geometry-in','p4',[(945,200),(945,230)],'Designer-approved geometry and scale',990,175,400,key='geometry-handoff-in')
for a,b,y,label,dash in [('d4','p4',298,'Layout edits / conditional save / view request',False),('p4','d4',355,'Saved 2D/3D layouts / layout version',False),('c4','p4',456,'Saved 2D/3D layout view request',True),('p4','c4',503,'Authorized saved 2D/3D layouts',True),('p4','store5a',300,'Canonical layout snapshot',False),('store5a','p4',360,'Saved geometry / version',False),('d5','p5',814,'Panel / obstacles / routing specifications',False),('p5','d5',875,'Route points / horizontal and vertical lengths',False),('p5','store5b',830,'Measured route version',False),('store5b','p5',888,'Saved geometry / routes',False),('d6','p6',1218,'Estimate request / explicit material mappings',False),('p6','d6',1274,'Stored estimate / captured unit prices and totals',False),('c6','p6',1385,'Stored estimate view request',True),('p6','c6',1428,'Authorized captured cost estimate',True),('a6','p6',1534,'Material catalog / price import selection',False),('p6','a6',1580,'Catalog / price revision status',False),('p6','store6',1228,'Price / estimate snapshots',False),('store6','p6',1294,'Prices / stored estimates',False),('p6','store5c',1494,'Layout / route version selectors',False),('store5c','p6',1554,'Verified symbols / measured routes',False)]:horizontal(a,b,y,label,dash)
flow('p4','p5',[(945,560),(945,730)],'Current layout version and metric geometry',975,635,430)
flow('p5','p6',[(945,1020),(945,1150)],'Measured route lengths and source versions',975,1066,430)
end('dfd-level1-b','Level 1, Part B - Client retrieves saved data; Designer creates or modifies it')

# A focused level-2 view makes the future Client restrictions unambiguous.
begin('Client Read-only Access - Level 2 Detail',1120,'Planned extension of 4.0 and the retrieval branch of 6.0; sign-in is handled by 1.0')
node('client-detail','entity','Client\nAuthenticated read-only session',780,220,340,100,planned=True)
for nid,label,x,y,num in [('l1','Authorize project-scoped\nlayout access',150,390,'4.1'),('l2','Retrieve saved\ncanonical snapshot',150,650,'4.2'),('l3','Present read-only\n2D / 3D layout',150,870,'4.3'),('e1','Authorize project-scoped\nestimate access',1050,390,'6.1'),('e2','Retrieve stored estimate\nand captured prices',1050,650,'6.2'),('e3','Present read-only\ncost estimate',1050,870,'6.3')]:node(nid,'process',label,x,y,300,112,num,True)
node('access-left','store','Identity / client\nproject scope*',560,380,240,120,'D1')
node('access-right','store','Identity / client\nproject scope*',1460,380,220,120,'D1')
node('layouts','store','Saved canonical\nlayout versions',560,640,240,120,'D5')
node('costs','store','Stored estimates /\ncaptured unit prices',1460,640,220,120,'D6')
flow('client-detail','l1',[(780,280),(300,280),(300,390)],'Saved layout view request and session',360,262,370,True)
flow('client-detail','e1',[(1120,280),(1200,280),(1200,390)],'Stored estimate view request and session',1230,302,420,True)
for a,b,y,label in [('l1','access-left',417,'Scope check'),('access-left','l1',466,'Access decision'),('l2','layouts',674,'Version IDs'),('layouts','l2',720,'Saved geometry'),('e1','access-right',417,'Scope check'),('access-right','e1',466,'Access decision'),('e2','costs',674,'Estimate ID'),('costs','e2',720,'Captured costs')]:horizontal(a,b,y,label,True)
flow('l1','l2',[(300,502),(300,650)],'Authorized project and floor selectors',320,545,300,True)
flow('l2','l3',[(300,762),(300,870)],'Saved geometry and version',320,794,270,True)
flow('e1','e2',[(1200,502),(1200,650)],'Authorized project and estimate selectors',1220,545,390,True)
flow('e2','e3',[(1200,762),(1200,870)],'Stored items and captured totals',1220,794,390,True)
flow('l3','client-detail',[(150,932),(60,932),(60,164),(850,164),(850,220)],'Authorized saved 2D/3D layouts',250,148,330,True)
flow('e3','client-detail',[(1350,932),(1690,932),(1690,174),(1080,174),(1080,220)],'Authorized captured cost estimate',1210,158,360,True)
end('dfd-client-detail','* Client-to-project authorization policy and CLIENT role support require future implementation')

FILE=OUT/'ved-data-flow-diagram-2026-10-12.drawio'
ET.indent(MX);ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE);assert len(parsed.findall('diagram'))==4
for d in parsed.findall('diagram'):
    cells=d.findall('.//mxCell');ids={c.attrib['id'] for c in cells}
    assert len(ids)==len(cells)
    for c in cells:
        if 'parent' in c.attrib:assert c.attrib['parent'] in ids
        if c.attrib.get('edge')=='1':assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in parsed.findall('.//mxCell'))
level1_processes=[n['number'] for p in PAGES[1:3] for n in p['nodes'].values() if n['kind']=='process']
assert sorted(level1_processes)==['1.0','2.0','3.0','4.0','5.0','6.0']
client_level1=[f for p in PAGES[1:3] for f in p['flows'] if p['nodes'][f['source']]['label'].startswith('Client') or p['nodes'][f['target']]['label'].startswith('Client')]
assert len(client_level1)==6 and all(f['planned'] for f in client_level1)
assert [f['label'] for f in client_level1]==['Sign-in request','Access result / read-only scope','Saved 2D/3D layout view request','Authorized saved 2D/3D layouts','Stored estimate view request','Authorized captured cost estimate']
handoff_out=next(f for f in PAGES[1]['flows'] if f['key']=='geometry-handoff-out')
handoff_in=next(f for f in PAGES[2]['flows'] if f['key']=='geometry-handoff-in')
assert handoff_out['label']==handoff_in['label']
preview=['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED data flow diagrams</title><style>body{margin:0;background:#e5e5e5;font-family:Arial}nav{padding:16px;background:white;position:sticky;top:0}nav a{margin-right:20px;color:#333}section{max-width:1700px;margin:20px auto;background:white}svg{width:100%;display:block}@media print{nav{display:none}section{margin:0;break-after:page}@page{size:A3 portrait;margin:6mm}}</style><nav><strong>VED data flow diagrams</strong><br>']
for i,p in enumerate(PAGES,1):preview.append(f'<a href="#page-{i}">{html.escape(p["name"])}</a>')
preview.append('</nav>')
for i,p in enumerate(PAGES,1):preview.append(f'<section id="page-{i}">{p["svg"]}</section>')
preview.append('</html>');(OUT/'dfd-preview.html').write_text('\n'.join(preview),encoding='utf-8')
report={'pages':4,'level1_processes':6,'level1_client_flows':6,'client_permissions':'Sign-in; read authorized saved 2D/3D layouts; read captured estimates only',
        'client_status':'Planned, not implemented','client_restrictions':'PASS','data_store_entity_separation':'PASS','process_inputs_and_outputs':'PASS','geometry_continuation_balance':'PASS',
        'flow_crossings':0,'flow_node_collisions':0,'flow_label_collisions':0,'text_fit':'PASS','editable_xml':'PASS','preview_visual_review':'PENDING','editor_import':'NOT TESTED','downloads_copy':'PENDING'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'dfd-data.json').write_text(json.dumps([{k:v for k,v in p.items() if k!='svg'} for p in PAGES],indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
