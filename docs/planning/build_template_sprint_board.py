"""Six native draw.io sprint boards matching the supplied PDF figure design."""
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
ORIGINAL=json.loads((OUT/'sprint-board-data.json').read_text(encoding='utf-8'))
REFERENCE=Path('C:/Users/kupal/Downloads/reference.pdf')
assert REFERENCE.is_file()
DATE='2026-10-12'
TEAM_SOURCE=OUT.parents[1]/'docs/THESIS_SOURCE.md'
author_section=TEAM_SOURCE.read_text(encoding='utf-8').split('## Authors',1)[1].split('**Date:**',1)[0]
TEAM=[line[2:].strip() for line in author_section.splitlines() if line.startswith('- ')]
assert len(TEAM)==5 and len(set(TEAM))==5
BOARDS=[
    dict(number=1,title='DISCOVERY &\nBACKLOG CREATION',focus='Requirements Analysis',
         goal='Define the VED workflow, users, data requirements and prioritized product backlog.',
         activities=[
             'Review the project requirements and separate Admin and Designer responsibilities.',
             'Organize the upload, AI review, canonical geometry, routing, costing and report workflow into small tickets.',
             'Define acceptance criteria for immutable originals, shared geometry, authorization and historical prices.',
         ],milestone='Prioritized VED product backlog with ticket dependencies, scope boundaries and documented acceptance criteria.',
         state='Documented',timeline='Requirements phase\nDates: not recorded',
         team=TEAM,
         evidence=['docs/FUNCTIONAL_SPEC.md','AGENTS.md'],
         acceptance=['Backlog and ticket dependencies exist.','Stakeholder sign-off is not inferred from documentation.']),
    dict(number=2,title='PROTOTYPING &\nARCHITECTURE',focus='User Design and System Planning',
         goal='Model the user journey and the shared data contracts before feature integration.',
         activities=[
             'Map authentication, projects, uploads, proposal review and saved 2D/3D workspaces.',
             'Define the ERD, FastAPI service boundaries, candidate schema and versioned canonical geometry.',
             'Review workspace layouts and feedback paths with the intended Designer and Admin users.',
         ],milestone='System architecture, database diagrams, geometry contracts and workspace designs ready for implementation and review.',
         state='Implemented; review pending',timeline='Design phase\nDates: not recorded',
         team=TEAM,
         evidence=['docs/ARCHITECTURE.md','docs/geometry.md','docs/erd/README.md'],
         acceptance=['Architecture and geometry contracts exist.','Formal client design approval remains a separate event.']),
    dict(number=3,title='FOUNDATIONAL\nENGINEERING',focus='Platform and Data Foundations',
         goal='Establish secure identity, database persistence, source safety and durable processing controls.',
         activities=[
             'Implement React/Vite and FastAPI with configurable MySQL connectivity and OAuth/OIDC access.',
             'Build owner-scoped projects, floors and validated JPEG/PNG/PDF uploads with unchanged originals.',
             'Persist processing jobs, source pages, artifacts, review authority and concurrent layout saves.',
             'Complete the PRE0-PRE12 readiness checks before model work.',
         ],milestone='Working platform foundations with durable records, preserved originals and a recorded PRE12 readiness gate.',
         state='Implemented',timeline='PRE12 gate recorded\n06 September 2026',
         team=TEAM,
         evidence=['docs/PRE_VLM_READINESS_REPORT.md','backend/app/main.py'],
         acceptance=['Historical PRE12 foundation gate is PASS.','This gate does not establish a production AI release.']),
    dict(number=4,title='AI & ELECTRICAL\nPLANNING INTEGRATION',focus='Iterative Development',
         goal='Connect reviewable floor-plan proposals to synchronized geometry, routing and backend estimates.',
         activities=[
             'Prepare source views and validate wall, symbol and observed-wiring proposals with explicit provenance.',
             'Support Designer corrections and shared versioned geometry for Konva 2D and Three/R3F 3D.',
             'Integrate obstacle-aware A*, service-level routes, vertical drops and explicit multi-floor connectors.',
             'Use database materials and prices for draft BOMs and captured-price estimate snapshots.',
         ],milestone='Integrated development workflow from upload and review through saved layouts, electrical routes and versioned estimates.',
         state='In progress; quality gated',timeline='Development snapshot\n12 October 2026',
         team=TEAM,
         evidence=['docs/U_VLM_PROGRESS.md','backend/app/api/routes/estimates.py','frontend/src/features/estimation/BOMPanel.jsx'],
         acceptance=['Integration is implemented in the development tree.','Independent accuracy and measured real-input costing remain unproven.']),
    dict(number=5,title='QUALITY ASSURANCE &\nOPTIMIZATION',focus='Testing, Review and Stabilization',
         goal='Make the current editing, source-evidence and costing changes reproducible and reviewable.',
         activities=[
             'Capture the dirty-tree baseline; run full backend/frontend, build and lint gates; resolve catalog lint debt.',
             'Integrate endpoint magnets, draft BOM pricing and source-backed evidence as scoped changes.',
             'Verify native 2D/3D dragging, exact anchors, cancel/disconnect, undo/redo and save/reload.',
             'Check pricing units, historical snapshots, stale routes and reanalysis durability; align status documentation.',
         ],milestone='Reviewed integration changes and recorded regression, live interaction, pricing and source-preservation evidence.',
         state='In progress',timeline='Proposed sprint window\n12-23 October 2026',
         team=TEAM,
         evidence=['docs/U_VLM_PROGRESS.md','frontend/package.json','backend/tests/test_reanalysis_durability.py'],
         acceptance=['SP-01 through SP-10 have explicit dependencies and completion checks.','All required selected-scope gates must pass; failures are not silently skipped.']),
    dict(number=6,title='REPORTING, GO-LIVE &\nEVALUATION',focus='Delivery and User Acceptance',
         goal='Complete reporting, audit traceability and evidence-based acceptance of the full VED workflow.',
         activities=[
             'Implement Q1-Q4: version-linked PDF contracts, generation, protected retrieval and report history UI.',
             'Implement R1-R3: safe workflow audit events and an Admin-only audit viewer.',
             'Prepare deployment and a complete login-to-report acceptance walkthrough with approved real inputs.',
             'Close independent gold evaluation, model/runtime selection and signed U14 promotion/rollback gates.',
         ],milestone='Stored PDF reports, safe audit history, validated MVP acceptance and documented deployment/release evidence.',
         state='Planned; evidence gated',timeline='After stabilization gate\nDates: to be confirmed',
         team=TEAM,
         evidence=['docs/FUNCTIONAL_SPEC.md','docs/LOCAL_VLM_MIGRATION_PLAN.md'],
         acceptance=['Report totals retain the captured estimate version after price changes.','Human, independent-data and release evidence remain required.']),
]

W,H=1400,980
COLORS={'ink':'#232833','secondary':'#4B5160','lime':'#B8FA67','pale':'#E9EDF3',
        'line':'#E3E6EA','cyan':'#50DCE0','orange':'#FFB547','green':'#8EAF58'}
FONTS={};COUNTER=0;MX=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device','version':'24.7.17'})
PAGES=[];all_geometry=[]
def font(size,bold=False):
    key=size,bold
    if key not in FONTS:
        FONTS[key]=ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)
    return FONTS[key]

def wrap(value,width,size,bold=False):
    result=[]
    for para in value.split('\n'):
        line=''
        for word in para.split():
            proposed=(line+' '+word).strip()
            if line and font(size,bold).getlength(proposed)>width:
                result.append(line);line=word
            else:line=proposed
        result.append(line)
    assert all(font(size,bold).getlength(line)<=width for line in result),value
    return result

def group(cid,x,y,w,h):
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':'','vertex':'1','parent':'1','style':'group;'})
    ET.SubElement(c,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})

def rect(x,y,w,h,fill='white',border=True,rounding=0,parent='1',px=0,py=0,cid=None):
    global COUNTER
    COUNTER+=1;cid=cid or f'cell-{COUNTER}'
    style=f'rounded={1 if rounding else 0};arcSize=4;fillColor={fill};strokeColor={COLORS["line"] if border else "none"};'
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':'','vertex':'1','parent':parent,'style':style})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    SVG.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rounding}" fill="{fill}" stroke="{COLORS["line"] if border else "none"}"/>')
    PEN.rounded_rectangle((x,y,x+w,y+h),radius=rounding,fill=fill,outline=COLORS['line'] if border else None)
    return cid

def text(value,x,y,w,h,size=17,bold=False,color=None,align='left',valign='top',parent='1',px=0,py=0,padding=0):
    global COUNTER
    COUNTER+=1;cid=f'text-{COUNTER}';color=color or COLORS['ink']
    lines=wrap(value,w-padding*2,size,bold);lh=size+6
    assert len(lines)*lh<=h-padding*2+2,('Text overflow',value,len(lines),h)
    assert x>=0 and y>=0 and x+w<=W and y+h<=H,('Outside page',value)
    c=ET.SubElement(ROOT,'mxCell',{'id':cid,'value':'\n'.join(lines),'vertex':'1','parent':parent,
        'style':f'text;html=0;whiteSpace=wrap;fontFamily=Arial;fontSize={size};fontStyle={1 if bold else 0};fontColor={color};fillColor=none;strokeColor=none;align={align};verticalAlign={valign};spacing={padding};'})
    ET.SubElement(c,'mxGeometry',{'x':str(x-px),'y':str(y-py),'width':str(w),'height':str(h),'as':'geometry'})
    ty=y+padding if valign=='top' else y+(h-len(lines)*lh)/2
    for line in lines:
        fw=font(size,bold).getlength(line);tx=x+padding if align=='left' else x+(w-fw)/2
        SVG.append(f'<text x="{tx}" y="{ty+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(line)}</text>')
        PEN.text((tx,ty),line,font=font(size,bold),fill=color)
        all_geometry.append((BOARD['number'],tx,ty,fw,lh))
        ty+=lh
    return len(lines)*lh

def circle(cx,cy,r,fill,label='',size=12):
    global COUNTER
    COUNTER+=1
    c=ET.SubElement(ROOT,'mxCell',{'id':f'circle-{COUNTER}','value':label,'vertex':'1','parent':'1',
        'style':f'ellipse;whiteSpace=wrap;html=0;fillColor={fill};strokeColor=none;fontColor=#FFFFFF;fontFamily=Arial;fontSize={size};fontStyle=1;align=center;verticalAlign=middle;spacing=0;'})
    ET.SubElement(c,'mxGeometry',{'x':str(cx-r),'y':str(cy-r),'width':str(r*2),'height':str(r*2),'as':'geometry'})
    SVG.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>');PEN.ellipse((cx-r,cy-r,cx+r,cy+r),fill=fill)
    if label:
        fw=font(size,True).getlength(label);SVG.append(f'<text x="{cx-fw/2}" y="{cy+size/2-1}" font-family="Arial" font-size="{size}" font-weight="700" fill="white">{label}</text>')
        PEN.text((cx-fw/2,cy-size/2-2),label,font=font(size,True),fill='white')

for BOARD in BOARDS:
    number=BOARD['number']
    diagram=ET.SubElement(MX,'diagram',{'id':f'sprint-{number}','name':f'Sprint {number} - '+BOARD['title'].replace('\n',' ').title()})
    model=ET.SubElement(diagram,'mxGraphModel',{'dx':str(W),'dy':str(H),'grid':'1','gridSize':'10','guides':'1','tooltips':'1','connect':'1','arrows':'1','fold':'1','page':'1','pageScale':'1','pageWidth':str(W),'pageHeight':str(H),'background':'#FFFFFF'})
    ROOT=ET.SubElement(model,'root');ET.SubElement(ROOT,'mxCell',{'id':'0'});ET.SubElement(ROOT,'mxCell',{'id':'1','parent':'0'})
    SVG=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Sprint {number}: {html.escape(BOARD["title"].replace(chr(10)," "))}"><rect width="{W}" height="{H}" fill="white"/>']
    IMAGE=Image.new('RGB',(W,H),'white');PEN=ImageDraw.Draw(IMAGE)
    text('Sprint Planning Board',86,46,1228,62,size=42,bold=True)
    text('Plan, track, and complete VED sprint tasks efficiently',87,113,1227,34,size=18)
    x1,x2,x3=86,414,1038;w1,w2,w3=304,600,276;y=178;body_bottom=624
    for idx,(x,width) in enumerate([(x1,w1),(x2,w2),(x3,w3)]):
        gid=f'panel-{number}-{idx}';group(gid,x,y,width,body_bottom-y)
        rect(x,y,width,body_bottom-y,rounding=6,parent=gid,px=x,py=y)
    left='panel-'+str(number)+'-0';center='panel-'+str(number)+'-1';right='panel-'+str(number)+'-2'
    rect(x1,y,w1,78,fill=COLORS['pale'],border=False,parent=left,px=x1,py=y)
    text('SPRINT '+str(number)+': '+BOARD['title'],x1+11,y+9,w1-22,62,size=14,bold=True,align='center',valign='middle',parent=left,px=x1,py=y)
    rect(x2,y,w2,42,fill=COLORS['lime'],border=False,parent=center,px=x2,py=y)
    rect(x3,y,w3,42,fill=COLORS['lime'],border=False,parent=right,px=x3,py=y)
    text('ACTIVITIES',x2,y+7,w2,28,size=15,bold=True,align='center',valign='middle',parent=center,px=x2,py=y)
    text('MILESTONE DELIVERABLE',x3,y+7,w3,28,size=13,bold=True,align='center',valign='middle',parent=right,px=x3,py=y)
    used=text('Focus: '+BOARD['focus'],x1+15,y+92,w1-30,98,size=17,parent=left,px=x1,py=y)
    text('Goal: '+BOARD['goal'],x1+15,y+106+used,w1-30,body_bottom-(y+106+used)-15,size=17,parent=left,px=x1,py=y)
    ay=y+63
    for activity in BOARD['activities']:
        lines=wrap(activity,w2-38,17);height=len(lines)*23
        text(activity,x2+19,ay,w2-38,height,size=17,parent=center,px=x2,py=y)
        ay+=height+25
    assert ay-25<=body_bottom-16,('Activities overflow',number,ay)
    text(BOARD['milestone'],x3+16,y+66,w3-32,body_bottom-y-82,size=19,parent=right,px=x3,py=y)
    # Template's status / timeline / team strip.
    sy=659;sh=219;status_w=330;timeline_w=310;team_x=x1+status_w+timeline_w;team_w=1228-status_w-timeline_w
    rect(x1,sy,1228,sh)
    rect(x1+status_w,sy,timeline_w,sh,fill=COLORS['pale'])
    text('STATUS',x1,sy+9,status_w,25,size=13,bold=True,align='center')
    text('TIMELINE',x1+status_w,sy+9,timeline_w,25,size=13,bold=True,align='center')
    text('TEAM',team_x,sy+9,team_w,25,size=13,bold=True,align='center')
    rect(x1,sy+43,1228,1,fill=COLORS['line'],border=False)
    for i,(label,color) in enumerate([('IN PROGRESS',COLORS['cyan']),('PLANNED',COLORS['orange']),('DONE',COLORS['lime'])]):
        cy=sy+72+i*32;circle(x1+24,cy,5,color);text(label,x1+43,cy-8,status_w-57,23,size=12)
    text('Current: '+BOARD['state'],x1+17,sy+166,status_w-34,46,size=12,bold=True)
    text(BOARD['timeline'],x1+status_w+18,sy+56,timeline_w-36,146,size=17,align='center',valign='middle')
    for i,name in enumerate(BOARD['team']):
        tx=team_x+30+(i%2)*290;ty=sy+60+(i//2)*51
        initials=name.split()[0][0]+name.split()[-1][0]
        circle(tx,ty+12,14,COLORS['green'],initials,10)
        text(name,tx+25,ty-3,240,42,size=14,bold=True)
    text('VED Electrical Services | Snapshot: 12 Oct 2026 | Dates: recorded, proposed or TBD | Design reference: senior paper (reference.pdf)',86,911,1228,27,size=12,color=COLORS['secondary'])
    text(f'Sprint {number} of 6 | '+BOARD['title'].replace('\n',' ').title(),86,945,1228,26,size=13,bold=True,color=COLORS['secondary'],align='center')
    SVG.append('</svg>');PAGES.append({'number':number,'svg':''.join(SVG)})
    IMAGE.save(OUT/f'template-sprint-{number}.png');(OUT/f'template-sprint-{number}.svg').write_text(PAGES[-1]['svg'],encoding='utf-8')

ET.indent(MX)
FILE=OUT/f'ved-sprint-planning-board-{DATE}.drawio'
ET.ElementTree(MX).write(FILE,encoding='utf-8',xml_declaration=True)
parsed=ET.parse(FILE);assert len(parsed.findall('diagram'))==6
for diagram in parsed.findall('diagram'):
    ids=[c.attrib['id'] for c in diagram.findall('.//mxCell')]
    assert len(ids)==len(set(ids))
    for c in diagram.findall('.//mxCell'):
        if 'parent' in c.attrib:assert c.attrib['parent'] in ids
    labels=[c.attrib.get('value','').replace('\n',' ') for c in diagram.findall('.//mxCell')]
    for member in TEAM:
        assert labels.count(member)==1,('Missing or repeated team member',member)
    assert not any('Name: TBD' in value for value in labels)
    assert not any(value in ['Product lead','Frontend developer','Backend developer','QA analyst','Electrical Designer','Admin','AI/CV developer','QA / deployment lead','VED release approver'] for value in labels)
assert not any('shape=image' in c.attrib.get('style','') for c in parsed.findall('.//mxCell'))
assert sum(1 for c in parsed.findall('.//mxCell') if c.attrib.get('value'))>100

preview=['<!doctype html><html lang="en"><meta charset="utf-8"><title>VED sprint planning boards</title><style>body{margin:0;background:#ebedef;font-family:Arial;color:#232833}nav{padding:14px;background:white;position:sticky;top:0;z-index:1}nav a{margin-right:18px;color:#4b5160}section{margin:22px auto;max-width:1400px;background:white}svg{display:block;width:100%}@media print{nav{display:none}section{margin:0;break-after:page}@page{size:A3 landscape;margin:6mm}}</style><nav><strong>VED sprint planning boards</strong><br>']
for b in BOARDS:preview.append(f'<a href="#sprint-{b["number"]}">Sprint {b["number"]}</a>')
preview.append('</nav>')
for p in PAGES:preview.append(f'<section id="sprint-{p["number"]}">{p["svg"]}</section>')
preview.append('</html>');(OUT/'sprint-board-preview.html').write_text('\n'.join(preview),encoding='utf-8')
thumb_w,thumb_h=700,490
overview=Image.new('RGB',(1430,1510),'#E4E7EA')
for i in range(6):
    image=Image.open(OUT/f'template-sprint-{i+1}.png');image.thumbnail((thumb_w,thumb_h))
    overview.paste(image,(10+(i%2)*710,10+(i//2)*500))
overview.save(OUT/'template-sprints-overview.png')
data={'reference_template':str(REFERENCE),'design':'Three main columns with lime headers and status/timeline/team strip',
      'team_source':str(TEAM_SOURCE),'team':TEAM,
      'snapshot_date':DATE,'branch':ORIGINAL['branch'],'head':ORIGINAL['head'],'boards':BOARDS,
      'detailed_stabilization_items':ORIGINAL['lanes'],'detailed_acceptance':ORIGINAL['acceptance'],'sources':ORIGINAL['sources']}
(OUT/'template-sprint-data.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
report={'pages':6,'native_text_labels':sum(1 for c in parsed.findall('.//mxCell') if c.attrib.get('value')),
        'editable_shapes':'PASS','xml_parse':'PASS','group_references':'PASS','text_fit':'PASS','preview_visual_review':'PENDING',
        'reference_pdf_changed':False,'team_names':TEAM,'team_source':str(TEAM_SOURCE),'team_coverage':'PASS: five names exactly once on all six boards','team_roles_removed':'PASS','timeline':'Historical record, proposed sprint or TBD',
        'product_tests_this_task':'NOT TESTED (planning only)','diagrams_net_editor_import':'NOT TESTED','downloads_copy':'PENDING'}
(OUT/'sprint-board-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
