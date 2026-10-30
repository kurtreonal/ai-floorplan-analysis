"""Repository-grounded DFD, with explicitly planned read-only Client flows."""
import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent / "reference-rebuild"
OUT.mkdir(exist_ok=True)
ROOT_PATH=OUT.parents[1]
W=1200
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
    text('Appendix Figure. '+('Data Flow Diagram' if not PAGES else 'Continuation'),40,20,W-80,32,18,True)
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
            text(label,x+12,y+31,w-24,h-39,13,False,'center',cid,x,y)
        else:text(label,x+10,y+8,w-20,h-16,13,False,'center',cid,x,y)
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
    text(caption,40,HEIGHT-90,W-80,35,17,False,'center')
    text('Client* is planned: sign-in, authorized saved 2D/3D layout viewing and captured estimate viewing only.',40,HEIGHT-48,W-80,22,12)
    text(str(len(PAGES)),40,HEIGHT-23,W-80,21,12,False,'center')
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
    node_items=list(NODES.items())
    for i,(nid,a) in enumerate(node_items):
        for other,b in node_items[i+1:]:
            assert not (a['x']<b['x']+b['w'] and a['x']+a['w']>b['x'] and a['y']<b['y']+b['h'] and a['y']+a['h']>b['y']),('Overlapping nodes',nid,other)
    for f in FLOWS:
        a,b=NODES[f['source']],NODES[f['target']]
        assert not (a['kind']=='entity' and b['kind']=='store')
        assert not (a['kind']=='store' and b['kind']=='entity')
        assert not (a['kind']=='store' and b['kind']=='store')
        if a['label'].startswith('Client'):
            assert b['number'] in {'1.0','3.0','5.0','3.2','5.3',''}
            assert f['planned']
    for nid,n in NODES.items():
        if n['kind']=='process':
            assert any(f['source']==nid for f in FLOWS) and any(f['target']==nid for f in FLOWS)
    SVG.append('</svg>');PAGES[-1].update(nodes=NODES,flows=FLOWS,svg=''.join(SVG))
    IMAGE.save(OUT/(filename+'.png'));(OUT/(filename+'.svg')).write_text(PAGES[-1]['svg'],encoding='utf-8')
    print(filename,len(NODES),'nodes',len(FLOWS),'flows',flush=True)

# Page 1 follows the reference's compact, staggered five-process overview.
begin('Level 1 - Overview',1120,'')
for cid,label,x,y,num in [
 ('p1','Access Management',480,130,'1.0'),
 ('p2','Floor Plan Analysis\nand Review',480,310,'2.0'),
 ('p3','2D / 3D Layout\nManagement',480,530,'3.0'),
 ('p4','Routing and\nMeasurements',480,800,'4.0'),
 ('p5','Materials and\nCost Estimation',820,530,'5.0')]:
 node(cid,'process',label,x,y,180,85,num)
node('users','entity','Admin / Designer /\nClient*',80,150,150,80)
node('oidc','entity','OAuth / OIDC\nProvider',820,235,160,60)
node('designer2','entity','Electrical Designer',250,305,130,70)
node('admin2','entity','Administrator',80,350,150,65)
node('designer3','entity','Electrical Designer',80,475,150,50)
node('client','entity','Client*',80,540,150,100,planned=True)
node('designer4','entity','Electrical Designer',80,755,150,70)
node('admin5','entity','Administrator',1000,335,155,65)
node('designer5','entity','Electrical Designer',820,920,170,60)
for cid,label,x,y,w,h,code in [
 ('s1','Users / roles',800,140,250,70,'D1'),
 ('s2','Projects / sources /\nanalysis / review',800,315,180,75,'D2'),
 ('s3','Canonical layouts',780,415,220,60,'D3'),
 ('s4','Saved route versions',80,875,210,60,'D4'),
 ('s5','Materials / prices /\nestimate snapshots',820,820,275,65,'D5')]:
 node(cid,'store',label,x,y,w,h,code)
node('k-out','connector','K',315,640,30,30)
node('k-in','connector','K',830,480,30,30)
node('r-out','connector','R',565,935,30,30)
node('r-in','connector','R',1050,475,30,30)
flow('users','p1',[(230,172),(330,172),(330,150),(480,150)],'Sign-in request',350,133,125,key='auth-in')
flow('p1','users',[(480,183),(360,183),(360,240),(160,240),(160,230)],'Session / access result',190,245,165,key='auth-out')
horizontal('p1','s1',160,'Identity updates')
horizontal('s1','p1',190,'Role / user records')
flow('p1','oidc',[(660,205),(720,205),(720,255),(820,255)],'Auth request',723,239,95,key='oidc-out')
flow('oidc','p1',[(820,279),(690,279),(690,210),(660,210)],'OIDC claims',704,263,95,key='oidc-in')
flow('p1','p2',[(560,215),(560,310)],'Designer access',581,253,160)
horizontal('designer2','p2',333,'Plan / review inputs',key='plan-in')
horizontal('p2','designer2',370,'Results',key='plan-out')
horizontal('p2','s2',335,'Source / review data')
horizontal('s2','p2',370,'Saved evidence')
flow('admin2','p2',[(230,380),(390,380),(390,385),(480,385)],'Legend updates',245,387,128,key='legend-in')
flow('p2','admin2',[(515,395),(515,440),(160,440),(160,415)],'Legend / status',280,424,150,key='legend-out')
flow('p2','p3',[(560,395),(560,530)],'Approved geometry',580,402,150,key='geometry')
flow('designer3','p3',[(230,495),(450,495),(450,540),(480,540)],'Edit / save request',260,478,160,key='layout-edit')
flow('p3','designer3',[(480,548),(430,548),(430,535),(230,535),(230,525)],'Saved layouts',265,519,140,key='layout-result')
horizontal('client','p3',560,'Layout view request',True,key='client-layout-in')
horizontal('p3','client',590,'Read-only 2D / 3D layout',True,key='client-layout-out')
flow('client','k-out',[(230,630),(330,630),(330,640)],'Estimate view request',245,608,170,True,key='client-cost-in')
flow('k-in','p5',[(845,510),(845,530)],'Estimate view request',870,493,170,True,key='client-cost-in')
flow('p3','s3',[(660,565),(690,565),(690,440),(780,440)],'Save layout',697,424,80)
flow('s3','p3',[(780,460),(720,460),(720,600),(660,600)],'Layout data',727,554,90)
flow('p3','p4',[(560,615),(560,800)],'Metric geometry',583,716,150)
flow('designer4','p4',[(230,785),(360,785),(360,830),(480,830)],'Routing inputs',245,769,125,key='route-in')
flow('p4','designer4',[(480,814),(380,814),(380,730),(160,730),(160,755)],'Routes / lengths',215,713,160,key='route-out')
flow('p4','s4',[(515,885),(515,955),(180,955),(180,935)],'Save measured routes',255,939,190)
flow('s4','p4',[(240,875),(240,850),(480,850)],'Saved routes',270,833,130)
flow('p4','r-out',[(580,885),(580,935)],'Route data',611,902,150,key='routing-handoff')
flow('r-in','p5',[(1065,505),(1065,545),(1000,545)],'Route data',1007,511,140,key='routing-handoff')
flow('admin5','p5',[(1110,400),(1110,560),(1000,560)],'Price updates',1008,439,95,key='price-in')
flow('p5','admin5',[(1000,578),(1185,578),(1185,380),(1155,380)],'Catalog / price status',1008,603,158,key='price-out')
flow('designer5','p5',[(880,920),(880,900),(800,900),(800,600),(820,600)],'Estimate request',824,891,140,key='estimate-in')
flow('p5','designer5',[(820,582),(770,582),(770,925),(820,925)],'Saved estimate',671,851,94,key='estimate-out')
flow('p5','s5',[(870,615),(870,820)],'Save prices\nand estimates',880,750,88)
flow('s5','p5',[(965,820),(965,615)],'Prices / snapshots',979,723,180)
flow('p5','client',[(1000,600),(1170,600),(1170,990),(50,990),(50,605),(80,605)],'Stored cost estimate',412,974,220,True,key='client-cost-out')
text('Matching K / R circles continue the same data flow without crossing another arrow.',300,1010,800,22,12)
end('01-level1','Data Flow Diagram Level 1 of VED Electrical Services')

# Page 2 mirrors the reference's full-page Level 2.1 access continuation.
begin('Continuation - Level 2.1 Access',850,'')
node('users','entity','Admin / Designer /\nClient*',100,230,180,80)
node('oidc','entity','OAuth / OIDC\nProvider',875,230,180,80)
node('a1','process','OIDC Sign-in',490,230,180,80,'1.1')
node('a2','process','Resolve Identity\nand Local Role',490,440,180,80,'1.2')
node('a3','process','Establish Authorized\nApplication Session',490,650,180,80,'1.3')
node('s1','store','Users / roles',850,450,240,65,'D1')
horizontal('users','a1',252,'Sign-in request',key='auth-in')
horizontal('a1','oidc',252,'Authorization request',key='oidc-out')
horizontal('oidc','a1',287,'Verified OIDC claims',key='oidc-in')
flow('a1','a2',[(580,310),(580,440)],'Verified external identity',605,357,230)
horizontal('a2','s1',470,'Identity record update')
horizontal('s1','a2',500,'Stored user / role')
flow('a2','a3',[(580,520),(580,650)],'VED identity and role',605,562,220)
flow('a3','users',[(490,690),(60,690),(60,350),(180,350),(180,310)],'Session / access result',250,673,200,key='auth-out')
end('02-access','Data Flow Diagram Level 2.1 of VED Electrical Services')

# Page 3 contains two compact continuation figures, as reference page 3 does.
begin('Continuation - Level 2.2 and 2.3',1300,'')
for cid,label,y,num in [('f1','Manage Project\nand Upload',145,'2.1'),('f2','Analyze Floor\nPlan Source',300,'2.2'),('f3','Review and\nCorrect Candidates',455,'2.3')]:
 node(cid,'process',label,430,y,180,75,num)
node('designer-a','entity','Electrical Designer',80,170,150,70)
node('admin','entity','Administrator',80,320,150,60)
node('designer-b','entity','Electrical Designer',80,470,150,65)
for cid,label,y in [('source','Projects / original\nsource files',155),('processing','Jobs / sources /\napproved legends',315),('review','Candidates / review\nrecords',470)]:
 node(cid,'store',label,820,y,240,65,'D2')
horizontal('designer-a','f1',175,'Project / plan input',key='plan-in')
flow('f1','designer-a',[(430,205),(340,205),(340,270),(130,270),(130,240)],'Project / upload status',165,254,165,key='plan-out-status')
horizontal('f1','source',175,'Validated source / metadata')
horizontal('source','f1',205,'Saved source records')
flow('f1','f2',[(520,220),(520,300)],'Source / page identifiers',542,244,220)
horizontal('admin','f2',335,'Approved legend updates',key='legend-in')
horizontal('f2','admin',365,'Legend / status',key='legend-out')
horizontal('f2','processing',332,'Source / job updates')
horizontal('processing','f2',363,'Originals / job records')
flow('f2','f3',[(520,375),(520,455)],'Advisory candidates',542,402,210)
horizontal('designer-b','f3',489,'Review / corrections',key='plan-in-review')
horizontal('f3','designer-b',518,'Candidates / review status',key='plan-out-candidates')
horizontal('f3','review',491,'Candidate / review updates')
horizontal('review','f3',522,'Saved evidence / review')
node('g-out','connector','G',505,565,30,30)
flow('f3','g-out',[(520,530),(520,565)],'Approved geometry',542,538,170,key='geometry')
text('Data Flow Diagram Level 2.2 of VED Electrical Services',40,613,1120,30,17,False,'center')
node('g-in','connector','G',505,665,30,30)
node('l1','process','Validate and Save\nCanonical Geometry',430,715,180,75,'3.1')
node('l2','process','Read Authorized\n2D / 3D Layout',820,925,180,75,'3.2')
node('designer-l','entity','Electrical Designer',80,740,150,70)
node('client-l','entity','Client*',80,970,150,70,planned=True)
node('layout','store','Canonical layouts',450,935,240,65,'D3')
flow('g-in','l1',[(520,695),(520,715)],'Approved geometry',542,690,170,key='geometry')
horizontal('designer-l','l1',755,'Edit / save request',key='layout-edit')
flow('l1','designer-l',[(430,780),(300,780),(300,835),(130,835),(130,810)],'Saved layouts',170,818,120,key='layout-result')
flow('l1','layout',[(510,790),(510,935)],'Canonical snapshot',531,857,200)
node('l-out','connector','L',705,880,30,30)
flow('l1','l-out',[(610,760),(720,760),(720,880)],'Metric geometry',737,810,150,key='metric-handoff')
horizontal('l2','layout',955,'Version selection')
horizontal('layout','l2',982,'Saved geometry')
flow('client-l','l2',[(130,1040),(130,1100),(900,1100),(900,1000)],'Layout view request',390,1084,180,True,key='client-layout-in')
flow('l2','client-l',[(1000,980),(1120,980),(1120,1125),(70,1125),(70,1010),(80,1010)],'Read-only 2D / 3D layout',410,1109,260,True,key='client-layout-out')
text('G carries the approved geometry from Level 2.2 to Level 2.3.',300,1160,800,22,12)
end('03-analysis-layout','Data Flow Diagram Level 2.3 of VED Electrical Services')

# Page 4 repeats the reference's two-figure routing / estimate continuation.
begin('Continuation - Level 2.4 and 2.5',1380,'')
for cid,label,x,y,num in [('r1','Retrieve Canonical\nMetric Geometry',430,150,'4.1'),('r2','Generate Electrical\nRoute Points',430,310,'4.2'),('r3','Measure and Save\nRoute Version',820,450,'4.3')]:
 node(cid,'process',label,x,y,180,85 if cid=='r3' else 75,num)
node('designer-r','entity','Electrical Designer',80,170,150,70)
node('layout-r','store','Canonical layouts',820,155,240,65,'D3')
node('routes','store','Saved route versions',430,470,240,70,'D4')
node('l-in','connector','L',505,90,30,30)
flow('l-in','r1',[(520,120),(520,150)],'Metric geometry',542,125,160,key='metric-handoff')
horizontal('designer-r','r1',175,'Routing inputs',key='route-in')
horizontal('r1','layout-r',175,'Layout version selection')
horizontal('layout-r','r1',205,'Saved metric geometry')
flow('r1','r2',[(520,225),(520,310)],'Geometry / route settings',542,251,230)
flow('r2','r3',[(610,350),(700,350),(700,470),(820,470)],'Route points',720,453,95)
horizontal('r3','routes',493,'Route snapshot')
horizontal('routes','r3',523,'Saved lengths')
flow('r3','designer-r',[(1000,490),(1120,490),(1120,580),(50,580),(50,210),(80,210)],'Routes / lengths',355,564,180,key='route-out')
node('r-out','connector','R',1055,400,30,30)
flow('r3','r-out',[(1000,460),(1070,460),(1070,430)],'Route data',1007,436,90,key='routing-handoff')
text('Data Flow Diagram Level 2.4 of VED Electrical Services',40,613,1120,30,17,False,'center')
node('e1','process','Manage Material\nCatalog and Prices',430,715,180,75,'5.1')
node('e2','process','Calculate and Save\nCaptured-Price Estimate',430,925,180,80,'5.2')
node('e3','process','Read Authorized\nCost Estimate',820,1110,180,80,'5.3')
node('admin-e','entity','Administrator',80,740,150,70)
node('designer-e','entity','Electrical Designer',80,935,150,70)
node('client-e','entity','Client*',80,1100,150,70,planned=True)
node('prices','store','Materials / prices',820,730,250,65,'D5')
node('estimate','store','Estimate snapshots /\ncaptured prices',430,1130,240,65,'D5')
node('layout-e','store','Canonical layout\nversions',820,925,250,80,'D3')
node('r-in','connector','R',600,840,30,30)
horizontal('admin-e','e1',755,'Price updates',key='price-in')
horizontal('e1','admin-e',785,'Catalog / price status',key='price-out')
horizontal('e1','prices',755,'Catalog / price revisions')
horizontal('prices','e1',785,'Stored material prices')
flow('e1','e2',[(520,790),(520,925)],'Stored prices',542,801,120)
flow('r-in','e2',[(615,870),(615,900),(585,900),(585,925)],'Route data',633,883,100,key='routing-handoff')
horizontal('designer-e','e2',955,'Estimate request',key='estimate-in')
horizontal('e2','designer-e',990,'Saved estimate',key='estimate-out')
horizontal('e2','layout-e',951,'Layout version selection')
horizontal('layout-e','e2',990,'Verified geometry / quantities')
flow('e2','estimate',[(520,1005),(520,1130)],'Captured estimate items',542,1052,210)
horizontal('e3','estimate',1135,'Estimate selection')
horizontal('estimate','e3',1175,'Stored captured costs')
flow('client-e','e3',[(230,1130),(300,1130),(300,1225),(900,1225),(900,1190)],'Estimate view request',390,1209,220,True,key='client-cost-in')
flow('e3','client-e',[(1000,1170),(1120,1170),(1120,1255),(70,1255),(70,1145),(80,1145)],'Stored cost estimate',405,1239,220,True,key='client-cost-out')
text('R continues the measured routing data from Level 2.4 to Level 2.5.',300,1273,800,22,12)
end('04-routing-cost','Data Flow Diagram Level 2.5 of VED Electrical Services')

# Native editable output; previews are generated from the identical node/flow geometry.
FILE=OUT/'ved-data-flow-diagram-2026-10-12.drawio'
ET.indent(MX)
ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE)
assert len(parsed.findall('diagram'))==4
for diagram in parsed.findall('diagram'):
    cells=diagram.findall('.//mxCell');ids={c.attrib['id'] for c in cells}
    assert len(ids)==len(cells)
    for c in cells:
        assert c.attrib.get('parent','0') in ids
        if c.attrib.get('edge')=='1':
            assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in parsed.findall('.//mxCell'))
assert sorted(n['number'] for n in PAGES[0]['nodes'].values() if n['kind']=='process')==['1.0','2.0','3.0','4.0','5.0']
assert sorted(n['number'] for p in PAGES[1:] for n in p['nodes'].values() if n['kind']=='process')==['1.1','1.2','1.3','2.1','2.2','2.3','3.1','3.2','4.1','4.2','4.3','5.1','5.2','5.3']

# Each matching letter is an actual paired data handoff, with the same payload label.
continuation_pairs=[(0,'k-out',0,'k-in'),(0,'r-out',0,'r-in'),(2,'g-out',2,'g-in'),(2,'l-out',3,'l-in'),(3,'r-out',3,'r-in')]
for pi,a,pj,b in continuation_pairs:
    outgoing=next(f for f in PAGES[pi]['flows'] if f['target']==a)
    incoming=next(f for f in PAGES[pj]['flows'] if f['source']==b)
    assert outgoing['label']==incoming['label'] and outgoing['key']==incoming['key']

# Client view requests reach only the authorized layout/estimate reading paths.
for p in PAGES:
    for f in p['flows']:
        if p['nodes'][f['source']]['label'].startswith('Client'):
            assert f['planned']
            target=p['nodes'][f['target']]
            assert target['number'] in {'3.0','3.2','5.3',''}
            if target['kind']=='connector':assert f['key']=='client-cost-in'
    for n in p['nodes'].values():
        if n['label'].startswith('Admin / Designer /'):assert 'Client*' in n['label']
assert sum(f['key']=='client-layout-in' for f in PAGES[0]['flows'])==1
assert sum(f['key']=='client-layout-out' for f in PAGES[0]['flows'])==1
assert sum(f['key']=='client-cost-in' for f in PAGES[0]['flows'])==2
assert sum(f['key']=='client-cost-out' for f in PAGES[0]['flows'])==1
for key in ['client-layout-in','client-layout-out','client-cost-in','client-cost-out']:
    parent=next(f for f in PAGES[0]['flows'] if f['key']==key)
    child=next(f for p in PAGES[1:] for f in p['flows'] if f['key']==key)
    assert parent['label']==child['label']
for key in ['auth-in','auth-out','oidc-in','oidc-out','legend-in','legend-out','layout-edit','layout-result','route-in','route-out','price-in','price-out','estimate-in','estimate-out']:
    assert any(f['key']==key for f in PAGES[0]['flows'])
    assert any(f['key']==key for p in PAGES[1:] for f in p['flows'])

preview=['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED reference-style DFD</title><style>body{margin:0;background:#ddd;font-family:Arial}nav{background:white;padding:14px;position:sticky;top:0}nav a{margin-right:18px}section{max-width:1200px;background:white;margin:20px auto}svg{display:block;width:100%}@media print{nav{display:none}section{break-after:page;margin:0}@page{size:A3 portrait;margin:6mm}}</style><nav>']
for i,p in enumerate(PAGES,1):preview.append(f'<a href="#page-{i}">{html.escape(p["name"])}</a>')
preview.append('</nav>')
for i,p in enumerate(PAGES,1):preview.append(f'<section id="page-{i}">{p["svg"]}</section>')
preview.append('</html>')
(OUT/'preview.html').write_text('\n'.join(preview),encoding='utf-8')
(OUT/'dfd-data.json').write_text(json.dumps([{k:v for k,v in p.items() if k!='svg'} for p in PAGES],indent=2),encoding='utf-8')
report={'pages':4,'overview_processes':5,'level2_processes':14,'source_reference':'C:/Users/kupal/Downloads/reference.pdf',
 'reference_pages_inspected':4,'planned_client':'Sign-in; authorized saved 2D/3D layouts; captured estimate viewing only',
 'client_restrictions':'PASS','client_request_response_balance':'PASS','all_five_overview_processes_expanded':'PASS','continuation_pair_balance':'PASS',
 'flow_crossings':0,'flow_node_collisions':0,'flow_label_collisions':0,'label_label_collisions':0,'node_node_collisions':0,
 'text_fit':'PASS','editable_xml':'PASS','process_inputs_outputs':'PASS','entity_store_separation':'PASS',
 'orthogonal_perimeter_routing':'PASS','visual_review':'PENDING','editor_import':'NOT TESTED','downloads_copy':'PENDING'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
