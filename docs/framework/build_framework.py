"""Editable theoretical framework using the supplied reference's visual structure."""
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H = 1840, 1700
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
    elif kind == 'database':
        cell('', x, y, w, h, 'shape=cylinder3;whiteSpace=wrap;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#FFFFFF;strokeColor=#222222;strokeWidth=1.5;', cid, x, y)
        SVG.append(f'<path d="M {x} {y+15} L {x} {y+h-15} A {w/2} 15 0 0 0 {x+w} {y+h-15} L {x+w} {y+15}" fill="white" stroke="#222222" stroke-width="1.5"/><ellipse cx="{x+w/2}" cy="{y+15}" rx="{w/2}" ry="15" fill="white" stroke="#222222" stroke-width="1.5"/>')
        PEN.rectangle((x, y+15, x+w, y+h-15), fill='white')
        PEN.ellipse((x, y+h-30, x+w, y+h), fill='white', outline='#222222', width=2)
        PEN.line((x, y+15, x, y+h-15), fill='#222222', width=2)
        PEN.line((x+w, y+15, x+w, y+h-15), fill='#222222', width=2)
        PEN.ellipse((x, y, x+w, y+30), fill='white', outline='#222222', width=2)
        text('Saved project, layout,\nrouting and estimate data', x+10, y+42, w-20, h-60, 13, False, cid, x, y)


def flow(source, target, points, label, lx, ly, lw, planned=False, tag=''):
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
    lines = wrap(label, lw-10, 14)
    width = math.ceil(max(font(14).getlength(line) for line in lines))+10
    lh = len(lines)*18+4
    lx += (lw-width)/2
    text(label, lx, ly, width, lh, 14, white=True)
    EDGES.append({'id': fid, 'source': source, 'target': target, 'points': points, 'label': label, 'planned': planned, 'tag': tag})
    LABELS.append((fid, (lx, ly, width, lh)))


text('THEORETICAL FRAMEWORK', 40, 20, 650, 40, 24, True)
node('system', 'VED Electrical Services', 650, 160, 500, 1130, 'system')
text('VED ELECTRICAL SERVICES:\nAI-DRIVEN FLOOR PLAN ANALYSIS AND\n3D VISUALIZATION SYSTEM FOR AUTOMATED\nLAYOUT AND COST ESTIMATION', 670, 177, 460, 112, 18, True, 'system', 650, 160)
for cid, label, yy in [
    ('access', 'USER AND ACCESS\nMANAGEMENT MODULE', 310),
    ('project-ai', 'PROJECT, FLOOR PLAN AND\nAI REVIEW MODULE', 510),
    ('visualization', '2D / 3D VISUALIZATION\nMODULE', 710),
    ('routing', 'ELECTRICAL ROUTING AND\nMEASUREMENTS MODULE', 910),
    ('estimation', 'COST ESTIMATION AND\nREPORTING MODULE', 1110)]:
    node(cid, label, 680, yy, 440, 140)
node('designer', 'ELECTRICAL DESIGNER', 90, 650, 230, 250, 'actor')
node('admin', 'ADMINISTRATOR', 1370, 80, 230, 220, 'actor')
node('client', 'CLIENT*\nREAD-ONLY', 1550, 850, 230, 250, 'actor')
node('database', 'MySQL Database', 800, 1390, 200, 150, 'database')
text('MYSQL DATABASE', 740, 1550, 320, 30, 18, True)

# A web-access cloud, matching the reference. It is context, not an external AI service.
cell('INTERNET', 1010, 27, 230, 95, 'shape=cloud;whiteSpace=wrap;html=0;fillColor=#FFFFFF;strokeColor=#222222;fontFamily=Arial;fontSize=14;fontStyle=1;')
cloud = [(1010,83),(1012,67),(1028,59),(1035,43),(1056,40),(1070,29),(1097,29),(1111,36),(1133,29),(1161,33),(1171,45),(1194,46),(1206,59),(1225,66),(1236,81),(1230,97),(1208,106),(1188,115),(1158,113),(1139,120),(1111,114),(1084,116),(1062,105),(1038,103),(1021,94)]
cloud_path = [f'M {cloud[0][0]} {cloud[0][1]}']
smooth_cloud = []
for i,p1 in enumerate(cloud):
    p0,p2,p3 = cloud[(i-1)%len(cloud)],cloud[(i+1)%len(cloud)],cloud[(i+2)%len(cloud)]
    c1 = (p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6)
    c2 = (p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6)
    cloud_path.append(f'C {c1[0]} {c1[1]} {c2[0]} {c2[1]} {p2[0]} {p2[1]}')
    for step in range(10):
        t=step/10;u=1-t
        smooth_cloud.append((u**3*p1[0]+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t**3*p2[0],u**3*p1[1]+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t**3*p2[1]))
SVG.append('<path d="'+' '.join(cloud_path)+' Z" fill="white" stroke="#222222" stroke-width="1.2"/>')
PEN.polygon(smooth_cloud, fill='white', outline='#222222')
# Preview text only: the editable cloud already owns its native label.
fw = font(14, True).getlength('INTERNET')
PEN.text((1125-fw/2, 68), 'INTERNET', font=font(14, True), fill='black')
SVG.append('<text x="1090" y="82" font-family="Arial" font-size="14" font-weight="700">INTERNET</text>')
shape(1014, 130, 25, 15, kind='ellipse')
shape(1003, 149, 12, 8, kind='ellipse')

# Designer can produce and edit outputs; each request has a distinct response.
flow('designer','access',[(120,650),(120,350),(680,350)],'Sign in and request access',335,329,315,tag='sign-in')
flow('access','designer',[(680,400),(160,400),(160,650)],'Access result and permissions',335,379,315,tag='access-result')
flow('designer','project-ai',[(200,650),(200,550),(680,550)],'Create projects; upload plans;\nreview or correct AI results',335,520,315,tag='project-write')
flow('project-ai','designer',[(680,600),(240,600),(240,650)],'Saved projects; proposals;\nreview and validation status',335,577,315,tag='project-result')
flow('designer','visualization',[(320,750),(680,750)],'Open, edit and save layout',335,729,315,tag='layout-write')
flow('visualization','designer',[(680,800),(320,800)],'Saved 2D / 3D layout and version',335,779,315,tag='layout-result')
flow('designer','routing',[(240,900),(240,950),(680,950)],'Set routing inputs and\ncalculate electrical routes',335,923,315,tag='route-write')
flow('routing','designer',[(680,1000),(200,1000),(200,900)],'Wire / conduit paths and lengths',335,979,315,tag='route-result')
flow('designer','estimation',[(160,900),(160,1150),(680,1150)],'Generate estimate and export report',335,1129,315,tag='estimate-write')
flow('estimation','designer',[(680,1200),(120,1200),(120,900)],'Cost breakdown and report',335,1179,315,tag='estimate-result')

# Administrative operations are directed to the system boundary as a whole.
flow('admin','system',[(1370,170),(1150,170)],'Manage access, approved legends\nand material prices',1163,139,195,tag='admin-manage')
flow('system','admin',[(1150,250),(1370,250)],'Records and update status',1163,229,195,tag='admin-result')

# Client connects to the system directly, never through the Designer.
flow('client','access',[(1740,850),(1740,350),(1120,350)],'Sign in and request access',1250,329,400,True,'client-sign-in')
flow('access','client',[(1120,400),(1700,400),(1700,850)],'Access result and read-only permissions',1250,379,400,True,'client-access-result')
flow('client','visualization',[(1660,850),(1660,750),(1120,750)],'Request saved 2D / 3D layout',1250,729,360,True,'client-view-layout')
flow('visualization','client',[(1120,800),(1620,800),(1620,850)],'Authorized layout - view only',1250,779,340,True,'client-layout-result')
flow('client','estimation',[(1620,1100),(1620,1150),(1120,1150)],'Request stored cost estimate',1250,1129,340,True,'client-view-cost')
flow('estimation','client',[(1120,1200),(1660,1200),(1660,1100)],'Cost breakdown and total - view only',1250,1179,360,True,'client-cost-result')
flow('system','database',[(875,1290),(875,1390)],'Store data',681,1328,180,tag='persist')
flow('database','system',[(925,1390),(925,1290)],'Retrieve saved data',943,1328,205,tag='retrieve')

text('Shared canonical geometry keeps 2D, 3D, routes and estimate quantities aligned.', 370, 1588, 1100, 28, 16)
text('Figure. Theoretical Framework of VED Electrical Services', 260, 1625, 1320, 32, 20)
text('* Proposed Client access: sign-in and viewing saved layouts / estimates only. No editing, routing or report export.', 180, 1662, 1480, 26, 14)


def hit(rect, a, b):
    x, y, w, h = rect
    if a[0] == b[0]:
        return x < a[0] < x+w and max(min(a[1],b[1]),y) < min(max(a[1],b[1]),y+h)
    return y < a[1] < y+h and max(min(a[0],b[0]),x) < min(max(a[0],b[0]),x+w)


def cross(a,b,c,d):
    if a[1] == b[1] and c[1] == d[1]:
        return a[1] == c[1] and max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0]))
    if a[0] == b[0] and c[0] == d[0]:
        return a[0] == c[0] and max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1]))
    if a[0] == b[0]:
        return cross(c,d,a,b)
    return min(a[0],b[0]) <= c[0] <= max(a[0],b[0]) and min(c[1],d[1]) <= a[1] <= max(c[1],d[1])


segments = [(f['id'],a,b) for f in EDGES for a,b in zip(f['points'],f['points'][1:])]
for i,(fid,a,b) in enumerate(segments):
    assert a[0] == b[0] or a[1] == b[1]
    for other,c,d in segments[i+1:]:
        if fid != other:
            assert not cross(a,b,c,d), ('Crossed arrows',fid,other,a,b,c,d)
    for nid,n in NODES.items():
        if n['kind'] != 'system':
            assert not hit((n['x'],n['y'],n['w'],n['h']),a,b), ('Arrow through node',fid,nid)
    for lid,rect in LABELS:
        if lid != fid:
            assert not hit(rect,a,b), ('Arrow through label',fid,lid)
for i,(fid,a) in enumerate(LABELS):
    for other,b in LABELS[i+1:]:
        assert not (a[0]<b[0]+b[2] and a[0]+a[2]>b[0] and a[1]<b[1]+b[3] and a[1]+a[3]>b[1]), ('Label overlap',fid,other)
    for nid,n in NODES.items():
        if n['kind'] != 'system':
            assert not (a[0]<n['x']+n['w'] and a[0]+a[2]>n['x'] and a[1]<n['y']+n['h'] and a[1]+a[3]>n['y']), ('Label through node',fid,nid)
assert len([n for n in NODES.values() if n['kind']=='module']) == 5
assert len(EDGES) == 20
for f in EDGES:
    assert any(g['source']==f['target'] and g['target']==f['source'] for g in EDGES), ('Missing response',f)
client_flows = [f for f in EDGES if 'client' in {f['source'],f['target']}]
assert len(client_flows) == 6 and all(f['planned'] for f in client_flows)
assert {f['target'] for f in client_flows if f['source']=='client'} == {'access','visualization','estimation'}
assert not any({f['source'],f['target']} == {'client','designer'} for f in EDGES)
assert {f['tag'] for f in client_flows} == {'client-sign-in','client-access-result','client-view-layout','client-layout-result','client-view-cost','client-cost-result'}
SVG.append('</svg>')
FILE = OUT/'ved-theoretical-framework-2026-10-20.drawio'
ET.indent(MX)
ET.ElementTree(MX).write(FILE, encoding='utf-8', xml_declaration=True)
parsed = ET.parse(FILE)
cells = parsed.findall('.//mxCell')
ids = {c.attrib['id'] for c in cells}
assert len(ids) == len(cells)
for c in cells:
    assert c.attrib.get('parent','0') in ids
    if c.attrib.get('edge') == '1':
        assert c.attrib['source'] in ids and c.attrib['target'] in ids
assert not any('shape=image' in c.attrib.get('style','') for c in cells)
IM.save(OUT/'ved-theoretical-framework.png')
(OUT/'ved-theoretical-framework.svg').write_text(''.join(SVG), encoding='utf-8')
(OUT/'preview.html').write_text('<!doctype html><html><meta charset="utf-8"><title>VED theoretical framework</title><style>body{margin:0;background:#ddd}svg{display:block;width:100%;max-width:1840px;margin:auto;background:white}</style>'+''.join(SVG)+'</html>', encoding='utf-8')
(OUT/'framework-data.json').write_text(json.dumps({'nodes':NODES,'flows':EDGES},indent=2),encoding='utf-8')
report = {'pages':1,'modules':5,'flows':20,'client_request_response_pairs':3,'client_scope':'Sign-in; authorized saved 2D/3D layout viewing; stored estimate viewing only',
          'client_status':'Planned','direct_client_system_access':'PASS','client_restrictions':'PASS','paired_arrows':'PASS',
          'crossed_arrows':0,'arrow_node_collisions':0,'arrow_label_collisions':0,'overlapping_labels':0,'text_fit':'PASS','editable_xml':'PASS',
          'visual_review':'PENDING','editor_import':'NOT TESTED','downloads_copy':'PENDING',
          'source_reference_sha256':hashlib.sha256(Path('C:/Users/kupal/Downloads/ref.pdf').read_bytes()).hexdigest(),
          'source_image_sha256':hashlib.sha256(Path('C:/Users/kupal/Downloads/Theodore Framework (1).png').read_bytes()).hexdigest()}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
