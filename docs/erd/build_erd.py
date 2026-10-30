"""Build a native, editable diagrams.net ERD from the captured database metadata."""
import html
import json
import math
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
DATA = json.loads((OUT / 'schema-metadata.json').read_text(encoding='utf-8'))
TABLES = {t['name']: t for t in DATA['tables']}
W, H = 1160, 1640
LEFT, TW, REF_X, REF_W = 40, 590, 820, 300
FONT = 'Arial'
DESCRIPTIONS = {
    'roles': 'Application permission roles, such as ADMIN and DESIGNER.',
    'users': 'External OAuth/OIDC identities mapped to local application roles.',
    'dataset_approver_assignments': 'Who is authorized to approve datasets, and who granted or ended that authority.',
    'projects': 'Project ownership and basic project information.',
    'project_floors': 'Named and ordered floors belonging to a project.',
    'floor_plans': 'Uploaded floor plan records and original-file locations.',
    'floor_plan_sources': 'Original-file identity and checksum for each uploaded plan.',
    'floor_plan_pages': 'Individual pages belonging to an original floor plan source.',
    'page_scale_settings': 'Reviewed page scale used to convert pixel measurements to meters.',
    'floor_elevation_settings': 'Reviewed elevation of a project floor, measured in meters.',
    'processing_jobs': 'Queued analysis work, progress, and completion or failure status.',
    'processing_job_attempts': 'Worker attempts, leases, and heartbeat information for each job.',
    'processing_job_cancellations': 'Cancellation requests and their resolution for a processing job.',
    'processing_artifacts': 'Files produced by processing, with checksums, page identity, and dimensions.',
    'floor_plan_interpretation_runs': 'Candidate AI interpretation tied to a job, page, and source artifact.',
    'interpretation_page_outcomes': 'Per-page processing outcome and candidate provenance.',
    'floor_plan_interpretation_reviews': 'Versioned designer decisions about an AI interpretation.',
    'interpretation_releases': 'Local model release identity, approval evidence, activation, and rollback history.',
    'symbol_legends': 'Approved electrical symbol classes available to the application.',
    'symbol_legend_history': 'Audited changes to the symbol legend and the user who made each change.',
    'detected_symbols': 'Original detected classes, confidence scores, and positions kept for review.',
    'walls': 'Detected wall candidates in both image pixels and canonical meter coordinates.',
    'detection_reviews': 'Ordered user decisions on a detected symbol.',
    'detection_class_corrections': 'History of class corrections, preserving old and new legend information.',
    'manual_symbols': 'Symbols manually placed by a user, including class and image coordinates.',
    'layout_versions': 'Saved canonical geometry shared by the 2D editor and 3D viewer.',
    'layout_save_requests': 'Save request identity and the layout version created by that request.',
    'generated_route_versions': 'Versioned routing configuration, layout references, and calculated results.',
    'materials': 'Material catalog and measurement units; prices are stored separately.',
    'material_prices': 'Versioned material prices and the user responsible for each price change.',
    'estimates': 'Saved project estimate totals, currency, and version number.',
    'estimate_items': 'Estimate lines with quantity and the captured unit price used for that estimate.',
    'estimate_sources': 'One optional source snapshot per estimate, with request identity.',
}
GROUPS = [
    ('Accounts and authority', ['roles', 'users', 'dataset_approver_assignments']),
    ('Projects and uploads', ['projects', 'project_floors', 'floor_plans']),
    ('Source pages and scale', ['floor_plan_sources', 'floor_plan_pages', 'page_scale_settings']),
    ('Floor elevation and jobs', ['floor_elevation_settings', 'processing_jobs']),
    ('Worker execution', ['processing_job_attempts', 'processing_job_cancellations']),
    ('Processing artifacts and AI runs', ['processing_artifacts', 'floor_plan_interpretation_runs']),
    ('AI outcomes and review', ['interpretation_page_outcomes', 'floor_plan_interpretation_reviews']),
    ('Model release register', ['interpretation_releases']),
    ('Symbol legend administration', ['symbol_legends', 'symbol_legend_history']),
    ('Detected symbols and walls', ['detected_symbols', 'walls']),
    ('Detection review and corrections', ['detection_reviews', 'detection_class_corrections']),
    ('Manual symbol placement', ['manual_symbols']),
    ('Canonical layouts and saves', ['layout_versions', 'layout_save_requests']),
    ('Generated electrical routes', ['generated_route_versions']),
    ('Materials and price history', ['materials', 'material_prices']),
    ('Estimate snapshots', ['estimates', 'estimate_items', 'estimate_sources']),
]

def unique_sets(table):
    return [set(table['primary_key'])] + [set(u['column_names']) for u in table['unique_constraints']]

def key_labels(table):
    labels = {c['name']: [] for c in table['columns']}
    for c in table['primary_key']:
        labels[c].append('PK')
    for fk in table['foreign_keys']:
        for c in fk['constrained_columns']:
            labels[c].append('FK')
    composite = []
    for u in table['unique_constraints']:
        if len(u['column_names']) == 1:
            labels[u['column_names'][0]].append('UQ')
        else:
            composite.append('UQ together: ' + ' + '.join(u['column_names']))
    return labels, composite

def table_height(table):
    fkcols = {c for f in table['foreign_keys'] for c in f['constrained_columns']}
    _, composite = key_labels(table)
    return 44 + 36 + 26 + sum(64 if c['name'] in fkcols else 26 for c in table['columns']) + 18 + 22 * len(composite) + 36

pages = [{'title': 'How to read this ERD', 'tables': []}]
for title, names in GROUPS:
    current = []
    height = 0
    part = 1
    for name in names:
        needed = table_height(TABLES[name])
        if current and height + needed > H - 220:
            pages.append({'title': title + (f' - continuation {part}' if part > 1 else ''), 'tables': current})
            current, height = [], 0
            part += 1
        current.append(name)
        height += needed
    pages.append({'title': title + (f' - continuation {part}' if part > 1 else ''), 'tables': current})
TABLE_PAGE = {name: i + 1 for i, p in enumerate(pages) for name in p['tables']}
mxfile = ET.Element('mxfile', {'host': 'app.diagrams.net', 'type': 'device', 'version': '24.7.17'})
render_pages = []
all_columns, all_edges, all_full_tables = [], [], []
uid = 0

def cell(root, value, x, y, w, h, style='', parent='1', extra=None):
    global uid
    uid += 1
    attrs = {'id': f'c{uid}', 'value': value, 'vertex': '1', 'parent': parent,
             'style': 'rounded=0;whiteSpace=wrap;html=0;fontFamily=Arial;fontSize=13;'
                      'fontColor=#17212B;strokeColor=#64748B;fillColor=#FFFFFF;spacing=6;' + style}
    if extra:
        attrs.update(extra)
    c = ET.SubElement(root, 'mxCell', attrs)
    ET.SubElement(c, 'mxGeometry', {'x': str(x), 'y': str(y), 'width': str(w), 'height': str(h), 'as': 'geometry'})
    return c.attrib['id']

def draw_rect(root, shapes, value, x, y, w, h, fill='#FFFFFF', size=13, bold=False, align='left', border=True, extra=None):
    sty = f'fillColor={fill};fontSize={size};align={align};fontStyle={1 if bold else 0};'
    if not border:
        sty += 'strokeColor=none;'
    cid = cell(root, value, x, y, w, h, sty, extra=extra)
    shapes.append({'kind': 'rect', 'value': value, 'x': x, 'y': y, 'w': w, 'h': h,
                   'fill': fill, 'size': size, 'bold': bold, 'align': align, 'border': border, 'id': cid})
    return cid

def text(root, shapes, value, x, y, w, h, size=13, bold=False, align='left'):
    return draw_rect(root, shapes, value, x, y, w, h, size=size, bold=bold, align=align, border=False)

def add_table(root, shapes, table, y, page_number):
    name = table['name']
    all_full_tables.append(name)
    title_y = y
    draw_rect(root, shapes, name, LEFT, y, TW, 36, '#E8EDF2', 16, True,
              extra={'erdTable': name})
    text(root, shapes, DESCRIPTIONS[name], LEFT, y + 38, W - 80, 38, 13)
    y += 80
    widths = [64, 294, 144, 88]
    xpositions = [LEFT, LEFT+64, LEFT+358, LEFT+502]
    for title, x, width in zip(['KEY', 'COLUMN NAME', 'DATA TYPE', 'NULL?'], xpositions, widths):
        draw_rect(root, shapes, title, x, y, width, 26, '#F3F5F7', 12, True)
    text(root, shapes, 'RELATED TABLE / CONTINUATION', REF_X, y, REF_W, 26, 11, True)
    y += 26
    labels, composite = key_labels(table)
    fkmap = {c: f for f in table['foreign_keys'] for c in f['constrained_columns']}
    for c in table['columns']:
        fk = fkmap.get(c['name'])
        rh = 64 if fk else 26
        datatype = c['type'].split(' COLLATE')[0].replace(', ', ',')
        values = ['/'.join(labels[c['name']]), c['name'], datatype, 'Yes' if c['nullable'] else 'No']
        row_ids = []
        for colidx, (value, x, width) in enumerate(zip(values, xpositions, widths)):
            row_ids.append(draw_rect(root, shapes, value, x, y, width, rh,
                                      '#F4F7FA' if fk else '#FFFFFF', 12 if colidx == 0 else 13,
                                      colidx == 0, extra={'erdColumn': c['name'], 'erdTable': name} if colidx == 1 else None))
        all_columns.append((name, c['name']))
        if fk:
            assert len(fk['constrained_columns']) == 1, 'Composite FK needs a grouped connector.'
            target_name = fk['referred_table']
            target_cols = ', '.join(fk['referred_columns'])
            target_page = TABLE_PAGE[target_name]
            ref_value = f'{target_name}\nPK: {target_cols}   |   See page {target_page:02d}'
            ref_id = draw_rect(root, shapes, ref_value, REF_X, y+5, REF_W, rh-10,
                               '#FFFFFF', 13, extra={'erdReference': target_name, 'erdPage': str(target_page)})
            unique_child = any(s and s.issubset(set(fk['constrained_columns'])) for s in unique_sets(table))
            child_mark = 'ERzeroToOne' if unique_child else 'ERzeroToMany'
            parent_mark = 'ERzeroToOne' if c['nullable'] else 'ERone'
            child_label = '0..1' if unique_child else '0..many'
            parent_label = '0..1' if c['nullable'] else '1'
            global uid
            uid += 1
            edge_id = f'e{uid}'
            edge = ET.SubElement(root, 'mxCell', {
                'id': edge_id, 'value': '', 'edge': '1', 'parent': '1', 'source': row_ids[-1], 'target': ref_id,
                'erdForeignKey': fk['name'] or f'{name}.{c["name"]}',
                'style': f'edgeStyle=none;rounded=0;html=0;strokeColor=#334155;strokeWidth=1.3;'
                         f'startArrow={child_mark};endArrow={parent_mark};startSize=12;endSize=12;'
                         'exitX=1;exitY=0.5;exitPerimeter=0;entryX=0;entryY=0.5;entryPerimeter=0;'
                         'sourcePerimeterSpacing=0;targetPerimeterSpacing=0;'
            })
            ET.SubElement(edge, 'mxGeometry', {'relative': '1', 'as': 'geometry'})
            x1, x2, cy = LEFT+TW, REF_X, y+rh/2
            shapes.append({'kind': 'edge', 'x1': x1, 'x2': x2, 'y': cy, 'child': child_label, 'parent': parent_label})
            # Labels are above each line, not placed on or across it.
            text(root, shapes, child_label, x1+9, cy-25, 64, 19, 11)
            text(root, shapes, parent_label, x2-49, cy-25, 40, 19, 11, align='right')
            all_edges.append({'page': page_number, 'table': name, 'column': c['name'],
                              'target': target_name, 'x1': x1, 'x2': x2, 'y': cy,
                              'child': child_label, 'parent': parent_label})
        y += rh
    y += 8
    for note in composite:
        text(root, shapes, note, LEFT, y, W-80, 22, 12)
        y += 22
    if name == 'interpretation_releases':
        text(root, shapes, 'No declared foreign keys: similarly named ID fields are not drawn as database relationships.', LEFT, y, W-80, 28, 13)
        y += 28
    if name == 'generated_route_versions':
        text(root, shapes, 'Layout references and route geometry are inside JSON documents, not separate foreign-key tables.', LEFT, y, W-80, 28, 13)
        y += 28
    return max(y+36, title_y+table_height(table))

for index, page in enumerate(pages, 1):
    diagram = ET.SubElement(mxfile, 'diagram', {'id': f'page-{index:02d}', 'name': f'{index:02d} {page["title"]}'})
    model = ET.SubElement(diagram, 'mxGraphModel', {'dx': str(W), 'dy': str(H), 'grid': '1', 'gridSize': '10',
             'guides': '1', 'tooltips': '1', 'connect': '1', 'arrows': '1', 'fold': '1', 'page': '1',
             'pageScale': '1', 'pageWidth': str(W), 'pageHeight': str(H), 'math': '0', 'shadow': '0', 'background': '#FFFFFF'})
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', {'id': '0'})
    ET.SubElement(root, 'mxCell', {'id': '1', 'parent': '0'})
    shapes = []
    text(root, shapes, 'VED ELECTRICAL SERVICES', LEFT, 22, W-80, 26, 15, True)
    text(root, shapes, page['title'], LEFT, 54, W-80, 42, 26, True)
    text(root, shapes, 'ENTITY RELATIONSHIP DIAGRAM  /  Live XAMPP schema  /  07 October 2026', LEFT, 99, W-80, 26, 12)
    if index == 1:
        text(root, shapes, '33 tables   |   303 columns   |   60 foreign-key relationships', LEFT, 150, W-80, 38, 20, True)
        blocks = [
            ('What this diagram shows', 'The existing ved_electrical database, checked against the project models.\nEach full table appears once. Small related-table boxes repeat a key as a continuation reference.'),
            ('Read a relationship from left to right', 'The FK column on the left refers to the PK in the small box on the right.\nSee page NN tells you where that related table is shown in full.'),
            ('Keys and optional fields', 'PK = primary key: uniquely identifies a row.   FK = foreign key: refers to another table.\nUQ = unique value.   UQ together = the combination must be unique.   NULL? Yes = optional.'),
            ('Relationship counts', '1 = exactly one.   0..1 = zero or one.   0..many = zero or more.\nExample: many projects can refer to one user; each project must have one owner.'),
            ('Database details kept accurate', 'Only declared foreign keys have connectors. No relationship is inferred from a field name.\nMariaDB stores JSON as LONGTEXT; boolean fields appear as TINYINT. Full metadata accompanies this file.'),
        ]
        y = 212
        for title, description in blocks:
            text(root, shapes, title, LEFT, y, W-80, 28, 16, True)
            text(root, shapes, description, LEFT, y+29, W-80, 52, 14)
            y += 100
        text(root, shapes, 'PAGE DIRECTORY', LEFT, y+10, W-80, 32, 17, True)
        y += 58
        for j, p in enumerate(pages[1:]):
            col, row = divmod(j, 9)
            x = LEFT + col*550
            yy = y + row*69
            text(root, shapes, f'{j+2:02d}  {p["title"]}', x, yy, 530, 26, 14, True)
            names = ', '.join(p['tables'])
            text(root, shapes, names, x+27, yy+27, 505, 38, 12)
        text(root, shapes, 'Continuation boxes represent existing tables, not additional tables. Lines are relationships, not workflow arrows.', LEFT, H-105, W-80, 40, 13)
    else:
        y = 148
        for name in page['tables']:
            y = add_table(root, shapes, TABLES[name], y, index)
        assert y < H-90, (page['title'], y)
    text(root, shapes, f'PK primary key  |  FK foreign key  |  UQ unique  |  1 exactly one  |  0..1 optional one  |  0..many any number', LEFT, H-54, W-160, 26, 11)
    text(root, shapes, f'{index:02d} / {len(pages):02d}', W-110, H-54, 70, 26, 12, True, 'right')
    render_pages.append({'title': page['title'], 'shapes': shapes})

ET.indent(mxfile)
drawio = OUT / 'ved-electrical-erd.drawio'
ET.ElementTree(mxfile).write(drawio, encoding='utf-8', xml_declaration=True)

# Render the same geometry to SVG/HTML and PNG for a local, dependency-free preview.
font_dir = Path('C:/Windows/Fonts')
font_cache = {}
def font(size, bold=False):
    key = size, bold
    if key not in font_cache:
        font_cache[key] = ImageFont.truetype(str(font_dir / ('arialbd.ttf' if bold else 'arial.ttf')), size)
    return font_cache[key]

def lines_for(s):
    f = font(s['size'], s['bold'])
    result = []
    for para in s['value'].split('\n'):
        words = para.split(' ')
        line = ''
        for word in words:
            test = (line+' '+word).strip()
            if f.getlength(test) > s['w']-12 and line:
                result.append(line)
                line = word
            else:
                line = test
        result.append(line)
    assert len(result)*(s['size']+3) <= s['h']+4, (s['value'], s['h'], result)
    for line in result:
        assert f.getlength(line) <= s['w']-10, ('Text overflow', line, s['w'])
    return result

def er_mark_svg(x, y, cardinality, direction):
    # Direction points from the endpoint toward the middle of the connector.
    parts = []
    def line(a,b,c,d):
        parts.append(f'<path d="M {a} {b} L {c} {d}"/>')
    if cardinality == '0..many':
        for dy in (-7,0,7):
            line(x, y+dy, x+direction*12, y)
        parts.append(f'<circle cx="{x+direction*20}" cy="{y}" r="4" fill="white"/>')
    elif cardinality == '0..1':
        line(x+direction*5,y-7,x+direction*5,y+7)
        parts.append(f'<circle cx="{x+direction*16}" cy="{y}" r="4" fill="white"/>')
    else:
        line(x+direction*5,y-7,x+direction*5,y+7)
        line(x+direction*11,y-7,x+direction*11,y+7)
    return ''.join(parts)

svgs = []
for idx, page in enumerate(render_pages, 1):
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(page["title"])}">',
           f'<rect width="{W}" height="{H}" fill="white"/>']
    im = Image.new('RGB', (W,H), 'white')
    canvas = ImageDraw.Draw(im)
    for s in page['shapes']:
        if s['kind'] == 'edge':
            x1,x2,y = s['x1'],s['x2'],s['y']
            svg.append(f'<g stroke="#334155" stroke-width="1.3" fill="none"><path d="M {x1} {y} H {x2}"/>'+er_mark_svg(x1,y,s['child'],1)+er_mark_svg(x2,y,s['parent'],-1)+'</g>')
            canvas.line((x1,y,x2,y),fill='#334155',width=2)
            for x,direction,card in [(x1,1,s['child']),(x2,-1,s['parent'])]:
                if card == '0..many':
                    for dy in (-7,0,7):
                        canvas.line((x,y+dy,x+direction*12,y),fill='#334155',width=1)
                    cx=x+direction*20
                    canvas.ellipse((cx-4,y-4,cx+4,y+4),fill='white',outline='#334155')
                else:
                    canvas.line((x+direction*5,y-7,x+direction*5,y+7),fill='#334155',width=1)
                    if card == '0..1':
                        cx=x+direction*16
                        canvas.ellipse((cx-4,y-4,cx+4,y+4),fill='white',outline='#334155')
                    else:
                        canvas.line((x+direction*11,y-7,x+direction*11,y+7),fill='#334155',width=1)
            continue
        x,y,w,h=s['x'],s['y'],s['w'],s['h']
        stroke = '#64748B' if s['border'] else 'none'
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{s["fill"]}" stroke="{stroke}" stroke-width="0.7"/>')
        canvas.rectangle((x,y,x+w,y+h),fill=s['fill'],outline='#64748B' if s['border'] else None)
        lines=lines_for(s)
        lh=s['size']+3
        ty=y+(h-len(lines)*lh)/2
        for line in lines:
            fw=font(s['size'],s['bold']).getlength(line)
            tx=x+6 if s['align']=='left' else x+w-6-fw if s['align']=='right' else x+(w-fw)/2
            svg.append(f'<text x="{tx}" y="{ty+s["size"]}" font-family="Arial,sans-serif" font-size="{s["size"]}" font-weight="{700 if s["bold"] else 400}" fill="#17212B">{html.escape(line)}</text>')
            canvas.text((tx,ty),line,font=font(s['size'],s['bold']),fill='#17212B')
            ty+=lh
    svg.append('</svg>')
    svgs.append(''.join(svg))
    preview_dir=OUT/'preview'
    preview_dir.mkdir(exist_ok=True)
    im.save(preview_dir/f'page-{idx:02d}.png')
    (preview_dir/f'page-{idx:02d}.svg').write_text(svgs[-1],encoding='utf-8')

preview = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED Electrical ERD</title>',
           '<style>body{margin:0;background:#e7ebef;font-family:Arial,sans-serif;color:#17212b}nav{padding:20px;background:#fff}nav a{display:inline-block;margin:6px 12px 6px 0;color:#254d75}section{max-width:1160px;margin:24px auto;background:white;box-shadow:0 2px 12px #0002}svg{width:100%;display:block}@media print{nav{display:none}body{background:white}section{margin:0;box-shadow:none;break-after:page}@page{size:A3 portrait;margin:8mm}}</style>',
           '<nav><strong>VED Electrical Services — ERD</strong><br>Read-only preview. Open the .drawio file in diagrams.net to edit.<br>']
for idx,p in enumerate(pages,1):
    preview.append(f'<a href="#page-{idx}">{idx:02d} {html.escape(p["title"])}</a>')
preview.append('</nav>')
for idx,svg in enumerate(svgs,1):
    preview.append(f'<section id="page-{idx}">{svg}</section>')
preview.append('</html>')
(OUT/'ved-electrical-erd-preview.html').write_text('\n'.join(preview),encoding='utf-8')

# Structural coverage and geometric verification of every relationship corridor.
assert len(all_full_tables)==len(set(all_full_tables))==len(TABLES)
expected_cols={(t['name'],c['name']) for t in TABLES.values() for c in t['columns']}
assert set(all_columns)==expected_cols and len(all_columns)==len(expected_cols)
expected_edges={(t['name'],f['constrained_columns'][0],f['referred_table']) for t in TABLES.values() for f in t['foreign_keys']}
assert {(e['table'],e['column'],e['target']) for e in all_edges}==expected_edges
assert len(all_edges)==len(expected_edges)
for idx,page in enumerate(render_pages,1):
    edges=[e for e in all_edges if e['page']==idx]
    assert len({e['y'] for e in edges})==len(edges), 'Crossed/overlapping connectors'
    for edge in edges:
        for s in page['shapes']:
            if s['kind']!='rect':
                continue
            assert not (s['x'] < edge['x2'] and s['x']+s['w'] > edge['x1'] and s['y'] < edge['y'] < s['y']+s['h']), ('Connector intersects box or text', edge, s)
        assert edge['x2']-edge['x1'] >= 150
    for s in page['shapes']:
        if s['kind']=='rect':
            assert s['x']>=0 and s['y']>=0 and s['x']+s['w']<=W and s['y']+s['h']<=H
parsed=ET.parse(drawio)
assert len(parsed.findall('diagram'))==len(pages)
ids=[c.attrib['id'] for c in parsed.findall('.//mxCell') if c.attrib['id'] not in ('0','1')]
assert len(ids)==len(set(ids))
for edge in parsed.findall('.//mxCell[@edge="1"]'):
    assert edge.attrib['source'] in ids and edge.attrib['target'] in ids

report={'tables':len(all_full_tables),'columns':len(all_columns),'foreign_keys':len(all_edges),
        'pages':len(pages),'line_crossings':0,'connector_box_collisions':0,'text_overflows':0,
        'all_columns_present':True,'all_foreign_keys_present':True,'xml_parse':True,
        'database_model_comparison':DATA['model_comparison'],
        'page_directory':{f'{i:02d} {p["title"]}':p['tables'] for i,p in enumerate(pages,1)}}
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'layout.json').write_text(json.dumps(render_pages,indent=2),encoding='utf-8')

thumb_w,thumb_h=232,328
sheet=Image.new('RGB',(thumb_w*4,thumb_h*math.ceil(len(pages)/4)), '#D8DEE5')
for idx in range(len(pages)):
    im=Image.open(OUT/'preview'/f'page-{idx+1:02d}.png')
    im.thumbnail((thumb_w-8,thumb_h-8))
    sheet.paste(im,((idx%4)*thumb_w+4,(idx//4)*thumb_h+4))
sheet.save(OUT/'preview'/'contact-sheet.png')
print(json.dumps(report,indent=2))
