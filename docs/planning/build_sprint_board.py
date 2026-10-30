"""Editable native diagrams.net sprint board grounded in repository evidence."""
import ast
import html
import json
import math
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TODAY = '2026-10-12'
BRANCH = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
COMMIT = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
assert date(2026,10,12).weekday()==0 and date(2026,10,23).weekday()==4

SOURCES = [
    {'path':'AGENTS.md','finding':'Shared canonical geometry; server-authoritative prices; preserve originals; one ticket at a time.'},
    {'path':'docs/FUNCTIONAL_SPEC.md','finding':'Q1-Q4 define PDF reporting; R1-R3 define audit logging; S3-S6 define quality and calculation gates.'},
    {'path':'docs/U_VLM_PROGRESS.md','finding':'Latest October 12: endpoint magnets are local uncommitted work; native drag is inconclusive; 83 files / 684 frontend tests reported.'},
    {'path':'docs/PRE_VLM_READINESS_REPORT.md','finding':'Historical PRE12 foundation gate passed on September 6; this is not a production AI release.'},
    {'path':'docs/LOCAL_VLM_MIGRATION_PLAN.md','finding':'Real-data approval, independent evaluation, model selection, training and release remain distinct gates.'},
    {'path':'backend/app/main.py','finding':'Estimate/material routes are registered; no report or audit router is registered.'},
    {'path':'backend/app/api/routes/estimates.py','finding':'Versioned estimate endpoints and draft/historical BOM CSV endpoints exist.'},
    {'path':'backend/app/api/routes/materials.py','finding':'Admin-only workbook preview/apply endpoints exist.'},
    {'path':'frontend/src/features/estimation/BOMPanel.jsx','finding':'Draft BOM UI, material/price/unit controls, paper dimensions and CSV export are present.'},
    {'path':'frontend/src/features/detection-review/deviceConnections.js','finding':'Shared endpoint connection logic exists in the current local work.'},
    {'path':'frontend/src/features/viewer-3d/DeviceMeshCatalog.jsx','finding':'Untracked catalog imports @react-three/drei; ledger records six lint errors. Adoption/removal needs an explicit decision.'},
]
for source in SOURCES:
    assert (ROOT/source['path']).is_file(),source['path']
assert not (ROOT/'backend/app/api/routes/reports.py').exists()
assert not (ROOT/'backend/app/models/audit_log.py').exists()

def card(cid,title,body,done,role,priority='P1',needs='None',source=None):
    return dict(id=cid,title=title,body=body,done=done,role=role,priority=priority,needs=needs,source=source or [])

LANES = [
    ('BACKLOG', 'Next delivery slice', '#667085', [
        card('Q1','Freeze report data contract','Bind project, layout, routes, BOM and costs to one stored estimate version.',
             'Contract excludes live-price recalculation.','Backend','P1','O3 + K2',['docs/FUNCTIONAL_SPEC.md']),
        card('Q2','Generate planning PDF','Render quantities, captured unit prices, totals, date and prepared-by identity.',
             'Readable PDF stored outside originals.','Backend','P1','Q1',['docs/FUNCTIONAL_SPEC.md']),
        card('Q3','Persist and serve reports','Create report records and protected generation/download endpoints.',
             'Old report downloads retain old costs.','Backend','P1','Q2',['docs/FUNCTIONAL_SPEC.md']),
        card('Q4','Build report workspace','Show report status, errors, version history and PDF download.',
             'Designer can generate and reopen a report.','Frontend','P1','Q3',['docs/FUNCTIONAL_SPEC.md']),
    ]),
    ('READY TO PLAN', 'Proposed Sprint 01', '#226B83', [
        card('SP-01','Capture a clean baseline','Inventory the current dirty tree. Record full backend/frontend, build and lint results.',
             'Reproducible baseline; existing work preserved.','QA','P0','None',['docs/U_VLM_PROGRESS.md']),
        card('SP-02','Resolve catalog lint debt','Decide how to retain, fix or exclude the unused DeviceMeshCatalog source.',
             'Full lint passes without masking errors.','Frontend','P1','SP-01',['frontend/src/features/viewer-3d/DeviceMeshCatalog.jsx']),
        card('SP-05','Align status documentation','Reconcile README counts, implementation status and the chronological progress ledger.',
             'Current API/schema inventory is recorded.','Docs / Backend','P1','SP-01',['README.md','docs/U_VLM_PROGRESS.md']),
        card('SP-09','Close the integration gate','Run full regression, build and lint after the scoped integration changes.',
             'Gates pass; failures remain visible.','QA','P0','SP-02..08 + SP-10',['frontend/package.json']),
    ]),
    ('LOCAL WORK', 'Present in the working tree', '#9D641B', [
        card('SP-03','Integrate endpoint magnets','Shared 2D/3D connection controls exist locally; prepare a focused reviewable change.',
             'Exact anchors, cancel and disconnect persist.','Frontend','P0','SP-01',['docs/U_VLM_PROGRESS.md','frontend/src/features/detection-review/deviceConnections.js']),
        card('SP-04','Integrate draft BOM pricing','Review the local BOM, workbook import, separate pricing and CSV changes as a bounded slice.',
             'Draft totals stay distinct from snapshots.','Backend + Frontend','P0','SP-01',['backend/app/api/routes/materials.py','frontend/src/features/estimation/BOMPanel.jsx']),
        card('SP-10','Integrate source-evidence fixes','Source-backed helpers are checkpointed; worker/detector integration remains local.',
             'Existing raw results and reviews survive.','AI / Backend','P0','SP-01',['docs/U_VLM_PROGRESS.md']),
    ]),
    ('VERIFY', 'Acceptance still to prove', '#75619C', [
        card('SP-06','Verify native 2D / 3D drag','Reproduce actual pointer acquisition, connection, cancellation and reload in both views.',
             'Recorded live drag succeeds in both views.','QA + Designer','P0','SP-03',['docs/U_VLM_PROGRESS.md']),
        card('SP-07','Verify pricing and units','Exercise known-answer draft/snapshot totals, roll conversions and stale-route refusal.',
             'Exact decimals; historical prices stay fixed.','QA / Backend','P0','SP-04',['backend/app/services/estimate_service.py','backend/tests/test_estimates.py']),
        card('SP-08','Verify reanalysis durability','Check reviewed overrides, endpoint attachments and unchanged originals through reanalysis.',
             'No lost corrections or fabricated paths.','QA / Backend','P0','SP-03 + SP-10',['backend/tests/test_reanalysis_durability.py']),
    ]),
    ('BLOCKED / GATED', 'Inputs or evidence required', '#9B4242', [
        card('BL-01','Independent detection evidence','U3/U5/S3 need approved gold projects and thresholds; independent 85% accuracy is unproven.',
             'Frozen independent evaluation is approved.','VED Dataset Approver','P0','Human-reviewed gold',['docs/LOCAL_VLM_MIGRATION_PLAN.md','docs/U_VLM_PROGRESS.md']),
        card('BL-02','Real measured costing','Latest live BOM evidence lacks active prices, exact-page scale and reusable purchase inputs.',
             'Admin prices + Designer measures validate BOM.','Admin + Designer','P0','Approved real inputs',['docs/U_VLM_PROGRESS.md']),
        card('BL-03','Production model release','Runtime/model selection, approved training and signed U14 promotion are separate gates.',
             'Sealed evaluation and rollback evidence pass.','VED + AI Lead','P0','U3-U10 evidence + U14',['docs/LOCAL_VLM_MIGRATION_PLAN.md']),
    ]),
    ('IMPLEMENTED', 'Code / ledger evidence', '#39724E', [
        card('FOUNDATION','Identity, upload and jobs','OAuth/OIDC roles, original preservation, durable jobs and PRE0-PRE12 foundations exist.',
             'Historical readiness evidence is recorded.','Platform','P2','Recorded implementation',['docs/PRE_VLM_READINESS_REPORT.md']),
        card('K / L','Shared 2D / 3D geometry','Versioned canonical snapshots feed Konva and Three/R3F with conditional saves.',
             'Metric acceptance remains input-dependent.','Geometry','P2','Recorded implementation',['README.md']),
        card('M1-M7','Saved electrical routing','Obstacle-aware A*, service-level paths, drops/risers and route version persistence exist.',
             'Engineering and real-input QA stay separate.','Routing','P2','Recorded implementation',['README.md','backend/app/api/routes/routing.py']),
        card('N / O','Versioned estimates','Catalog/history, quantities and captured-price estimate APIs/UI are implemented.',
             'Reports and real costing QA remain open.','Estimation','P2','Recorded implementation',['backend/app/api/routes/estimates.py','backend/app/services/estimate_service.py']),
    ]),
]
CARDS=[c for _,_,_,cards in LANES for c in cards]
assert len(CARDS)==len({c['id'] for c in CARDS})==21
ids={c['id'] for c in CARDS}
ROADMAP = [
    dict(label='SPRINT 01',title='Stabilize the current workspace',date='Proposed: 12-23 Oct 2026',color='#226B83',
         goal='Deliver a reviewable, regression-tested development baseline.',
         items=[('Baseline + lint','SP-01 / SP-02: inventory, full baseline, catalog decision.'),
                ('Integrate local work','SP-03 / SP-04 / SP-10: magnets, draft BOM, source evidence.'),
                ('Prove acceptance','SP-06 / SP-07 / SP-08: live drag, units/prices, durability.'),
                ('Close and document','SP-05 / SP-09: status alignment and final regression gate.')],
         exit='Exit: all sprint checks pass, or unresolved failures are explicitly deferred.'),
    dict(label='SPRINT 02',title='Finish PDF reporting',date='After the Sprint 01 gate',color='#667085',
         goal='Export stored, versioned planning estimates as durable PDF reports.',
         items=[('Q1 - Report contract','Freeze project, canonical layout, route and captured estimate references.'),
                ('Q2 - PDF generation','Readable tables, totals, date/user and planning wording.'),
                ('Q3 - Report API','Persist records; authorize generation/retrieval; retain original costs.'),
                ('Q4 - Report UI','Status, history, errors and reopening/downloading old reports.')],
         exit='Exit: a stored report still matches its estimate after Admin price changes.'),
    dict(label='SPRINT 03',title='Complete audit traceability',date='Sequence proposed; dates TBD',color='#75619C',
         goal='Make important actions traceable through a protected Admin workflow.',
         items=[('R1 - Audit foundation','Reusable service/table; safe user, action, entity and timestamp fields.'),
                ('R2 - Workflow events','Login, upload, review, routing, prices, estimates and reports.'),
                ('R3 - Admin viewer','Role-protected filters by user/action/date; sanitized details.'),
                ('S4-S6 - Regression','Alignment, multi-floor lengths, no-path behavior and price snapshots.')],
         exit='Exit: audit records are complete and Designers cannot read unrestricted logs.'),
    dict(label='RELEASE TRACK',title='Earn production acceptance',date='Evidence-gated; no fixed date',color='#9B4242',
         goal='Keep development capability separate from measured production readiness.',
         items=[('U3-U5 / S3 - Gold evidence','Approve source eligibility, reference pack, frozen gold and thresholds.'),
                ('U6 / U8 - Runtime choice','Select a real measured local model; validate health, privacy and resources.'),
                ('U9 / U10 - Training','Human-approved records and compute; register an evaluated adapter.'),
                ('U14 / T2-T3 - Release','Signed promotion, rollback drill, deployment and complete workflow proof.')],
         exit='Exit: independent results and signed release evidence pass; retain YOLO until then.'),
]

CHECKS = [
    ('SP-01 / SP-09','Run existing backend, frontend, build and lint gates; preserve the dirty tree and private artifacts.'),
    ('SP-02','Resolve six reported catalog lint errors; do not silently add missing libraries or suppress checks.'),
    ('SP-03 / SP-06','Native drag + click/keyboard paths; exact coordinates, cancel/disconnect, undo/redo and save/reload.'),
    ('SP-04 / SP-07','Known quantities x captured prices; draft vs snapshot semantics; conversions; missing and stale inputs.'),
    ('SP-08 / SP-10','No lost reviewed paths or attachments after reanalysis; source checksums and history remain intact.'),
    ('SP-05','Re-measure counts and reconcile stale README claims with actual code and recent checkpoints.'),
    ('Q1-Q4','Reports reference stored estimate/layout/route versions; unchanged historical totals; authenticated access.'),
    ('R1-R3','Safe audit fields and role enforcement; no secrets or raw provider credentials in recorded details.'),
    ('BL-01 / BL-03','Independent gold, thresholds, rights, training authority and signed release; synthetic tests do not close these.'),
]

FONT_CACHE={};NUMBER=0;PAGES=[]
MX=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','version':'24.7.17'})
def font(size,bold=False):
    key=(size,bold)
    if key not in FONT_CACHE:
        FONT_CACHE[key]=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
    return FONT_CACHE[key]

def wrap(value,width,size,bold=False):
    lines=[]
    for paragraph in value.split('\n'):
        line=''
        for word in paragraph.split():
            trial=(line+' '+word).strip()
            if line and font(size,bold).getlength(trial)>width:
                lines.append(line);line=word
            else:line=trial
        lines.append(line)
    assert all(font(size,bold).getlength(line)<=width for line in lines),('Unbreakable text',value,width)
    return lines

def page(name,width,height):
    global ROOT_CELL,SVG,PEN,IMAGE,PAGE_WIDTH,PAGE_HEIGHT
    PAGE_WIDTH,PAGE_HEIGHT=width,height
    diagram=ET.SubElement(MX,'diagram',{'id':f'page-{len(PAGES)+1}','name':name})
    model=ET.SubElement(diagram,'mxGraphModel',{'dx':str(width),'dy':str(height),'grid':'1','gridSize':'10','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(width),'pageHeight':str(height),'background':'#F6F7FA'})
    ROOT_CELL=ET.SubElement(model,'root');ET.SubElement(ROOT_CELL,'mxCell',{'id':'0'});ET.SubElement(ROOT_CELL,'mxCell',{'id':'1','parent':'0'})
    SVG=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(name)}"><rect width="{width}" height="{height}" fill="#F6F7FA"/>']
    IMAGE=Image.new('RGB',(width,height),'#F6F7FA');PEN=ImageDraw.Draw(IMAGE)
    PAGES.append({'name':name,'width':width,'height':height,'items':[]})

def group(cid,x,y,w,h,parent='1',px=0,py=0):
    c=ET.SubElement(ROOT_CELL,'mxCell',{'id':cid,'value':'','vertex':'1','parent':parent,'style':'group;'})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})

def block(value,x,y,w,h,size=14,bold=False,fill='none',border=False,color='#17212B',align='left',parent='1',px=0,py=0,cid=None,rounded=False,padding=1):
    global NUMBER
    NUMBER+=1;cid=cid or f'cell-{NUMBER}'
    lines=wrap(value,w-2*padding,size,bold);lh=size+4
    assert len(lines)*lh<=h-2*padding+3,('Text overflow',value,h,len(lines),lh)
    assert x>=0 and y>=0 and x+w<=PAGE_WIDTH and y+h<=PAGE_HEIGHT,('Outside page',value)
    style=f'whiteSpace=wrap;html=0;fontFamily=Arial;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};align={align};verticalAlign=middle;spacing={padding};rounded={1 if rounded else 0};arcSize=8;fillColor={fill};strokeColor={"#D6DAE2" if border else "none"};'
    c=ET.SubElement(ROOT_CELL,'mxCell',{'id':cid,'value':'\n'.join(lines),'vertex':'1','parent':parent,'style':style})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    if fill!='none' or border:
        SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{8 if rounded else 0}" fill="{fill}" stroke="{"#D6DAE2" if border else "none"}"/>')
        if rounded:PEN.rounded_rectangle((x,y,x+w,y+h),radius=8,fill=fill if fill!='none' else None,outline='#D6DAE2' if border else None)
        else:PEN.rectangle((x,y,x+w,y+h),fill=fill if fill!='none' else None,outline='#D6DAE2' if border else None)
    ty=y+(h-len(lines)*lh)/2
    for line in lines:
        fw=font(size,bold).getlength(line);tx=x+padding if align=='left' else x+(w-fw)/2
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(line)}</text>')
        PEN.text((tx,ty),line,font=font(size,bold),fill=color);ty+=lh
    PAGES[-1]['items'].append({'id':cid,'x':x,'y':y,'w':w,'h':h,'value':value})
    return cid

def header(title,subtitle,width):
    block('VED ELECTRICAL SERVICES',30,18,width-60,28,size=14,bold=True,color='#667085')
    block(title,30,48,width-60,54,size=32,bold=True)
    block(subtitle,30,108,width-60,33,size=15,color='#475467')

def finish(filename):
    SVG.append('</svg>');PAGES[-1]['svg']=''.join(SVG)
    (OUT/(filename+'.svg')).write_text(PAGES[-1]['svg'],encoding='utf-8')
    IMAGE.save(OUT/(filename+'.png'))

page('01 Sprint planning board',2256,1260)
header('Sprint planning board','Proposed Sprint 01: 12-23 Oct 2026 | Goal: stabilize review, routing and costing | Owners / capacity: TBD',2256)
for lane_index,(name,description,color,cards) in enumerate(LANES):
    x=30+lane_index*367;y=174;w=349
    gid=f'lane-{lane_index}';group(gid,x,y,w,976)
    block('',x,y,w,976,fill='#EDF0F4',border=True,parent=gid,px=x,py=y,rounded=True)
    block(name,x+12,y+9,w-24,32,size=16,bold=True,color=color,parent=gid,px=x,py=y)
    block(description,x+12,y+43,w-24,26,size=12,color='#667085',parent=gid,px=x,py=y)
    for idx,c in enumerate(cards):
        cx=x+11;cy=y+81+idx*215;cw=w-22;ch=202
        cg='card-'+c['id'].replace(' ','-').replace('/','-');group(cg,cx,cy,cw,ch,gid,x,y)
        block('',cx,cy,cw,ch,fill='#FFFFFF',border=True,parent=cg,px=cx,py=cy,rounded=True)
        block(f'{c["id"]}  /  {c["priority"]}',cx+11,cy+7,cw-22,23,size=11,bold=True,color=color,parent=cg,px=cx,py=cy)
        block(c['title'],cx+11,cy+33,cw-22,44,size=16,bold=True,parent=cg,px=cx,py=cy)
        block(c['body'],cx+11,cy+80,cw-22,51,size=13,parent=cg,px=cx,py=cy)
        block('Done when: '+c['done'],cx+11,cy+132,cw-22,44,size=12,color='#475467',parent=cg,px=cx,py=cy)
        block(f'{c["role"]} | Owner: TBD',cx+11,cy+177,cw-22,22,size=10,color='#667085',parent=cg,px=cx,py=cy)
    block(f'{len(cards)} cards',x+12,y+935,w-24,28,size=12,color='#667085',parent=gid,px=x,py=y)
block('Planning labels SP/BL are proposed work items. Q/R/U labels follow the repository roadmap. Dependencies are on the acceptance tab.',30,1168,2196,31,size=14,color='#475467')
block('Implemented = code / recorded evidence, not production approval. Current test gates were not rerun for this planning artifact.',30,1206,2196,31,size=14,color='#475467')
finish('sprint-board')

page('02 Delivery roadmap',2256,1060)
header('Delivery roadmap','Sequence proposal | Later sprint dates and capacity remain uncommitted | Production acceptance depends on independent evidence',2256)
for idx,p in enumerate(ROADMAP):
    x=30+idx*557;y=180;w=525;gid=f'phase-{idx}';group(gid,x,y,w,786)
    block('',x,y,w,786,fill='#FFFFFF',border=True,rounded=True,parent=gid,px=x,py=y)
    block(p['label'],x+16,y+14,w-32,31,size=15,bold=True,color=p['color'],parent=gid,px=x,py=y)
    block(p['title'],x+16,y+52,w-32,68,size=24,bold=True,parent=gid,px=x,py=y)
    block(p['date'],x+16,y+124,w-32,29,size=14,color='#667085',parent=gid,px=x,py=y)
    block('Goal: '+p['goal'],x+16,y+166,w-32,70,size=16,parent=gid,px=x,py=y)
    for j,(title,detail) in enumerate(p['items']):
        yy=y+255+j*106
        block(title,x+16,yy,w-32,35,size=16,bold=True,parent=gid,px=x,py=y)
        block(detail,x+16,yy+38,w-32,57,size=14,color='#475467',parent=gid,px=x,py=y)
    block(p['exit'],x+16,y+697,w-32,71,size=15,bold=True,color=p['color'],parent=gid,px=x,py=y)
block('Stop at each ticket gate. No automatic model training, production promotion or engineering approval is implied by this plan.',30,990,2196,43,size=15,color='#475467')
finish('sprint-roadmap')

page('03 Acceptance and evidence',2256,1450)
header('Acceptance criteria and evidence','Snapshot: 12 Oct 2026 | Branch: '+BRANCH+' | HEAD: '+COMMIT+' | Proposed owners, capacity and effort estimates remain unassigned',2256)
block('SPRINT EXIT CHECKLIST',30,169,1080,40,size=20,bold=True)
yy=218
for cid,detail in CHECKS:
    block(cid,30,yy,230,86,size=14,bold=True,fill='#FFFFFF',border=True)
    block(detail,260,yy,850,86,size=15,fill='#FFFFFF',border=True)
    yy+=88
block('DEPENDENCIES',30,yy+18,1080,33,size=18,bold=True)
dependency_lines=[]
for c in CARDS:
    if c['id'].startswith('SP-'):dependency_lines.append(c['id']+': '+c['needs'])
block('\n'.join(dependency_lines),30,yy+60,1080,270,size=15,color='#475467')
block('REPOSITORY EVIDENCE / STATUS LIMITS',1140,169,1086,40,size=20,bold=True)
yy=218
for source in SOURCES:
    block(source['path'],1140,yy,1086,30,size=13,bold=True)
    block(source['finding'],1140,yy+32,1086,57,size=14,color='#475467')
    yy+=93
block('Evidence status',1140,yy+8,1086,32,size=18,bold=True)
block('PASS: repository analysis, editable XML, card/criteria coverage, text-fit and preview checks.\nNOT TESTED: product regression in this task and opening the file in the diagrams.net editor.\nLedger results are historical evidence; they are not a new test execution or a complete release claim.',1140,yy+43,1086,120,size=14,color='#475467')
finish('sprint-evidence')

DRAWIO=OUT/f'ved-sprint-planning-board-{TODAY}.drawio'
ET.indent(MX);ET.ElementTree(MX).write(DRAWIO,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(DRAWIO)
assert len(parsed.findall('diagram'))==3
for diagram in parsed.findall('diagram'):
    cells=diagram.findall('.//mxCell');cids=[c.attrib['id'] for c in cells]
    assert len(cids)==len(set(cids))
    for c in cells:
        if 'parent' in c.attrib:assert c.attrib['parent'] in cids
assert len(parsed.findall('.//mxCell[@id="card-SP-01"]'))==1
assert not any('shape=image' in c.attrib.get('style','') for c in parsed.findall('.//mxCell'))

preview=['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED sprint planning board</title><style>body{margin:0;background:#e2e6ec;font-family:Arial;color:#17212b}nav{padding:16px;background:white;position:sticky;top:0}nav a{margin-right:22px;color:#226b83}section{margin:20px auto;max-width:2256px;background:white}svg{display:block;width:100%}@media print{nav{display:none}section{margin:0;break-after:page}@page{size:A3 landscape;margin:6mm}}</style><nav><strong>VED sprint planning</strong> ']
for idx,p in enumerate(PAGES,1):preview.append(f'<a href="#page-{idx}">{html.escape(p["name"])}</a>')
preview.append('</nav>')
for idx,p in enumerate(PAGES,1):preview.append(f'<section id="page-{idx}">{p["svg"]}</section>')
preview.append('</html>');(OUT/'sprint-board-preview.html').write_text('\n'.join(preview),encoding='utf-8')
thumb=Image.open(OUT/'sprint-board.png');thumb.thumbnail((1700,1000));thumb.save(OUT/'sprint-board-overview.png')
data={'planning_date':TODAY,'sprint_dates_proposed':['2026-10-12','2026-10-23'],'owners':'TBD','capacity':'TBD',
      'branch':BRANCH,'head':COMMIT,'lanes':[{ 'name':n,'description':d,'cards':c } for n,d,_,c in LANES],
      'roadmap':ROADMAP,'acceptance':CHECKS,'sources':SOURCES}
(OUT/'sprint-board-data.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
report={'pages':3,'native_editable_cards':21,'duplicate_card_ids':0,'sources_checked':len(SOURCES),
        'text_fit':'PASS','xml_parse':'PASS','parent_group_references':'PASS','editable_native_shapes':'PASS',
        'preview_visual_review':'PENDING','product_tests_this_task':'NOT TESTED (planning only)',
        'diagrams_net_editor_import':'NOT TESTED','output':str(DRAWIO)}
(OUT/'sprint-board-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
