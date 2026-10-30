"""Compact four-part physical ERD using matching entity continuation connectors."""
import ast
import heapq
import html
import itertools
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
DATA = json.loads((OUT / 'schema-metadata.json').read_text(encoding='utf-8'))
TABLES = {t['name']: t for t in DATA['tables']}
GRID, TW, HEAD, ROW, KEY = 8, 360, 28, 24, 64
PARTS = [
    ('A', 'Accounts and projects', [
        ['roles', 'users', 'dataset_approver_assignments'],
        ['projects', 'project_floors', 'floor_elevation_settings'],
        ['floor_plans', 'floor_plan_sources', 'floor_plan_pages', 'page_scale_settings'],
    ]),
    ('B', 'Processing and AI', [
        ['processing_jobs', 'processing_job_attempts', 'processing_job_cancellations'],
        ['processing_artifacts', 'interpretation_page_outcomes', 'floor_plan_interpretation_reviews'],
        ['floor_plan_interpretation_runs', 'interpretation_releases'],
    ]),
    ('C', 'Symbols and layouts', [
        ['symbol_legends', 'symbol_legend_history', 'manual_symbols'],
        ['detected_symbols', 'detection_reviews', 'detection_class_corrections'],
        ['walls', 'layout_versions', 'layout_save_requests'],
    ]),
    ('D', 'Routing and estimates', [
        ['materials', 'material_prices'],
        ['estimates', 'estimate_items'],
        ['generated_route_versions', 'estimate_sources'],
    ]),
]
CODE, OWNER = {}, {}
for letter, title, columns in PARTS:
    for i, name in enumerate([n for col in columns for n in col], 1):
        CODE[name] = f'{letter}{i}'
        OWNER[name] = letter
assert set(CODE) == set(TABLES)

EDGES = []
for name, t in TABLES.items():
    for fk in t['foreign_keys']:
        assert len(fk['constrained_columns']) == 1
        col = fk['constrained_columns'][0]
        idx = next(i for i, c in enumerate(t['columns']) if c['name'] == col)
        unique_sets = [set(t['primary_key'])] + [set(u['column_names']) for u in t['unique_constraints']]
        EDGES.append({'id': f'fk-{len(EDGES)+1:02d}', 'child': name, 'parent': fk['referred_table'],
                      'column': col, 'column_index': idx, 'required': not t['columns'][idx]['nullable'],
                      'unique': any(u and u.issubset({col}) for u in unique_sets)})

# Reuse the existing orthogonal routing implementation without running its old layout.
source = ast.parse((OUT / 'build_connected_erd.py').read_text(encoding='utf-8'))
selected = {'cells_between', 'available_port', 'find_route', 'reserve', 'compress'}
functions = ast.Module(body=[n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in selected], type_ignores=[])
exec(compile(functions, '<existing-erd-router>', 'exec'), globals())

def port_options(e, parent=False):
    b = BOXES[e['parent'] if parent else e['child']]
    x, y, w, h = b['x'], b['y'], b['w'], b['h']
    if not parent:
        cy = y + HEAD + e['column_index'] * ROW + ROW / 2
        for side, px, ex in [('right', x+w+24, x+w), ('left', x-24, x)]:
            yield {'point': (px//GRID, int(cy)//GRID), 'end': (ex, cy), 'side': side}
    else:
        for cx in range(x+24, x+w-16, 24):
            yield {'point': (cx//GRID, (y-24)//GRID), 'end': (cx, y), 'side': 'top'}
            yield {'point': (cx//GRID, math.ceil((y+h+24)/GRID)), 'end': (cx, y+h), 'side': 'bottom'}
        for cy in range(y+16, y+h-8, 24):
            yield {'point': ((x-24)//GRID, cy//GRID), 'end': (x, cy), 'side': 'left'}
            yield {'point': ((x+w+24)//GRID, cy//GRID), 'end': (x+w, cy), 'side': 'right'}

def rect_hits(rect, a, b):
    x, y, w, h = rect
    if a[0] == b[0]:
        return x < a[0] < x+w and max(min(a[1], b[1]), y) < min(max(a[1], b[1]), y+h)
    return y < a[1] < y+h and max(min(a[0], b[0]), x) < min(max(a[0], b[0]), x+w)

def intersects(a, b, c, d):
    ax, ay = a; bx, by = b; cx, cy = c; dx, dy = d
    if ay == by and cy == dy:
        return ay == cy and max(min(ax,bx),min(cx,dx)) <= min(max(ax,bx),max(cx,dx))
    if ax == bx and cx == dx:
        return ax == cx and max(min(ay,by),min(cy,dy)) <= min(max(ay,by),max(cy,dy))
    if ax == bx:
        return intersects(c,d,a,b)
    return min(ax,bx) <= cx <= max(ax,bx) and min(cy,dy) <= ay <= max(cy,dy)

def badge_for(e, occupied, prefer='right'):
    b = BOXES[e['child']]
    cy = int(b['y'] + HEAD + e['column_index']*ROW + ROW/2)
    for side in [prefer, 'left' if prefer == 'right' else 'right']:
        ex = b['x']+b['w'] if side == 'right' else b['x']
        direction = 1 if side == 'right' else -1
        cx = ex + direction*56
        end = (cx-direction*16,cy)
        rect = (cx-16,cy-10,32,20)
        x1,x2 = sorted((round(ex/GRID),round(cx/GRID)))
        iy = round(cy/GRID)
        if occupied[iy-1:iy+2, max(0,x1-2):x2+3].any():
            continue
        if any(rect_hits(rect, (bb['x'],bb['y']), (bb['x']+bb['w'],bb['y'])) for bb in BOXES.values()):
            continue
        occupied[iy-1:iy+2,max(0,x1-2):x2+3] = True
        return {'code': CODE[e['parent']], 'points': [(ex,cy),end], 'rect': rect, 'side': side}
    return None

LAYOUTS=[]
for letter, title, columns in PARTS:
    BOXES={}
    for column, names in enumerate(columns):
        y=200
        for name in names:
            h=HEAD+ROW*len(TABLES[name]['columns'])
            BOXES[name]={'x':72+column*480,'y':y,'w':TW,'h':h}
            y=math.ceil((y+h+72)/GRID)*GRID
    content_bottom=max(b['y']+b['h'] for b in BOXES.values())
    local=[e for e in EDGES if e['child'] in BOXES and e['parent'] in BOXES]
    remote=[e for e in EDGES if e['child'] in BOXES and e['parent'] not in BOXES]
    W=1520; H=math.ceil((content_bottom+240)/GRID)*GRID
    NX,NY=W//GRID+1,H//GRID+1
    node_mask=np.zeros((NY,NX),dtype=np.bool_)
    for b in BOXES.values():
        x1,y1=math.floor((b['x']-8)/GRID),math.floor((b['y']-8)/GRID)
        x2,y2=math.ceil((b['x']+b['w']+8)/GRID),math.ceil((b['y']+b['h']+8)/GRID)
        node_mask[y1:y2+1,x1:x2+1]=True
    node_mask[:24,:]=True
    node_mask[math.floor((content_bottom+80)/GRID):,:]=True
    occupied=np.zeros_like(node_mask)
    badges={}; routes={}
    for e in remote:
        badge=badge_for(e,occupied)
        assert badge,('No external badge',letter,e)
        badges[e['id']]=badge
    def dist(e):
        a,b=BOXES[e['child']],BOXES[e['parent']]
        return abs(a['x']-b['x'])+abs(a['y']-b['y'])
    for e in sorted(local,key=dist):
        route=find_route(e,occupied)
        if route:
            reserve(route,occupied)
            route['points']=compress([route['source']['end']]+[(x*GRID,y*GRID) for x,y in route['grid']]+[route['target']['end']])
            routes[e['id']]=route
        else:
            badge=badge_for(e,occupied)
            assert badge,('No internal continuation',letter,e)
            badges[e['id']]=badge
    references=sorted({b['code'] for b in badges.values()},key=lambda c:(c[0],int(c[1:])))
    # Crop the footer to exactly the reference directory needed on this part.
    footer_h=40+math.ceil(len(references)/3)*26+50
    H=math.ceil((content_bottom+80+footer_h)/GRID)*GRID
    lines=[]
    for eid,r in routes.items():
        lines += [(eid,a,b) for a,b in zip(r['points'],r['points'][1:])]
    for eid,badge in badges.items():
        lines.append((eid,*badge['points']))
    for i,(eid,a,b) in enumerate(lines):
        assert a[0]==b[0] or a[1]==b[1]
        for eid2,c,d in lines[i+1:]:
            if eid!=eid2:
                assert not intersects(a,b,c,d),('Crossed lines',letter,eid,eid2)
        for name,box in BOXES.items():
            assert not rect_hits((box['x'],box['y'],box['w'],box['h']),a,b),('Line through table',eid,name)
        for bid,badge in badges.items():
            if eid!=bid:
                assert not rect_hits(badge['rect'],a,b),('Line through connector',eid,bid)
    print(f'Part {letter}: {len(BOXES)} tables, {len(routes)} direct, {len(badges)} connectors, {W}x{H}',flush=True)
    LAYOUTS.append({'letter':letter,'title':title,'width':W,'height':H,'boxes':BOXES,
                    'routes':routes,'badges':badges,'references':references,'footer_y':content_bottom+80})

# Native diagrams.net cells and previews use identical measured geometry.
MX=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','version':'24.7.17'})
COUNTER=0;FONT_CACHE={};all_fields=[];all_relationships=[];svgs=[];images=[]
def font(size,bold=False):
    key=(size,bold)
    if key not in FONT_CACHE:
        FONT_CACHE[key]=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
    return FONT_CACHE[key]

def cell(value,x,y,w,h,size=13,bold=False,fill='white',border=True,parent='1',px=0,py=0,align='left',ellipse=False,cid=None):
    global COUNTER
    COUNTER+=1;cid=cid or f'v{COUNTER}'
    style=f'whiteSpace=wrap;html=0;rounded=0;fontFamily=Arial;fontSize={size};fontStyle={1 if bold else 0};fontColor=#111111;fillColor={fill};strokeColor={"#555555" if border else "none"};spacing=3;align={align};'
    if ellipse:style+='ellipse;'
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':value,'vertex':'1','parent':parent,'style':style})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    stroke='#555' if border else 'none'
    if ellipse:
        SVG.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{stroke}"/>')
        PEN.ellipse((x,y,x+w,y+h),fill=fill,outline='#555555' if border else None)
    else:
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="0.7"/>')
        PEN.rectangle((x,y,x+w,y+h),fill=fill,outline='#555555' if border else None)
    lines=value.split('\n');lh=size+3
    assert len(lines)*lh<=h+3,('Text height',value)
    for i,line in enumerate(lines):
        fw=font(size,bold).getlength(line)
        assert fw<=w-5,('Text width',line,w,fw)
        tx=x+3 if align=='left' else x+(w-fw)/2
        ty=y+(h-len(lines)*lh)/2+i*lh
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="#111">{html.escape(line)}</text>')
        PEN.text((tx,ty),line,font=font(size,bold),fill='#111')
    return cid

def line(points):
    SVG.append('<path d="'+' '.join(('M' if i==0 else 'L')+f' {x} {y}' for i,(x,y) in enumerate(points))+'" fill="none" stroke="#222" stroke-width="1.1"/>')
    PEN.line([tuple(p) for p in points],fill='#222',width=1)

def marker(end,nxt,kind):
    ex,ey=end;dx,dy=nxt[0]-ex,nxt[1]-ey;length=math.hypot(dx,dy)
    ux,uy=dx/length,dy/length;vx,vy=-uy,ux
    def p(a,b=0):return ex+a*ux+b*vx,ey+a*uy+b*vy
    def bar(a):line([p(a,-4),p(a,4)])
    def circ(a):
        cx,cy=p(a);SVG.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="white" stroke="#222"/>')
        PEN.ellipse((cx-2.5,cy-2.5,cx+2.5,cy+2.5),fill='white',outline='#222')
    if kind=='many':
        for b in (-4,0,4):line([p(0,b),p(8)])
        circ(12)
    elif kind=='optional':bar(3);circ(10)
    else:bar(3);bar(7)

EDGE_MAP={e['id']:e for e in EDGES}
for layout in LAYOUTS:
    letter,title,W,H=layout['letter'],layout['title'],layout['width'],layout['height']
    boxes=layout['boxes']
    diagram=ET.SubElement(MX,'diagram',{'id':'part-'+letter,'name':f'Part {letter} - {title}'})
    model=ET.SubElement(diagram,'mxGraphModel',{'dx':str(W),'dy':str(H),'grid':'1','gridSize':'8','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(W),'pageHeight':str(H),'background':'#FFFFFF'})
    ROOT=ET.SubElement(model,'root');ET.SubElement(ROOT,'mxCell',{'id':'0'});ET.SubElement(ROOT,'mxCell',{'id':'1','parent':'0'})
    SVG=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Part {letter}: {html.escape(title)}"><rect width="{W}" height="{H}" fill="white"/>']
    IMAGE=Image.new('RGB',(W,H),'white');PEN=ImageDraw.Draw(IMAGE)
    cell('VED ELECTRICAL SERVICES / ENTITY RELATIONSHIP DIAGRAM',56,22,W-112,26,size=14,bold=True,border=False)
    cell(f'Part {letter}. {title}',56,56,W-112,44,size=27,bold=True,border=False)
    cell('A Accounts & projects   /   B Processing & AI   /   C Symbols & layouts   /   D Routing & estimates',56,106,W-112,26,size=14,border=False)
    cell('Match oval connectors to the same code in a table header. Example: A2 = users in Part A.',56,140,W-112,27,size=14,border=False)
    for name,box in boxes.items():
        c=ET.SubElement(ROOT,'mxCell',{'id':'table-'+name,'value':'','vertex':'1','parent':'1','style':'group;','erdTable':name})
        ET.SubElement(c,'mxGeometry',{'x':str(box['x']),'y':str(box['y']),'width':str(box['w']),'height':str(box['h']),'as':'geometry'})
    for eid,r in layout['routes'].items():
        e=EDGE_MAP[eid];a,b=boxes[e['child']],boxes[e['parent']];start,end=r['points'][0],r['points'][-1]
        style='edgeStyle=none;rounded=0;html=0;strokeColor=#222222;strokeWidth=1.1;'
        style+=f'startArrow={"ERzeroToOne" if e["unique"] else "ERzeroToMany"};endArrow={"ERone" if e["required"] else "ERzeroToOne"};startSize=8;endSize=8;'
        style+=f'exitX={(start[0]-a["x"])/a["w"]};exitY={(start[1]-a["y"])/a["h"]};entryX={(end[0]-b["x"])/b["w"]};entryY={(end[1]-b["y"])/b["h"]};exitPerimeter=0;entryPerimeter=0;'
        c=ET.SubElement(ROOT,'mxCell',{'id':'edge-'+eid,'value':'','edge':'1','parent':'1','source':'table-'+e['child'],'target':'table-'+e['parent'],'style':style,'erdRelationship':eid})
        geo=ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=ET.SubElement(geo,'Array',{'as':'points'})
        for x,y in r['points'][1:-1]:ET.SubElement(arr,'mxPoint',{'x':str(x),'y':str(y)})
        line(r['points']);marker(start,r['points'][1],'optional' if e['unique'] else 'many');marker(end,r['points'][-2],'one' if e['required'] else 'optional')
        all_relationships.append(eid)
    for eid,badge in layout['badges'].items():
        e=EDGE_MAP[eid];rect=badge['rect'];start,end=badge['points']
        code_id=cell(badge['code'],*rect,size=10,bold=True,ellipse=True,align='center')
        a=boxes[e['child']]
        style=f'edgeStyle=none;rounded=0;html=0;strokeColor=#222222;strokeWidth=1.1;startArrow={"ERzeroToOne" if e["unique"] else "ERzeroToMany"};endArrow={"ERone" if e["required"] else "ERzeroToOne"};startSize=8;endSize=8;'
        style+=f'exitX={(start[0]-a["x"])/a["w"]};exitY={(start[1]-a["y"])/a["h"]};entryX={0 if badge["side"]=="right" else 1};entryY=0.5;exitPerimeter=0;entryPerimeter=0;'
        c=ET.SubElement(ROOT,'mxCell',{'id':'edge-'+eid,'value':'','edge':'1','parent':'1','source':'table-'+e['child'],'target':code_id,'style':style,'erdRelationship':eid,'erdTargetTable':e['parent'],'erdTargetCode':CODE[e['parent']]})
        ET.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
        line(badge['points']);marker(start,end,'optional' if e['unique'] else 'many');marker(end,start,'one' if e['required'] else 'optional')
        all_relationships.append(eid)
    for name,box in boxes.items():
        t=TABLES[name];x,y=box['x'],box['y'];par='table-'+name
        cell(CODE[name],x,y,38,HEAD,size=11,bold=True,fill='#F0F0F0',parent=par,px=x,py=y,align='center')
        cell(name,x+38,y,TW-38,HEAD,size=13,bold=True,fill='#F0F0F0',parent=par,px=x,py=y,align='center')
        fks={e['column'] for e in EDGES if e['child']==name}
        uniques={u['column_names'][0] for u in t['unique_constraints'] if len(u['column_names'])==1}
        for i,c in enumerate(t['columns']):
            keys=[]
            if c['name'] in t['primary_key']:keys.append('PK')
            if c['name'] in fks:keys.append('FK')
            if c['name'] in uniques and 'PK' not in keys:keys.append('UQ')
            cy=y+HEAD+i*ROW
            cell('/'.join(keys),x,cy,KEY,ROW,size=11,parent=par,px=x,py=y)
            cell(c['name']+(' ?' if c['nullable'] else ''),x+KEY,cy,TW-KEY,ROW,size=13,parent=par,px=x,py=y)
            all_fields.append((name,c['name']))
        if name=='interpretation_releases':
            cell('No declared foreign keys.',x,y+box['h']+8,TW,24,size=12,border=False)
    fy=layout['footer_y']
    if layout['references']:
        cell('CONTINUATION CONNECTORS',56,fy,W-112,25,size=13,bold=True,border=False)
        for i,code in enumerate(layout['references']):
            name=next(n for n,c in CODE.items() if c==code)
            cell(f'{code}  {name}  (Part {code[0]})',72+(i%3)*480,fy+30+(i//3)*26,450,26,size=12,border=False)
    cell('PK primary key  |  FK foreign key  |  UQ unique  |  ? optional field  |  Crow\'s foot: zero or many; double bar: one; circle + bar: zero or one',56,H-40,W-112,25,size=11,border=False)
    SVG.append('</svg>');svgs.append(''.join(SVG));images.append(IMAGE)
    (OUT/f'part-{letter.lower()}.svg').write_text(svgs[-1],encoding='utf-8');IMAGE.save(OUT/f'part-{letter.lower()}.png')

ET.indent(MX)
ET.ElementTree(MX).write(OUT/'ved-electrical-erd.drawio',encoding='utf-8',xml_declaration=True)
preview=['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED — four-part ERD</title><style>body{margin:0;background:#e6e6e6;color:#111;font-family:Arial}nav{position:sticky;top:0;padding:15px;background:white;z-index:1}nav a{margin-right:20px;color:#174d78}button{margin-left:12px;padding:6px 12px}section{margin:18px auto;max-width:1520px;background:white}svg{display:block;width:100%;height:auto}body.actual section{width:1520px;max-width:none;margin-left:20px}@media print{nav{display:none}body{background:white}section{margin:0;break-after:page;max-width:none}@page{size:A3 portrait;margin:8mm}}</style><nav><strong>VED — four connected ERD parts</strong><br>']
for letter,title,_ in PARTS:preview.append(f'<a href="#part-{letter}">Part {letter}: {html.escape(title)}</a>')
preview.append('<button onclick="document.body.classList.remove(\'actual\')">Fit width</button><button onclick="document.body.classList.add(\'actual\')">Readable size</button></nav>')
for (letter,_,_),svg in zip(PARTS,svgs):preview.append(f'<section id="part-{letter}">{svg}</section>')
preview.append('</html>');(OUT/'ved-electrical-erd-preview.html').write_text('\n'.join(preview),encoding='utf-8')
thumbs=[]
for im in images:
    thumb=im.copy();thumb.thumbnail((760,800));thumbs.append(thumb)
row_heights=[max(thumbs[i].height,thumbs[i+1].height) for i in (0,2)]
overview=Image.new('RGB',(1540,sum(row_heights)+30),'#D6D6D6');y=10
for row in range(2):
    for col in range(2):overview.paste(thumbs[row*2+col],(10+col*770,y))
    y+=row_heights[row]+10
overview.save(OUT/'four-parts-overview.png')
overview.save(OUT/'ved-electrical-erd.png')
overview_svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1540" height="{sum(row_heights)+30}" viewBox="0 0 1540 {sum(row_heights)+30}"><rect width="100%" height="100%" fill="#D6D6D6"/>']
oy=10
for row in range(2):
    for col in range(2):
        i=row*2+col
        nested=svgs[i].replace('<svg ',f'<svg x="{10+col*770}" y="{oy}" width="{thumbs[i].width}" height="{thumbs[i].height}" ',1)
        overview_svg.append(nested)
    oy+=row_heights[row]+10
overview_svg.append('</svg>')
(OUT/'ved-electrical-erd.svg').write_text(''.join(overview_svg),encoding='utf-8')

expected_fields={(t['name'],c['name']) for t in TABLES.values() for c in t['columns']}
assert len(all_fields)==len(expected_fields)==303 and set(all_fields)==expected_fields
assert len(all_relationships)==len(set(all_relationships))==60
assert set(all_relationships)=={e['id'] for e in EDGES}
parsed=ET.parse(OUT/'ved-electrical-erd.drawio');assert len(parsed.findall('diagram'))==4
for diagram in parsed.findall('diagram'):
    ids={c.attrib['id'] for c in diagram.findall('.//mxCell')}
    for edge in diagram.findall('.//mxCell[@edge="1"]'):
        assert edge.attrib['source'] in ids and edge.attrib['target'] in ids
old_area=3864*4340;new_area=sum(p['width']*p['height'] for p in LAYOUTS)
report={'parts':4,'tables':33,'columns':303,'foreign_keys':60,'direct_within_part':sum(len(p['routes']) for p in LAYOUTS),
        'continuation_relationships':sum(len(p['badges']) for p in LAYOUTS),'line_crossings':0,'line_table_collisions':0,
        'line_connector_collisions':0,'text_fit':'PASS','xml_parse':'PASS','complete_schema_coverage':'PASS',
        'canvas_area_reduction_percent':round((1-new_area/old_area)*100,1),'diagrams_net_editor_import':'NOT TESTED',
        'parts_directory':{p['letter']:{'title':p['title'],'tables':list(p['boxes']),'size':[p['width'],p['height']]} for p in LAYOUTS}}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'parts-layout.json').write_text(json.dumps({'parts':LAYOUTS,'codes':CODE,'relationships':EDGES},indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
