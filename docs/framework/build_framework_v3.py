"""Editable theoretical framework using the supplied reference's visual structure."""
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "revision-3"
OUT.mkdir(exist_ok=True)
W, H = 1840, 1870
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
    cell('\n'.join(lines), x, y, w, h, f'text;html=0;whiteSpace=wrap;fillColor={"#FFFFFF" if white else "none"};strokeColor=none;fontFamily=Arial;fontSize={size};fontStyle={int(bold)};align=center;verticalAlign=middle;spacing=0;', parent, px, py)
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
        text(label, x+18, y+20, w-36, h-40, 26, True, cid, x, y)
    elif kind == 'callout':
        shape(x, y, w, h, parent=cid, px=x, py=y)
        text(label, x+15, y+15, w-30, h-30, 24, False, cid, x, y)
    elif kind == 'actor':
        shape(x, y, w, h, parent=cid, px=x, py=y)
        # Three editable silhouettes reproduce the reference's user-group symbols.
        icon_scale = min(1, (h-80)/202)
        for dx, dy, scale in [(27, 30, .85), (139, 30, .85), (79, 50, 1)]:
            sx = x+(w-230*icon_scale)/2+dx*icon_scale
            sy = y+15+(dy-15)*icon_scale
            scale *= icon_scale
            assert sy+142*scale < y+h-67, ('Actor icon overlaps label',cid)
            shape(sx-5*scale, sy+49*scale, 70*scale, 93*scale, '#241F21', 'body', '#241F21', cid, x, y)
            shape(sx+8*scale, sy, 43*scale, 47*scale, '#241F21', 'ellipse', '#241F21', cid, x, y)
            shape(sx+23*scale, sy+56*scale, 14*scale, 60*scale, '#FFFFFF', 'tie', '#FFFFFF', cid, x, y)
        text(label, x+7, y+h-67, w-14, 60, 22, True, cid, x, y)
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


def flow(source, target, points, label, lx, ly, lw, planned=False, tag='', label_size=24):
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


# Reference composition: gray spine, white modules, outside people, cloud and database.
text('THEORETICAL FRAMEWORK',20,20,620,42,28,True)
node('system','VED Electrical Services',580,170,460,1320,'system')
text('VED ELECTRICAL SERVICES:\nAI-DRIVEN FLOOR PLAN ANALYSIS\nAND 3D VISUALIZATION SYSTEM FOR\nAUTOMATED LAYOUT AND COST\nESTIMATION',600,180,420,140,22,True,'system',580,170)
for cid,label,y,h in [
 ('access','USER AND ACCESS\nMANAGEMENT MODULE',340,120),
 ('project-visualization','PROJECT, FLOOR PLAN AND\nVISUALIZATION MODULE',480,280),
 ('ai','AI ANALYSIS AND\nDETECTION MODULE',820,200),
 ('routing-cost','ELECTRICAL ROUTING,\nCOST ESTIMATION AND\nREPORTING MODULE',1080,360)]:
 node(cid,label,600,y,420,h)
node('admin','ADMINISTRATOR',20,730,230,270,'actor')
node('designer','ELECTRICAL\nDESIGNER',1270,890,200,220,'actor')
node('client','CLIENT*\nVIEW ONLY',1540,660,200,220,'actor')
node('shared-sign-in','SHARED SIGN-IN\nAdmin / Designer / Client*',1100,150,630,130,'callout')
node('database','MySQL Database',720,1570,180,120,'database')
text('MYSQL DATABASE',660,1700,300,36,24,True)

# The Internet motif is context, not an additional application module.
cell('INTERNET',840,25,250,110,'shape=cloud;whiteSpace=wrap;html=0;fillColor=#FFFFFF;strokeColor=#222222;fontFamily=Arial;fontSize=22;fontStyle=1;')
cloud=[(840,83),(848,62),(863,57),(870,41),(893,37),(906,29),(933,29),(946,36),(968,29),(996,33),(1006,45),(1029,46),(1041,59),(1061,67),(1069,83),(1061,100),(1038,108),(1018,117),(988,113),(969,120),(941,114),(914,116),(892,105),(868,103),(851,94)]
SVG.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in cloud)+'" fill="white" stroke="#222222" stroke-width="1.2"/>')
PEN.polygon(cloud,fill='white',outline='#222222')
PEN.text((901,65),'INTERNET',font=font(22,True),fill='black')
SVG.append('<text x="901" y="87" font-family="Arial" font-size="22" font-weight="700">INTERNET</text>')
shape(855,132,25,15,kind='ellipse')
shape(844,151,12,8,kind='ellipse')

# Sign-in applies to each named role. One shared connection avoids repeating
# three identical authentication paths across the authoring and viewing paths.
flow('shared-sign-in','access',[(1200,280),(1200,360),(1020,360)],'Sign in',1030,363,160,tag='shared-sign-in')
flow('access','shared-sign-in',[(1020,400),(1250,400),(1250,280)],'Access / role',1030,403,210,tag='shared-access-result')

# ADMIN: all six responsibility/result groups remain explicit.
flow('admin','access',[(60,730),(60,350),(600,350)],'Manage users / roles*;\nassign / revoke approvers',260,284,320,tag='admin-access-manage')
flow('access','admin',[(600,400),(100,400),(100,730)],'Records / access status',260,403,320,tag='admin-access-result')
flow('admin','project-visualization',[(140,730),(140,650),(600,650)],'Inspect projects / layouts',260,653,320,tag='admin-project-inspect')
flow('project-visualization','admin',[(600,700),(180,700),(180,730)],'Plans / jobs / layouts',260,703,320,tag='admin-project-result')
flow('admin','ai',[(250,900),(600,900)],'Manage legends / datasets*',260,903,330,tag='admin-ai-manage')
flow('ai','admin',[(600,960),(250,960)],'Updates / AI review status',260,963,330,tag='admin-ai-result')
flow('admin','routing-cost',[(220,1000),(220,1120),(600,1120)],'Inspect saved routes',260,1123,320,tag='admin-route-inspect')
flow('routing-cost','admin',[(600,1160),(180,1160),(180,1000)],'Routes / lengths',260,1163,320,tag='admin-route-result')
flow('admin','routing-cost',[(140,1000),(140,1200),(600,1200)],'Manage prices / reports*',260,1203,320,tag='admin-price-manage')
flow('routing-cost','admin',[(600,1240),(100,1240),(100,1000)],'Catalog / update status',260,1243,320,tag='admin-price-result')
flow('admin','routing-cost',[(60,1000),(60,1280),(600,1280)],'View costs / export reports*',260,1283,330,tag='admin-cost-export')
flow('routing-cost','admin',[(600,1320),(30,1320),(30,1000)],'Costs / BOM / report files*',260,1323,330,tag='admin-cost-result')

# DESIGNER: aggregated project/layout pair retains all authoring functions.
flow('designer','project-visualization',[(1450,890),(1450,875),(1510,875),(1510,575),(1020,575)],'Projects / uploads / layout edits',1060,578,410,tag='designer-project-layout-manage')
flow('project-visualization','designer',[(1020,620),(1490,620),(1490,845),(1410,845),(1410,890)],'Project / layout status',1060,623,410,tag='designer-project-layout-result')
flow('designer','ai',[(1270,900),(1020,900)],'Analyze / review',1030,903,230,tag='designer-ai-review')
flow('ai','designer',[(1020,960),(1270,960)],'Results / status',1030,963,230,tag='designer-ai-result')
flow('designer','routing-cost',[(1330,1110),(1330,1120),(1020,1120)],'Generate routes',1030,1123,280,tag='designer-route-generate')
flow('routing-cost','designer',[(1020,1160),(1370,1160),(1370,1110)],'Paths / measured lengths',1030,1163,330,tag='designer-route-result')
flow('designer','routing-cost',[(1410,1110),(1410,1240),(1020,1240)],'Generate costs / reports*',1040,1243,350,tag='designer-cost-generate')
flow('routing-cost','designer',[(1020,1280),(1450,1280),(1450,1110)],'Costs / report files*',1040,1283,390,tag='designer-cost-result')

# CLIENT: direct saved-output viewing only; never routed through Designer.
flow('client','project-visualization',[(1700,660),(1700,490),(1020,490)],'View saved 2D / 3D layout',1100,493,420,True,'client-visualization-request')
flow('project-visualization','client',[(1020,530),(1650,530),(1650,660)],'Read-only layout',1100,533,420,True,'client-visualization-result')
flow('client','routing-cost',[(1740,780),(1780,780),(1780,1350),(1020,1350)],'View stored estimate',1120,1353,490,True,'client-cost-request')
flow('routing-cost','client',[(1020,1400),(1810,1400),(1810,740),(1740,740)],'Read-only costs',1120,1403,490,True,'client-cost-result')

flow('system','database',[(790,1490),(790,1570)],'Store data',600,1515,175,tag='store',label_size=22)
flow('database','system',[(830,1570),(830,1490)],'Retrieve data',845,1515,200,tag='retrieve',label_size=22)
text('Figure. Theoretical Framework of VED Electrical Services',120,1760,1600,40,26)
text('* Planned: Client access, user / role management, broader dataset administration and PDF report functions.\nDashed arrows show planned Client viewing. All roles use shared sign-in.',80,1810,1680,55,20)


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
assert len(EDGES)==28
for f in EDGES:assert any(g['source']==f['target'] and g['target']==f['source'] for g in EDGES),('Unpaired arrow',f)
admin_required={'admin-access-manage','admin-access-result','admin-project-inspect','admin-project-result','admin-ai-manage','admin-ai-result','admin-route-inspect','admin-route-result','admin-price-manage','admin-price-result','admin-cost-export','admin-cost-result'}
assert {f['tag'] for f in EDGES if 'admin' in (f['source'],f['target'])}==admin_required
assert all(f['planned'] and set((f['source'],f['target'])) & {'project-visualization','routing-cost'} for f in EDGES if 'client' in (f['source'],f['target']))
assert not any(set((f['source'],f['target']))=={'client','designer'} for f in EDGES)
assert all(role in NODES['shared-sign-in']['label'] for role in ['Admin','Designer','Client'])
SVG.append('</svg>')
FILE=OUT/'ved-theoretical-framework-readable-2026-10-20.drawio'
ET.indent(MX);ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE);cells=parsed.findall('.//mxCell');ids={c.attrib['id'] for c in cells}
assert len(ids)==len(cells)
for c in cells:
 assert c.attrib.get('parent','0') in ids
 if c.attrib.get('edge')=='1':assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in cells)
font_sizes=[int(c.attrib['style'].split('fontSize=')[1].split(';')[0]) for c in cells if 'fontSize=' in c.attrib.get('style','')]
assert min(font_sizes)>=20
IM.save(OUT/'ved-theoretical-framework-readable.png')
(OUT/'ved-theoretical-framework-readable.svg').write_text(''.join(SVG),encoding='utf-8')
(OUT/'preview.html').write_text('<!doctype html><html><meta charset="utf-8"><title>VED theoretical framework</title><style>body{margin:0;background:#ddd}svg{display:block;width:100%;max-width:1840px;margin:auto;background:white}</style>'+''.join(SVG)+'</html>',encoding='utf-8')
(OUT/'framework-data.json').write_text(json.dumps({'nodes':NODES,'flows':EDGES,'arrow_label_boxes':LABELS},indent=2),encoding='utf-8')
report={'pages':1,'original_modules_preserved':4,'arrows':28,'admin_explicit_operation_pairs':6,'designer_operation_pairs':4,'client_direct_viewing_pairs':2,'shared_sign_in_roles':['Admin','Designer','Client (planned)'],
 'canvas':[W,H],'main_arrow_font':24,'module_font':26,'minimum_font':min(font_sizes),
 'admin_capability_coverage':'PASS','client_scope':'Shared sign-in, saved 2D/3D visualization viewing and stored cost-estimate viewing only','paired_arrows':'PASS',
 'crossed_arrows':0,'arrow_node_collisions':0,'arrow_label_collisions':0,'overlapping_labels':0,'text_fit':'PASS','native_editable_xml':'PASS',
 'visual_review':'PENDING','downloads_copy':'PENDING','editor_import':'NOT TESTED'}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
