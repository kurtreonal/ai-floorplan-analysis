"""Editable theoretical framework using the supplied reference's visual structure."""
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "revision-2"
OUT.mkdir(exist_ok=True)
W, H = 2640, 2100
MX = ET.Element('mxfile', {'host': 'app.diagrams.net', 'type': 'device', 'version': '24.7.17'})
D = ET.SubElement(MX, 'diagram', {'id': 'ved-framework', 'name': 'Theoretical Framework'})
M = ET.SubElement(D, 'mxGraphModel', {'dx': str(W), 'dy': str(H), 'grid': '1', 'gridSize': '10', 'guides': '1', 'connect': '1', 'page': '1', 'pageScale': '1', 'pageWidth': str(W), 'pageHeight': str(H), 'background': '#FFFFFF'})
ROOT = ET.SubElement(M, 'root')
ET.SubElement(ROOT, 'mxCell', {'id': '0'})
ET.SubElement(ROOT, 'mxCell', {'id': '1', 'parent': '0'})
IM = Image.new('RGB', (W, H), 'white')
PEN = ImageDraw.Draw(IM)
SVG = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="white"/>']
FONT, NODES, EDGES, LABELS = {}, {}, [], []
SEQ = 0


def font(size, bold=False):
    if (size, bold) not in FONT:
        FONT[size, bold] = ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if bold else 'arial.ttf'), size)
    return FONT[size, bold]


def wrap(value, width, size, bold=False):
    result = []
    for para in value.split('\n'):
        line = ''
        for word in para.split():
            candidate = (line + ' ' + word).strip()
            if line and font(size, bold).getlength(candidate) > width:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    assert all(font(size, bold).getlength(s) <= width for s in result), value
    return result


def cell(value, x, y, w, h, style, parent='1', px=0, py=0, cid=None):
    global SEQ
    SEQ += 1
    cid = cid or f'c{SEQ}'
    c = ET.SubElement(ROOT, 'mxCell', {'id': cid, 'value': value, 'vertex': '1', 'parent': parent, 'style': style})
    ET.SubElement(c, 'mxGeometry', {'x': str(x-px), 'y': str(y-py), 'width': str(w), 'height': str(h), 'as': 'geometry'})
    return cid


def shape(x, y, w, h, fill='white', kind='rect', stroke='#222222', parent='1', px=0, py=0):
    styles = {'rect': 'rounded=0;', 'ellipse': 'ellipse;', 'body': 'rounded=1;arcSize=45;', 'tie': 'triangle;direction=south;'}
    cell('', x, y, w, h, styles[kind]+f'fillColor={fill};strokeColor={stroke};strokeWidth=1.2;', parent, px, py)
    if kind == 'ellipse':
        SVG.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        PEN.ellipse((x, y, x+w, y+h), fill=fill, outline=stroke, width=1)
    elif kind == 'tie':
        pts = [(x, y), (x+w, y), (x+w/2, y+h)]
        SVG.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in pts)+f'" fill="{fill}" stroke="{stroke}"/>')
        PEN.polygon(pts, fill=fill)
    else:
        r = min(w, h)*0.2 if kind == 'body' else 0
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        PEN.rounded_rectangle((x, y, x+w, y+h), radius=r, fill=fill, outline=stroke, width=1)


def text(value, x, y, w, h, size=16, bold=False, parent='1', px=0, py=0, white=False):
    lines = wrap(value, w-10, size, bold)
    line_h = size+4
    assert len(lines)*line_h <= h+1, ('Text overflow', value, h, len(lines)*line_h)
    assert 0 <= x <= W-w and 0 <= y <= H-h
    cell('\n'.join(lines), x, y, w, h, f'text;html=0;whiteSpace=wrap;fillColor={"#FFFFFF" if white else "none"};strokeColor=none;fontFamily=Arial;fontSize={size};fontStyle={int(bold)};align=center;verticalAlign=middle;spacing=5;', parent, px, py)
    if white:
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>')
        PEN.rectangle((x, y, x+w, y+h), fill='white')
    ty = y+(h-len(lines)*line_h)/2
    for line in lines:
        tx = x+(w-font(size, bold).getlength(line))/2
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}">{html.escape(line)}</text>')
        PEN.text((tx, ty), line, font=font(size, bold), fill='#111111')
        ty += line_h


def node(cid, label, x, y, w, h, kind='module'):
    NODES[cid] = {'label': label, 'x': x, 'y': y, 'w': w, 'h': h, 'kind': kind}
    c = ET.SubElement(ROOT, 'mxCell', {'id': cid, 'value': '', 'vertex': '1', 'parent': '1', 'style': 'group;'})
    ET.SubElement(c, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(w), 'height': str(h), 'as': 'geometry'})
    if kind == 'system':
        shape(x, y, w, h, '#D9D9D9', stroke='#777777', parent=cid, px=x, py=y)
    elif kind == 'module':
        shape(x, y, w, h, parent=cid, px=x, py=y)
        text(label, x+18, y+20, w-36, h-40, 21, True, cid, x, y)
    elif kind == 'actor':
        shape(x, y, w, h, parent=cid, px=x, py=y)
        # Three editable silhouettes reproduce the reference's user-group symbols.
        icon_scale = min(1, (h-60)/202)
        for dx, dy, scale in [(27, 30, .85), (139, 30, .85), (79, 50, 1)]:
            sx = x+(w-230*icon_scale)/2+dx*icon_scale
            sy = y+15+(dy-15)*icon_scale
            scale *= icon_scale
            assert sy+142*scale < y+h-49, ('Actor icon overlaps label',cid)
            shape(sx-5*scale, sy+49*scale, 70*scale, 93*scale, '#241F21', 'body', '#241F21', cid, x, y)
            shape(sx+8*scale, sy, 43*scale, 47*scale, '#241F21', 'ellipse', '#241F21', cid, x, y)
            shape(sx+23*scale, sy+56*scale, 14*scale, 60*scale, '#FFFFFF', 'tie', '#FFFFFF', cid, x, y)
        text(label, x+7, y+h-49, w-14, 42, 17, True, cid, x, y)
    elif kind == 'connector':
        shape(x,y,w,h,kind='ellipse',parent=cid,px=x,py=y)
        text(label,x,y,w,h,18,True,cid,x,y)
    elif kind == 'database':
        cell('', x, y, w, h, 'shape=cylinder3;whiteSpace=wrap;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#FFFFFF;strokeColor=#222222;strokeWidth=1.5;', cid, x, y)
        SVG.append(f'<path d="M {x} {y+15} L {x} {y+h-15} A {w/2} 15 0 0 0 {x+w} {y+h-15} L {x+w} {y+15}" fill="white" stroke="#222222" stroke-width="1.5"/><ellipse cx="{x+w/2}" cy="{y+15}" rx="{w/2}" ry="15" fill="white" stroke="#222222" stroke-width="1.5"/>')
        PEN.rectangle((x, y+15, x+w, y+h-15), fill='white')
        PEN.ellipse((x, y+h-30, x+w, y+h), fill='white', outline='#222222', width=2)
        PEN.line((x, y+15, x, y+h-15), fill='#222222', width=2)
        PEN.line((x+w, y+15, x+w, y+h-15), fill='#222222', width=2)
        PEN.ellipse((x, y, x+w, y+30), fill='white', outline='#222222', width=2)
        text('Saved project, layout,\nrouting and estimate data', x+10, y+42, w-20, h-60, 13, False, cid, x, y)


def flow(source, target, points, label, lx, ly, lw, planned=False, tag='', label_size=16):
    global SEQ
    SEQ += 1
    fid = f'f{SEQ}'
    a, b = NODES[source], NODES[target]
    start, end = points[0], points[-1]
    style = 'edgeStyle=none;rounded=0;html=0;endArrow=block;endFill=1;endSize=9;startArrow=none;strokeColor=#111111;strokeWidth=1.5;'
    style += f'exitX={(start[0]-a["x"])/a["w"]};exitY={(start[1]-a["y"])/a["h"]};entryX={(end[0]-b["x"])/b["w"]};entryY={(end[1]-b["y"])/b["h"]};exitPerimeter=0;entryPerimeter=0;'
    if planned:
        style += 'dashed=1;'
    c = ET.SubElement(ROOT, 'mxCell', {'id': fid, 'value': '', 'edge': '1', 'parent': '1', 'source': source, 'target': target, 'style': style, 'dataLabel': label})
    g = ET.SubElement(c, 'mxGeometry', {'relative': '1', 'as': 'geometry'})
    ar = ET.SubElement(g, 'Array', {'as': 'points'})
    for xx, yy in points[1:-1]:
        ET.SubElement(ar, 'mxPoint', {'x': str(xx), 'y': str(yy)})
    SVG.append('<path d="'+' '.join(('M' if i == 0 else 'L')+f' {xx} {yy}' for i,(xx,yy) in enumerate(points))+'" fill="none" stroke="#111111" stroke-width="1.5"'+(' stroke-dasharray="8 5"' if planned else '')+'/>')
    for p, q in zip(points, points[1:]):
        length = math.dist(p, q)
        if not planned:
            PEN.line((p, q), fill='#111111', width=2)
        else:
            for t in range(0, math.ceil(length), 13):
                t2 = min(t+8, length)
                PEN.line((p[0]+(q[0]-p[0])*t/length, p[1]+(q[1]-p[1])*t/length, p[0]+(q[0]-p[0])*t2/length, p[1]+(q[1]-p[1])*t2/length), fill='#111111', width=2)
    p, q = points[-2:]
    length = math.dist(p, q)
    ux, uy = (q[0]-p[0])/length, (q[1]-p[1])/length
    arrow = [q, (q[0]-10*ux+5*uy, q[1]-10*uy-5*ux), (q[0]-10*ux-5*uy, q[1]-10*uy+5*ux)]
    SVG.append('<polygon points="'+' '.join(f'{xx},{yy}' for xx,yy in arrow)+'" fill="#111111"/>')
    PEN.polygon(arrow, fill='#111111')
    lines = wrap(label, lw-10, label_size)
    width = math.ceil(max(font(label_size).getlength(line) for line in lines))+10
    lh = len(lines)*(label_size+4)+4
    lx += (lw-width)/2
    text(label, lx, ly, width, lh, label_size, white=True)
    EDGES.append({'id': fid, 'source': source, 'target': target, 'points': points, 'label': label, 'planned': planned, 'tag': tag})
    LABELS.append((fid, (lx, ly, width, lh)))


text('THEORETICAL FRAMEWORK',40,20,700,40,26,True)
node('system','VED Electrical Services',760,160,500,1510,'system')
text('VED ELECTRICAL SERVICES:\nAI-DRIVEN FLOOR PLAN ANALYSIS AND\n3D VISUALIZATION SYSTEM FOR AUTOMATED\nLAYOUT AND COST ESTIMATION',780,177,460,112,18,True,'system',760,160)
for cid,label,y,h in [
 ('access','USER AND ACCESS\nMANAGEMENT MODULE',320,160),
 ('project-visualization','PROJECT, FLOOR PLAN AND\nVISUALIZATION MODULE',570,260),
 ('ai','AI ANALYSIS AND\nDETECTION MODULE',930,180),
 ('routing-cost','ELECTRICAL ROUTING, COST ESTIMATION\nAND REPORTING MODULE',1290,280)]:
 node(cid,label,790,y,440,h)
node('admin','ADMINISTRATOR',60,820,230,300,'actor')
node('designer','ELECTRICAL DESIGNER',1750,820,230,300,'actor')
node('client','CLIENT*\nREAD-ONLY',2360,960,230,260,'actor')
node('database','MySQL Database',900,1770,200,150,'database')
text('MYSQL DATABASE',840,1930,320,30,18,True)

# Native Internet context, following the reference's cloud above the system.
cell('INTERNET',1110,30,230,95,'shape=cloud;whiteSpace=wrap;html=0;fillColor=#FFFFFF;strokeColor=#222222;fontFamily=Arial;fontSize=14;fontStyle=1;')
cloud=[(1110,83),(1118,62),(1133,57),(1140,41),(1163,37),(1176,29),(1203,29),(1216,36),(1238,29),(1266,33),(1276,45),(1299,46),(1311,59),(1331,67),(1339,83),(1331,100),(1308,108),(1288,117),(1258,113),(1239,120),(1211,114),(1184,116),(1162,105),(1138,103),(1121,94)]
SVG.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in cloud)+'" fill="white" stroke="#222222" stroke-width="1.2"/>')
PEN.polygon(cloud,fill='white',outline='#222222')
PEN.text((1189,68),'INTERNET',font=font(14,True),fill='black')
SVG.append('<text x="1189" y="82" font-family="Arial" font-size="14" font-weight="700">INTERNET</text>')
shape(1125,132,25,15,kind='ellipse')
shape(1114,151,12,8,kind='ellipse')

# ADMIN: each original responsibility has its own explicit module connection.
flow('admin','access',[(90,820),(90,360),(790,360)],'Sign in; manage user records / roles*;\nassign or revoke dataset approver',330,333,410,tag='admin-access-manage')
flow('access','admin',[(790,420),(130,420),(130,820)],'User / role records*; assignment history\nand access / update status',330,397,410,tag='admin-access-result')
flow('admin','project-visualization',[(170,820),(170,615),(790,615)],'Inspect all projects, floor plans\nand saved 2D / 3D layouts',330,588,410,tag='admin-project-inspect')
flow('project-visualization','admin',[(790,665),(210,665),(210,820)],'Project details; uploaded plans;\nsaved layouts and job status',330,643,410,tag='admin-project-result')
flow('admin','ai',[(290,980),(790,980)],'Manage approved datasets* / legends;\ninspect AI results and review records',330,955,410,tag='admin-ai-manage')
flow('ai','admin',[(790,1030),(290,1030)],'Dataset / legend update status*;\nAI results and review records',330,1007,410,tag='admin-ai-result')
flow('admin','routing-cost',[(250,1120),(250,1330),(790,1330)],'Inspect saved wire / conduit routes',330,1309,410,tag='admin-route-inspect')
flow('routing-cost','admin',[(790,1370),(210,1370),(210,1120)],'Stored routes and measured lengths',330,1349,410,tag='admin-route-result')
flow('admin','routing-cost',[(170,1120),(170,1410),(790,1410)],'Import / update material catalog and prices;\nmanage report records*',330,1380,410,tag='admin-price-manage')
flow('routing-cost','admin',[(790,1450),(130,1450),(130,1120)],'Material catalog / price revision status',330,1429,410,tag='admin-price-result')
flow('admin','routing-cost',[(90,1120),(90,1490),(790,1490)],'Inspect estimates, BOM and price versions;\nexport costs / reports*',330,1460,410,tag='admin-cost-export')
flow('routing-cost','admin',[(790,1530),(75,1530),(75,1120)],'Captured costs, quantities and export files*',330,1509,410,tag='admin-cost-result')

# DESIGNER: original authoring, verification and output capabilities preserved.
flow('designer','access',[(1940,820),(1940,360),(1230,360)],'Sign in and request access',1300,339,410,tag='designer-sign-in')
flow('access','designer',[(1230,420),(1900,420),(1900,820)],'Access result and permissions',1300,399,410,tag='designer-access-result')
flow('designer','project-visualization',[(1860,820),(1860,615),(1230,615)],'Create / update projects and upload plans',1300,594,410,tag='designer-project-manage')
flow('project-visualization','designer',[(1230,665),(1820,665),(1820,820)],'Saved project / floor-plan records and status',1300,644,410,tag='designer-project-result')
flow('designer','project-visualization',[(1780,820),(1780,715),(1230,715)],'Open, edit and save layout',1300,694,410,tag='designer-layout-edit')
flow('project-visualization','designer',[(1230,765),(1760,765),(1760,820)],'Saved 2D / 3D layout and geometry version',1300,744,410,tag='designer-layout-result')
flow('designer','ai',[(1750,980),(1230,980)],'Start analysis; confirm or correct results',1300,959,410,tag='designer-analysis-review')
flow('ai','designer',[(1230,1030),(1750,1030)],'Detected walls / symbols and review status',1300,1009,410,tag='designer-analysis-result')
flow('designer','routing-cost',[(1780,1120),(1780,1330),(1230,1330)],'Set routing inputs; calculate electrical routes',1300,1309,410,tag='designer-route-generate')
flow('routing-cost','designer',[(1230,1370),(1820,1370),(1820,1120)],'Wire / conduit paths and measured lengths',1300,1349,410,tag='designer-route-result')
flow('designer','routing-cost',[(1860,1120),(1860,1490),(1230,1490)],'Apply project prices; generate estimate;\nexport BOM / reports*',1300,1467,410,tag='designer-estimate-generate')
flow('routing-cost','designer',[(1230,1530),(1900,1530),(1900,1120)],'Cost breakdown and generated export files*',1300,1518,410,tag='designer-estimate-result')

# Client operation continuations make all three actors readable without crossings.
for cid,label,x,y in [('a-module','A',1320,500),('v-module','V',1320,850),('c-module','C',1320,1600),
                       ('a-client','A',2140,780),('v-client','V',2140,1030),('c-client','C',2140,1280)]:
 node(cid,label,x,y,50,50,'connector')
flow('a-module','access',[(1320,515),(1130,515),(1130,480)],'Sign-in request',1095,495,200,True,'client-sign-in-request',12)
flow('access','a-module',[(1080,480),(1080,535),(1320,535)],'Read-only access',1148,534,160,True,'client-sign-in-response',12)
flow('client','a-client',[(2490,960),(2490,795),(2190,795)],'Sign-in request',2205,778,200,True,'client-sign-in-request',12)
flow('a-client','client',[(2190,815),(2450,815),(2450,960)],'Read-only access',2205,813,200,True,'client-sign-in-response',12)
flow('v-module','project-visualization',[(1320,865),(1130,865),(1130,830)],'View saved layout',1095,845,200,True,'client-layout-request',12)
flow('project-visualization','v-module',[(1080,830),(1080,885),(1320,885)],'Read-only layout',1148,884,160,True,'client-layout-response',12)
flow('client','v-client',[(2360,1045),(2190,1045)],'View saved layout',2198,1028,150,True,'client-layout-request',12)
flow('v-client','client',[(2190,1075),(2360,1075)],'Read-only layout',2198,1058,150,True,'client-layout-response',12)
flow('c-module','routing-cost',[(1320,1615),(1130,1615),(1130,1570)],'View cost estimate',1095,1595,200,True,'client-cost-request',12)
flow('routing-cost','c-module',[(1080,1570),(1080,1635),(1320,1635)],'Read-only costs',1148,1634,160,True,'client-cost-response',12)
flow('client','c-client',[(2450,1220),(2450,1295),(2190,1295)],'View cost estimate',2205,1278,200,True,'client-cost-request',12)
flow('c-client','client',[(2190,1315),(2490,1315),(2490,1220)],'Read-only costs',2205,1318,200,True,'client-cost-response',12)
flow('system','database',[(975,1670),(975,1770)],'Store data',790,1706,170,tag='persist')
flow('database','system',[(1025,1770),(1025,1670)],'Retrieve saved data',1040,1706,210,tag='retrieve')

# Module scopes remain the same as in the supplied current theoretical framework.
text('A = Sign-in     V = Saved 2D / 3D visualization     C = Stored cost estimate',2040,1400,580,30,14,True)
text('Matching letters continue the same Client request / response.\nThey do not pass through the Designer.',2050,1440,560,52,14)
text('CLIENT PERMISSIONS',2090,1540,480,30,18,True)
text('Sign in to the system.\nView authorized saved 2D / 3D layouts.\nView stored cost breakdowns and totals.',2070,1580,520,82,16)
text('No project edits, uploads, AI review, route generation,\nprice changes, estimate generation or exports.',2040,1670,580,50,14)
text('Shared canonical geometry keeps 2D, 3D, routes and estimate quantities aligned.',500,1970,1450,30,17)
text('Figure. Theoretical Framework of VED Electrical Services',350,2010,1940,35,23)
text('* Planned target functions retained: user / role management, broader dataset administration, PDF reports / report administration and Client access.',210,2054,2220,26,14)


def hit(rect,a,b):
 x,y,w,h=rect
 if a[0]==b[0]:return x<a[0]<x+w and max(min(a[1],b[1]),y)<min(max(a[1],b[1]),y+h)
 return y<a[1]<y+h and max(min(a[0],b[0]),x)<min(max(a[0],b[0]),x+w)


def cross(a,b,c,d):
 if a[1]==b[1] and c[1]==d[1]:return a[1]==c[1] and max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0]))
 if a[0]==b[0] and c[0]==d[0]:return a[0]==c[0] and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1]))
 if a[0]==b[0]:return cross(c,d,a,b)
 return min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(c[1],d[1])<=a[1]<=max(c[1],d[1])


segments=[(f['id'],a,b) for f in EDGES for a,b in zip(f['points'],f['points'][1:])]
for i,(fid,a,b) in enumerate(segments):
 assert a[0]==b[0] or a[1]==b[1]
 for other,c,d in segments[i+1:]:
  if fid!=other:assert not cross(a,b,c,d),('Crossed arrows',fid,other,a,b,c,d)
 for nid,n in NODES.items():
  if n['kind']!='system':assert not hit((n['x'],n['y'],n['w'],n['h']),a,b),('Arrow through node',fid,nid)
 for lid,r in LABELS:
  if lid!=fid:assert not hit(r,a,b),('Arrow through label',fid,lid)
for i,(fid,a) in enumerate(LABELS):
 for other,b in LABELS[i+1:]:assert not(a[0]<b[0]+b[2] and a[0]+a[2]>b[0] and a[1]<b[1]+b[3] and a[1]+a[3]>b[1]),('Overlapping labels',fid,other)
 for nid,n in NODES.items():
  if n['kind']!='system':assert not(a[0]<n['x']+n['w'] and a[0]+a[2]>n['x'] and a[1]<n['y']+n['h'] and a[1]+a[3]>n['y']),('Label through node',fid,nid)
assert len([n for n in NODES.values() if n['kind']=='module'])==4
assert len(EDGES)==38
assert not any('system' in (f['source'],f['target']) and ('admin' in (f['source'],f['target'])) for f in EDGES)
for f in EDGES:assert any(g['source']==f['target'] and g['target']==f['source'] for g in EDGES),('Unpaired arrow',f)
admin_required={'admin-access-manage','admin-access-result','admin-project-inspect','admin-project-result','admin-ai-manage','admin-ai-result','admin-route-inspect','admin-route-result','admin-price-manage','admin-price-result','admin-cost-export','admin-cost-result'}
assert {f['tag'] for f in EDGES if 'admin' in (f['source'],f['target'])}==admin_required
for code,module in [('a','access'),('v','project-visualization'),('c','routing-cost')]:
 module_flows=[f for f in EDGES if f['source']==f'{code}-module' or f['target']==f'{code}-module']
 client_flows=[f for f in EDGES if f['source']==f'{code}-client' or f['target']==f'{code}-client']
 assert len(module_flows)==len(client_flows)==2
 assert {f['tag'] for f in module_flows}=={f['tag'] for f in client_flows}
 for f in module_flows:
  assert f['planned'] and module in (f['source'],f['target'])
  matching=next(g for g in client_flows if g['tag']==f['tag'])
  assert matching['label']==f['label'] and matching['planned']
assert all(NODES[f['target']]['kind']=='connector' for f in EDGES if f['source']=='client')
assert not any('client' in (f['source'],f['target']) and 'designer' in (f['source'],f['target']) for f in EDGES)
SVG.append('</svg>')
FILE=OUT/'ved-theoretical-framework-revised-2026-10-20.drawio'
ET.indent(MX);ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE);cells=parsed.findall('.//mxCell');ids={c.attrib['id'] for c in cells}
assert len(ids)==len(cells)
for c in cells:
 assert c.attrib.get('parent','0') in ids
 if c.attrib.get('edge')=='1':assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in cells)
IM.save(OUT/'ved-theoretical-framework-revised.png')
(OUT/'ved-theoretical-framework-revised.svg').write_text(''.join(SVG),encoding='utf-8')
(OUT/'preview.html').write_text('<!doctype html><html><meta charset="utf-8"><title>VED theoretical framework revised</title><style>body{margin:0;background:#ddd}svg{display:block;width:100%;max-width:2640px;margin:auto;background:white}</style>'+''.join(SVG)+'</html>',encoding='utf-8')
(OUT/'framework-data.json').write_text(json.dumps({'nodes':NODES,'flows':EDGES},indent=2),encoding='utf-8')
report={'pages':1,'original_modules_preserved':4,'arrows':38,'admin_explicit_operation_pairs':6,'designer_operation_pairs':6,'client_logical_operation_pairs':3,
 'admin_capability_coverage':'PASS','client_scope':'Sign-in, saved visualization viewing, stored cost-estimate viewing only','client_continuation_balance':'PASS','paired_arrows':'PASS',
 'crossed_arrows':0,'arrow_node_collisions':0,'arrow_label_collisions':0,'overlapping_labels':0,'text_fit':'PASS','native_editable_xml':'PASS',
 'visual_review':'PENDING','downloads_copy':'PENDING','editor_import':'NOT TESTED'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
