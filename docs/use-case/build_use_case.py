"""Build a monochrome, editable use-case/module overview from the user's references."""
from pathlib import Path
import hashlib
import html
import json
import math
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H = 1820, 2770
STEM = 'ved-use-case-diagram-2026-10-21'
MX = ET.Element('mxfile', host='app.diagrams.net', type='device')
PAGE = ET.SubElement(MX, 'diagram', id='ved-use-case', name='Use Case Diagram')
MODEL = ET.SubElement(PAGE, 'mxGraphModel', page='1', pageScale='1', pageWidth=str(W), pageHeight=str(H), grid='1', gridSize='10', background='#FFFFFF')
ROOT = ET.SubElement(MODEL, 'root')
ET.SubElement(ROOT, 'mxCell', id='0')
ET.SubElement(ROOT, 'mxCell', id='1', parent='0')
IM = Image.new('RGB', (W, H), 'white')
DRAW = ImageDraw.Draw(IM)
SVG = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="white"/>']
NODES, EDGES, FONTS, TEXT = {}, [], {}, []
SEQ = 0


def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if bold else 'arial.ttf'), size)
    return FONTS[key]


def vertex(cid, value, x, y, w, h, style, parent='1'):
    c = ET.SubElement(ROOT, 'mxCell', id=cid, value=value, vertex='1', parent=parent, style=style)
    ET.SubElement(c, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), attrib={'as':'geometry'})
    return c


def new_id():
    global SEQ
    SEQ += 1
    return f'c{SEQ}'


def text(value, x, y, w, h, size=24, bold=False, cid=None, parent='1', local=None):
    lines = []
    for para in value.split('\n'):
        line = ''
        for word in para.split():
            test = (line+' '+word).strip()
            if line and font(size, bold).getlength(test)>w-8:
                lines.append(line)
                line=word
            else:
                line=test
        lines.append(line)
    assert len(lines)*(size+5)<=h, ('Text overflow',value,lines,h)
    assert all(font(size,bold).getlength(s)<=w-8 for s in lines)
    assert x>=0 and y>=0 and x+w<=W and y+h<=H
    xx,yy = local if local else (x,y)
    vertex(cid or new_id(), '\n'.join(lines), xx,yy,w,h,
            f'text;html=0;whiteSpace=wrap;fillColor=none;strokeColor=none;fontColor=#000000;fontFamily=Arial;fontSize={size};fontStyle={int(bold)};align=center;verticalAlign=middle;spacing=0;',parent)
    ty = y+(h-len(lines)*(size+5))/2
    for line in lines:
        tx=x+(w-font(size,bold).getlength(line))/2
        DRAW.text((tx,ty),line,font=font(size,bold),fill='black')
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}">{html.escape(line)}</text>')
        ty+=size+5
    TEXT.append({'text':value,'font':size,'rect':[x,y,w,h]})


def primitive(cid, x,y,w,h,kind='rect',fill='white',parent='1',local=None):
    xx,yy=local if local else (x,y)
    style={'rect':'rounded=0;','round':'rounded=1;arcSize=30;','ellipse':'ellipse;'}[kind]
    vertex(cid,'',xx,yy,w,h,style+f'fillColor={"#000000" if fill=="black" else "#FFFFFF"};strokeColor=#000000;strokeWidth=1.5;',parent)
    if kind=='ellipse':
        DRAW.ellipse((x,y,x+w,y+h),fill=fill,outline='black',width=2)
        SVG.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="black" stroke-width="1.5"/>')
    else:
        r=min(w,h)*.2 if kind=='round' else 0
        DRAW.rounded_rectangle((x,y,x+w,y+h),radius=r,fill=fill,outline='black',width=2)
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="black" stroke-width="1.5"/>')


def oval(cid,label,x,y,w,h,kind='case'):
    vertex(cid,'',x,y,w,h,'group;')
    primitive(new_id(),x,y,w,h,'ellipse',parent=cid,local=(0,0))
    text(label,x+22,y+8,w-44,h-16,24,kind=='module',parent=cid,local=(22,8))
    NODES[cid]={'label':label,'x':x,'y':y,'w':w,'h':h,'kind':kind}


def silhouette(cid,label,x,y):
    # Full-body human pictogram, made entirely from editable vector primitives.
    vertex(cid,'',x,y,180,275,'group;')
    NODES[cid]={'label':label,'x':x,'y':y,'w':180,'h':275,'kind':'actor'}
    for dx,dy,w,h,kind in [(69,0,42,42,'ellipse'),(54,52,72,87,'round'),(38,58,17,88,'round'),(125,58,17,88,'round'),(57,127,27,72,'round'),(96,127,27,72,'round')]:
        primitive(new_id(),x+dx,y+dy,w,h,kind,'black',cid,(dx,dy))
    text(label,x-15,y+205,210,65,23,True,parent=cid,local=(-15,205))


def edge(cid,source,target,points,kind='association'):
    a,b=NODES[source],NODES[target]
    p,q=points[0],points[-1]
    style='edgeStyle=none;rounded=0;html=0;endArrow=none;startArrow=none;strokeColor=#000000;strokeWidth=1.5;'
    if kind!='association':style+='dashed=1;dashPattern=5 4;'
    if kind in ('include','extend'):style+='endArrow=open;endSize=9;endFill=0;'
    style+=f'exitX={(p[0]-a["x"])/a["w"]};exitY={(p[1]-a["y"])/a["h"]};entryX={(q[0]-b["x"])/b["w"]};entryY={(q[1]-b["y"])/b["h"]};exitPerimeter=0;entryPerimeter=0;'
    c=ET.SubElement(ROOT,'mxCell',id=cid,value='',edge='1',parent='1',source=source,target=target,style=style)
    g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
    array=ET.SubElement(g,'Array',attrib={'as':'points'})
    for xx,yy in points[1:-1]:ET.SubElement(array,'mxPoint',x=str(xx),y=str(yy))
    SVG.append('<path d="'+' '.join(('M' if i==0 else 'L')+f' {xx} {yy}' for i,(xx,yy) in enumerate(points))+'" fill="none" stroke="black" stroke-width="1.5"'+(' stroke-dasharray="5 4"' if kind!='association' else '')+'/>')
    for p,q in zip(points,points[1:]):
        if kind=='association':DRAW.line((p,q),fill='black',width=2)
        else:
            length=math.dist(p,q)
            for t in range(0,math.ceil(length),9):
                end=min(t+5,length)
                DRAW.line((p[0]+(q[0]-p[0])*t/length,p[1]+(q[1]-p[1])*t/length,p[0]+(q[0]-p[0])*end/length,p[1]+(q[1]-p[1])*end/length),fill='black',width=2)
    if kind in ('include','extend'):
        p,q=points[-2:]
        length=math.dist(p,q)
        ux,uy=(q[0]-p[0])/length,(q[1]-p[1])/length
        wing=[(q[0]-10*ux+5*uy,q[1]-10*uy-5*ux),q,(q[0]-10*ux-5*uy,q[1]-10*uy+5*ux)]
        DRAW.line(wing,fill='black',width=2)
        SVG.append('<polyline points="'+' '.join(f'{xx},{yy}' for xx,yy in wing)+'" fill="none" stroke="black" stroke-width="1.5"/>')
    EDGES.append({'id':cid,'source':source,'target':target,'points':points,'kind':kind})


text('USE CASE DIAGRAM',30,20,650,50,32,True)
primitive('system-boundary',280,105,1290,2445)
text('VED ELECTRICAL SERVICES',310,120,1230,40,28,True)
text('AI-Driven Floor Plan Analysis and 3D Visualization\nfor Automated Layout and Cost Estimation',310,162,1230,64,24)
text('MODULES',330,244,380,40,24,True)
text('USE CASES',980,244,410,40,24,True)

silhouette('admin','ADMINISTRATOR',45,640)
silhouette('designer','DESIGNER',1620,1210)
silhouette('client','CLIENT*',1620,2140)

GROUPS=[
 ('access','USER AND ACCESS\nMANAGEMENT MODULE',420,[
  ('sign-in','Sign in',330,['A','D','C']),
  ('users','Admin: manage users\nand roles*',420,['A']),
  ('approvers','Admin: assign / revoke\ndataset approver',510,['A'])]),
 ('project','PROJECT, FLOOR PLAN\nAND VISUALIZATION\nMODULE',900,[
  ('inspect','Admin: inspect all\nproject records',660,['A']),
  ('projects','Create / manage\nown projects',750,['D']),
  ('upload','Upload floor plan',840,['D']),
  ('validate-upload','Validate uploaded\nfloor-plan file',960,[]),
  ('edit-layout','Open, edit and\nsave layout',1050,['D']),
  ('view-layout','View 2D / 3D layout',1140,['D','C'])]),
 ('ai','AI ANALYSIS AND\nDETECTION MODULE',1470,[
  ('dataset','Admin: manage legends\nand datasets*',1320,['A']),
  ('analyze','Analyze floor plan\nwith AI / CV',1410,['D']),
  ('review','Review / confirm\nAI results',1500,['D']),
  ('correct','Correct detection\nresults',1620,['D'])]),
 ('cost','ELECTRICAL ROUTING,\nCOST ESTIMATION AND\nREPORTING MODULE',2130,[
  ('prices','Admin: import / update\nmaterial prices',1800,['A']),
  ('routes','Configure / calculate\nelectrical routes',1890,['D']),
  ('draft-bom','Preview draft BOM /\nprovisional costs',1980,['D']),
  ('estimate','Generate saved\ncost estimate',2100,['D']),
  ('calculate','Calculate quantities /\ncapture prices and totals',2220,[]),
  ('view-cost','View saved\ncost estimate',2340,['A','D','C']),
  ('export','Export estimate /\nBOM as CSV',2460,['A','D'])])]

# Module links show decomposition, not mandatory execution or data flow.
# Admin uses the four module-level associations requested by the user.
# Designer and planned Client use direct, uninterrupted case associations.
ASSOCIATIONS=[]
for mid,label,cy,cases in GROUPS:
    oval(mid,label,330,cy-95,380,190,'module')
    for index,(cid,label,yy,roles) in enumerate(cases):
        oval(cid,label,1000,yy-40,370,80)
        # Separate fan endpoints preserve readable outlines and do not merge lines.
        ry=cy-30+60*index/max(1,len(cases)-1)
        rx=520+190*math.sqrt(1-((ry-cy)/95)**2)
        edge(f'module-{cid}',mid,cid,[(rx,ry),(1000,yy)],'module-membership')
        for role in roles:
            ASSOCIATIONS.append({'actor':role,'use_case':cid})

# The Designer's direct lines fan out beside the use-case column, as in ref.pdf.
for a in ASSOCIATIONS:
    if a['actor']=='D':
        n=NODES[a['use_case']]
        edge('designer-'+a['use_case'],'designer',a['use_case'],[(1658,1300),(1370,n['y']+40)])

for mid,_,cy,_ in GROUPS:
    edge('admin-'+mid,'admin',mid,[(187,730),(240,730),(330,cy)])
for cid in ['sign-in','view-layout','view-cost']:
    n=NODES[cid]
    edge('client-'+cid,'client',cid,[(1658,2230),(1370,n['y']+40)])

# Execution dependencies, based on the route/service and UI audit.
DEPENDENCIES=[
 ('include','upload','validate-upload',[(1185,880),(1185,920)],884,'Successful upload validates the original file.'),
 ('extend','correct','review',[(1185,1580),(1185,1540)],1544,'During review, if detections need correction.'),
 ('include','estimate','calculate',[(1185,2140),(1185,2180)],2144,'New saved estimate derives quantities and captures the price used.'),
 ('extend','export','view-cost',[(1185,2420),(1185,2380)],2384,'While viewing a saved estimate/BOM, if Download is selected (Admin/Designer only).')]
for kind,source,target,points,label_y,condition in DEPENDENCIES:
    edge(f'{kind}-{source}',source,target,points,kind)
    text('«'+kind+'»',1205,label_y,150,32,22)

text('Admin connects only to modules; this does not grant Designer editing rights.\nUnlabeled dashed links show module scope; «include» is required; «extend» is conditional.',280,2570,1290,64,22)
text('* Planned: Client access, general user / role management, broader dataset administration and PDF reports.\nClient: sign in and view authorized saved layouts / estimates only. No editing, generation or export.\nDraft previews are provisional; saved estimates require compatible reviewed layout, route and price inputs.',45,2650,1730,95,21)


def segment_hits_box(a,b,n):
    # Liang-Barsky against the interior of a shape's bounding rectangle.
    left,top=n['x']+.1,n['y']+.1
    right,bottom=n['x']+n['w']-.1,n['y']+n['h']-.1
    dx,dy=b[0]-a[0],b[1]-a[1]
    low,high=0.,1.
    for p,q in [(-dx,a[0]-left),(dx,right-a[0]),(-dy,a[1]-top),(dy,bottom-a[1])]:
        if abs(p)<1e-10:
            if q<0:return False
        else:
            r=q/p
            if p<0:low=max(low,r)
            else:high=min(high,r)
            if low>high:return False
    return high>low


def intersection(a,b,c,d):
    def turn(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return turn(a,b,c)*turn(a,b,d)<-1e-6 and turn(c,d,a)*turn(c,d,b)<-1e-6


# Assertions inspect the vector geometry, permission model and serialized native XML.
assert len(GROUPS)==4
assert {a['use_case'] for a in ASSOCIATIONS if a['actor']=='C'}=={'sign-in','view-layout','view-cost'}
assert {a['use_case'] for a in ASSOCIATIONS if a['actor']=='A'}=={'sign-in','users','approvers','inspect','dataset','prices','export','view-cost'}
assert len([n for n in NODES.values() if n['kind']=='actor'])==3
ROLE_IDS={'A':'admin','D':'designer','C':'client'}
for a in ASSOCIATIONS:
    if a['actor']!='A':assert any(e['source']==ROLE_IDS[a['actor']] and e['target']==a['use_case'] for e in EDGES)
assert {e['target'] for e in EDGES if e['source']=='admin'}=={g[0] for g in GROUPS}
assert all(NODES[e['target']]['kind']=='module' for e in EDGES if e['source']=='admin')
assert not any(n['kind']=='port' for n in NODES.values())
crossings=[]
for i,e in enumerate(EDGES):
    for p,q in zip(e['points'],e['points'][1:]):
        for nid,n in NODES.items():
            if nid not in (e['source'],e['target']):
                assert not segment_hits_box(p,q,n),('Edge through unrelated shape',e['id'],nid)
        for f in EDGES[i+1:]:
            for r,s in zip(f['points'],f['points'][1:]):
                if intersection(p,q,r,s):crossings.append((e['id'],f['id']))
assert min(t['font'] for t in TEXT)>=21
FILE=OUT/(STEM+'.drawio')
ET.indent(MX)
ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE)
cells=parsed.findall('.//mxCell')
ids={c.attrib['id'] for c in cells}
assert len(ids)==len(cells)
for c in cells:
    assert c.attrib.get('parent','0') in ids
    if c.attrib.get('edge')=='1':assert c.attrib['source'] in ids and c.attrib['target'] in ids
    assert not re.search(r'(?:fillColor|strokeColor|fontColor)=#(?!000000|FFFFFF)[0-9a-fA-F]{6}',c.attrib.get('style',''))
assert len(parsed.findall('./diagram'))==1
SVG.append('</svg>')
IM.save(OUT/(STEM+'.png'))
(OUT/(STEM+'.svg')).write_text(''.join(SVG),encoding='utf-8')
(OUT/'diagram-data.json').write_text(json.dumps({'modules':GROUPS,'nodes':NODES,'edges':EDGES,'actor_associations':ASSOCIATIONS},indent=2),encoding='utf-8')
REPORT={'one_page':'PASS','module_count':4,'use_case_count':sum(len(g[3]) for g in GROUPS),'human_pictograms':3,'admin_module_only':'PASS','admin_module_associations':4,'include_count':2,'extend_count':2,'dependencies':[dict(kind=k,source=s,target=t,condition=c) for k,s,t,p,y,c in DEPENDENCIES],'continuation_keys':[],'continuation_circles':0,'line_crossings':len(crossings),'unrelated_shape_collisions':0,'native_editable_xml':'PASS','black_and_white_only':'PASS','client_scope':'PASS: sign-in, saved 2D/3D layouts, saved costs only','minimum_font':min(t['font'] for t in TEXT),'repository_audit':'PASS (static route/service/UI inspection; no runtime behavior claim)','visual_review':'PENDING','downloads_copy':'PENDING','diagrams_net_editor_import':'NOT TESTED'}
(OUT/'verification.json').write_text(json.dumps(REPORT,indent=2),encoding='utf-8')
print(json.dumps(REPORT,indent=2))
