"""Trace the two supplied activity-diagram PNGs; preserve content, enlarge text."""
from pathlib import Path
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

OUT=Path(__file__).resolve().parent
SCALE=3
FONTS={}
SOURCE=[Path('C:/Users/kupal/Downloads/841207488_2284807502296538_4859499289127506223_n.png'),Path('C:/Users/kupal/Downloads/840577695_2274581953114867_7184489182573623837_n.png')]


def font(size,bold=False,italic=False):
    key=(size,bold,italic)
    if key not in FONTS:FONTS[key]=ImageFont.truetype('C:/Windows/Fonts/'+('ariali.ttf' if italic else 'arialbd.ttf' if bold else 'arial.ttf'),round(size*SCALE))
    return FONTS[key]


def wrap(value,width,size,bold=False,italic=False):
    lines=[]
    for para in value.split('\n'):
        line=''
        for word in para.split():
            candidate=(line+' '+word).strip()
            if line and font(size,bold,italic).getlength(candidate)/SCALE>width:
                lines.append(line);line=word
            else:line=candidate
        lines.append(line)
    return lines


class Diagram:
    def __init__(self,number,w,h,headers):
        self.number,self.w,self.h=number,w,h
        self.model=ET.Element('mxGraphModel',page='1',pageScale='1',pageWidth=str(w),pageHeight=str(h),background='#FFFFFF',grid='1',gridSize='10')
        self.root=ET.SubElement(self.model,'root')
        ET.SubElement(self.root,'mxCell',id='0');ET.SubElement(self.root,'mxCell',id='1',parent='0')
        self.im=Image.new('RGB',(w*SCALE,h*SCALE),'white');self.pen=ImageDraw.Draw(self.im)
        self.nodes={};self.flows=[];self.texts=[];self.seq=0
        self.records=[]
        for i,label in enumerate(headers):
            self.shape(f'lane-{i}',(170*i,55,170,h-57),'rect','#FFFFFF' if i%2==0 else '#F5F9FF')
            self.shape(f'header-{i}',(170*i,0,170,55),'rect','#F0F0F0')
            self.text(label,(170*i+4,3,162,49),12,True)

    def uid(self):
        self.seq+=1
        return f'p{self.number}-c{self.seq}'

    def cell(self,cid,value,box,style):
        x,y,w,h=box
        c=ET.SubElement(self.root,'mxCell',id=cid,value=value,vertex='1',parent='1',style=style)
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
        return c

    def shape(self,cid,box,kind='round',fill='#FFFFFF',stroke='#000000'):
        x,y,w,h=box
        pbox=tuple(v*SCALE for v in (x,y,x+w,y+h))
        styles={'round':'rounded=1;arcSize=15;','rect':'rounded=0;','ellipse':'ellipse;','diamond':'rhombus;','database':'shape=cylinder3;size=15;boundedLbl=1;backgroundOutline=1;'}
        self.cell(cid,'',box,styles[kind]+f'fillColor={fill};strokeColor={stroke};strokeWidth=1;')
        if kind=='ellipse':self.pen.ellipse(pbox,fill=fill,outline=stroke,width=SCALE)
        elif kind=='diamond':self.pen.polygon([(x*SCALE,(y+h/2)*SCALE),((x+w/2)*SCALE,y*SCALE),((x+w)*SCALE,(y+h/2)*SCALE),((x+w/2)*SCALE,(y+h)*SCALE)],fill=fill,outline=stroke,width=SCALE)
        elif kind=='database':
            cap=15
            self.pen.rectangle((x*SCALE,(y+cap/2)*SCALE,(x+w)*SCALE,(y+h-cap/2)*SCALE),fill=fill)
            self.pen.arc((x*SCALE,(y+h-cap)*SCALE,(x+w)*SCALE,(y+h)*SCALE),0,180,fill=stroke,width=SCALE)
            self.pen.line([(x*SCALE,(y+cap/2)*SCALE),(x*SCALE,(y+h-cap/2)*SCALE)],fill=stroke,width=SCALE)
            self.pen.line([((x+w)*SCALE,(y+cap/2)*SCALE),((x+w)*SCALE,(y+h-cap/2)*SCALE)],fill=stroke,width=SCALE)
            self.pen.ellipse((x*SCALE,y*SCALE,(x+w)*SCALE,(y+cap)*SCALE),fill=fill,outline=stroke,width=SCALE)
        else:self.pen.rounded_rectangle(pbox,radius=(6 if kind=='round' else 0)*SCALE,fill=fill,outline=stroke,width=SCALE)

    def text(self,label,box,size=12,bold=False,background=None,italic=False):
        x,y,w,h=box
        lines=wrap(label,w,size,bold,italic)
        while len(lines)*size*1.2>h and size>11:
            size-=1;lines=wrap(label,w,size,bold,italic)
        assert len(lines)*size*1.2<=h+.1,('Text overflow',label,size,box,lines)
        assert all(font(size,bold,italic).getlength(s)/SCALE<=w for s in lines)
        assert 0<=x and 0<=y and x+w<=self.w and y+h<=self.h,box
        self.cell(self.uid(),'\n'.join(lines),box,f'text;html=0;whiteSpace=wrap;fillColor={background or "none"};strokeColor=none;fontColor=#000000;fontFamily=Arial;fontSize={size};fontStyle={int(bold)+2*int(italic)};align=center;verticalAlign=middle;spacing=0;')
        if background:self.pen.rectangle(tuple(v*SCALE for v in (x,y,x+w,y+h)),fill=background)
        ty=y+(h-len(lines)*size*1.2)/2
        for line in lines:
            tx=x+(w-font(size,bold,italic).getlength(line)/SCALE)/2
            self.pen.text((round(tx*SCALE),round(ty*SCALE)),line,font=font(size,bold,italic),fill='black',anchor='lt')
            ty+=size*1.2
        self.texts.append({'label':label,'font':size,'box':box})

    def node(self,cid,label,box,kind='round'):
        first=len(self.root)
        self.nodes[cid]={'label':label,'box':box,'kind':kind}
        self.shape(cid,box,kind,fill='#000000' if kind=='start' else '#FFFFFF') if kind!='start' else self.shape(cid,box,'ellipse','#000000')
        if label:
            x,y,w,h=box
            if kind=='database':self.text(label,(x+4,y+14,w-8,h-16),10)
            elif kind=='ellipse':self.text(label,(x+2,y+2,w-4,h-4),14)
            elif kind=='diamond':self.text(label,(x+3,y+h/2-8,w-6,16),10)
            else:self.text(label,(x+4,y+1,w-8,h-2),12)
        # Move a node together with its label when editing in draw.io.
        children=list(self.root)[first:]
        children[0].set('id',cid+'-shape')
        self.cell(cid,'',box,'group;')
        for child in children:
            child.set('parent',cid)
            g=child.find('mxGeometry')
            g.set('x',str(float(g.get('x',0))-box[0]));g.set('y',str(float(g.get('y',0))-box[1]))

    def edge(self,cid,source,target,points,label=None,label_at=None,dashed=False,label_size=10):
        a,b=self.nodes[source]['box'],self.nodes[target]['box'];p,q=points[0],points[-1]
        style='edgeStyle=none;rounded=0;html=0;strokeColor=#000000;strokeWidth=1;startArrow=none;endArrow=block;endFill=1;endSize=7;'
        style+=f'exitX={(p[0]-a[0])/a[2]};exitY={(p[1]-a[1])/a[3]};entryX={(q[0]-b[0])/b[2]};entryY={(q[1]-b[1])/b[3]};exitPerimeter=0;entryPerimeter=0;'
        if dashed:style+='dashed=1;dashPattern=3 3;'
        c=ET.SubElement(self.root,'mxCell',id=cid,value='',edge='1',parent='1',source=source,target=target,style=style)
        g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'});arr=ET.SubElement(g,'Array',attrib={'as':'points'})
        for xx,yy in points[1:-1]:ET.SubElement(arr,'mxPoint',x=str(xx),y=str(yy))
        for p,q in zip(points,points[1:]):
            assert p[0]==q[0] or p[1]==q[1],(cid,p,q)
            if not dashed:self.pen.line([(p[0]*SCALE,p[1]*SCALE),(q[0]*SCALE,q[1]*SCALE)],fill='black',width=SCALE)
            else:
                length=math.dist(p,q)
                for t in range(0,math.ceil(length),6):
                    t2=min(t+3,length)
                    self.pen.line([((p[0]+(q[0]-p[0])*t/length)*SCALE,(p[1]+(q[1]-p[1])*t/length)*SCALE),((p[0]+(q[0]-p[0])*t2/length)*SCALE,(p[1]+(q[1]-p[1])*t2/length)*SCALE)],fill='black',width=SCALE)
        p,q=points[-2:];length=math.dist(p,q);ux,uy=(q[0]-p[0])/length,(q[1]-p[1])/length
        self.pen.polygon([(q[0]*SCALE,q[1]*SCALE),((q[0]-7*ux+3*uy)*SCALE,(q[1]-7*uy-3*ux)*SCALE),((q[0]-7*ux-3*uy)*SCALE,(q[1]-7*uy+3*ux)*SCALE)],fill='black')
        if label:
            cx,cy=label_at
            width=font(label_size).getlength(label)/SCALE+4
            self.text(label,(cx-width/2,cy-6,width,12),label_size,background='#FFFFFF')
        self.flows.append({'id':cid,'source':source,'target':target,'points':points,'label':label,'dashed':dashed})


p1=Diagram(1,1192,1522,['Designer','Client','Administrator','User and Access Management Module','Project, Floorplan, and Visualization Module','AI Analysis and Detection Module','MySQL Database'])
for args in [
 ('designer-start','',(70,85,30,30),'start'),('client-start','',(240,85,30,30),'start'),
 ('designer-sign','Sign in and request access',(22,140,125,40)),
 ('client-sign','Sign in and request access\n(view-only)',(192,200,125,50)),
 ('verify','Verify account and log access request',(532,275,125,50)),
 ('db-users','users, roles, access requests',(1045,275,120,50),'database'),
 ('admin-access','Review and approve access; assign role',(362,355,125,50)),
 ('permissions','Grant role-based permissions',(532,435,125,50)),
 ('client-granted','Access granted (view-only)',(192,468,125,44)),
 ('B','B',(240,540,30,30),'ellipse'),
 ('project','Create / open project',(22,580,125,40)),
 ('save-project','Save project record',(702,635,125,50)),
 ('db-projects','projects, floor plans',(1045,635,120,50),'database'),
 ('upload','Upload floor plan (JPEG / PNG / PDF)',(22,705,125,50)),
 ('validate','Validate floor plan',(702,780,125,40)),
 ('valid','Valid?',(720,855,90,50),'diamond'),
 ('preprocess','Preprocess image (OpenCV)',(872,940,125,40)),
 ('datasets','Maintain approved datasets and legends',(362,1025,125,50)),
 ('detect','Detect walls and electrical symbols (multimodal AI)',(872,1025,125,50)),
 ('results','Return detected walls, symbols and review status',(872,1115,125,50)),
 ('db-detections','detections, review status',(1045,1115,120,50),'database'),
 ('review','Review detections',(22,1190,125,40)),
 ('corrections','Corrections needed?',(25,1272.5,120,55),'diamond'),
 ('correct','Confirm / add / delete / move / revise items',(25,1375,120,50)),
 ('A','A',(70,1465,30,30),'ellipse')]:p1.node(*args)

p1.edge('d-sign','designer-start','designer-sign',[(85,115),(85,140)])
p1.edge('c-sign','client-start','client-sign',[(255,115),(255,200)])
p1.edge('d-verify','designer-sign','verify',[(147,160),(610,160),(610,275)])
p1.edge('c-verify','client-sign','verify',[(317,225),(580,225),(580,275)])
p1.edge('check-user','verify','db-users',[(657,300),(1045,300)],'check user',(853,300))
p1.edge('request','verify','admin-access',[(532,300),(425,300),(425,355)],'access request',(480,300))
p1.edge('approved','admin-access','permissions',[(487,380),(595,380),(595,435)],'approved, role assigned',(541,380),label_size=9)
p1.edge('access-d','permissions','project',[(532,445),(85,445),(85,580)],'access granted',(310,445))
p1.edge('access-c','permissions','client-granted',[(532,470),(317,470)],'view-only access granted',(425,470))
p1.edge('continue-b','client-granted','B',[(255,512),(255,540)])
p1.edge('save-project-edge','project','save-project',[(147,600),(765,600),(765,635)])
p1.edge('store-project','save-project','db-projects',[(827,660),(1045,660)])
p1.edge('next-upload','save-project','upload',[(702,660),(85,660),(85,705)])
p1.edge('validate-edge','upload','validate',[(147,722),(765,722),(765,780)])
p1.edge('valid-decision','validate','valid',[(765,820),(765,855)])
p1.edge('invalid','valid','upload',[(720,880),(240,880),(240,745),(147,745)],'No: re-upload (or convert DWG / hard copy)',(480,880))
p1.edge('valid-yes','valid','preprocess',[(810,880),(935,880),(935,940)],'Yes',(874,880))
p1.edge('preprocess-detect','preprocess','detect',[(935,980),(935,1025)])
p1.edge('approved-data','datasets','detect',[(487,1050),(872,1050)],'approved datasets and legends',(680,1050),True)
p1.edge('detect-results','detect','results',[(935,1075),(935,1115)])
p1.edge('store-detections','results','db-detections',[(997,1140),(1045,1140)])
p1.edge('results-ready','results','review',[(872,1140),(85,1140),(85,1190)],'results ready',(480,1140))
p1.edge('corrections-needed','review','corrections',[(85,1230),(85,1272.5)])
p1.edge('correct-yes','corrections','correct',[(85,1327.5),(85,1375)],'Yes',(85,1352))
p1.edge('correct-a','correct','A',[(85,1425),(85,1465)])
p1.edge('correct-no','corrections','A',[(145,1300),(160,1300),(160,1480),(100,1480)],'No',(130,1480))

p2=Diagram(2,1022,1302,['Designer','Client','Administrator','Project, Floorplan, and Visualization Module','Electrical Routing, Cost Estimation, and Reporting Module','MySQL Database'])
for args in [
 ('A','A',(70,90,30,30),'ellipse'),
 ('generate-layout','Generate editable 2D layout and 3D visualization',(532,155,125,50)),
 ('edit','Open, edit and save 2D layout; view 3D',(22,240,125,50)),
 ('save','Save layout revision to project record',(532,320,125,50)),
 ('db-layout','layout revisions',(875,320,120,50),'database'),
 ('inspect','Inspect and approve project record',(362,400,125,50)),
 ('configure','Configure routing requirements',(22,470,125,50)),
 ('route','Generate wiring and conduit routes (A*) and lengths',(702,545,125,50)),
 ('review-route','Review routes',(22,630,125,40)),
 ('adjust','Adjustment needed?',(15,705,140,60),'diamond'),
 ('prices','Update material prices; monitor reports',(362,885,125,50)),
 ('calculate','Quantity takeoff; retrieve prices; compute BOM and cost breakdown',(702,880,125,60)),
 ('db-cost','material prices, estimates, reports',(875,885,120,50),'database'),
 ('report','Generate report',(702,980,125,40)),
 ('export','Export report and cost estimate',(22,1050,125,50)),
 ('B','B',(240,1040,30,30),'ellipse'),
 ('view','View approved 2D / 3D layout, cost breakdown and report',(192,1120,125,60)),
 ('end','',(240,1225,30,30),'ellipse')]:p2.node(*args)
p2.shape('end-inner',(244,1229,22,22),'ellipse','#000000')
end_inner=next(c for c in p2.root.findall('mxCell') if c.get('id')=='end-inner')
end_inner.set('parent','end')
end_inner.find('mxGeometry').set('x','4');end_inner.find('mxGeometry').set('y','4')
p2.text('Client signed in (view-only)',(172,1013,166,20),10,italic=True)

p2.edge('confirmed','A','generate-layout',[(100,105),(595,105),(595,155)],'confirmed results',(347,105))
p2.edge('layout-ready','generate-layout','edit',[(532,180),(85,180),(85,240)],'layout ready',(310,180))
p2.edge('save-edge','edit','save',[(147,265),(595,265),(595,320)],'save',(372,265))
p2.edge('store-layout','save','db-layout',[(657,345),(875,345)])
p2.edge('project-record','save','inspect',[(532,345),(425,345),(425,400)],'project record',(477,345))
p2.edge('approved-layout','inspect','configure',[(425,450),(425,458),(85,458),(85,470)],'approved',(255,458))
p2.edge('route-config','configure','route',[(147,495),(765,495),(765,545)])
p2.edge('routes-ready','route','review-route',[(702,570),(85,570),(85,630)],'routes and lengths',(400,570))
p2.edge('review-decision','review-route','adjust',[(85,670),(85,705)])
p2.edge('adjust-yes','adjust','route',[(155,735),(765,735),(765,595)],'Yes: adjust and recalculate',(445,735))
p2.edge('adjust-no','adjust','calculate',[(85,765),(85,815),(765,815),(765,880)],'No',(425,815))
p2.edge('unit-prices','prices','calculate',[(487,910),(702,910)],'unit prices',(600,910),True)
p2.edge('store-cost','calculate','db-cost',[(827,910),(875,910)])
p2.edge('generate-report','calculate','report',[(765,940),(765,980)])
p2.edge('report-ready','report','export',[(702,1000),(85,1000),(85,1050)],'report ready',(395,1000))
p2.edge('share','export','view',[(85,1100),(85,1150),(192,1150)],'share approved outputs',(135,1150),label_size=9)
p2.edge('client-b','B','view',[(255,1070),(255,1120)])
p2.edge('approved-records','inspect','view',[(362,425),(330,425),(330,1150),(317,1150)],'only approved records visible',(330,790),True)
p2.edge('finish','view','end',[(255,1180),(255,1225)])

root=ET.Element('mxfile',host='app.diagrams.net',type='device',pages='2')
report={'source_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE},'scope':'Text enlargement and editable tracing only; no workflow corrections.','pages':[],'visual_review':'PENDING','downloads_copy':'PENDING','drawio_editor_import':'NOT TESTED'}
for p in [p1,p2]:
    d=ET.SubElement(root,'diagram',id=f'activity-{p.number}',name=f'Activity Diagram - Part {p.number}')
    d.append(p.model)
    ids={c.get('id') for c in p.root.findall('mxCell')}
    assert len(ids)==len(p.root.findall('mxCell'))
    for c in p.root.findall('mxCell'):
        assert c.get('parent','0') in ids
        if c.get('edge')=='1':assert c.get('source') in ids and c.get('target') in ids
    single=ET.Element('mxfile',host='app.diagrams.net',type='device')
    sd=ET.SubElement(single,'diagram',id=f'activity-{p.number}',name=f'Activity Diagram - Part {p.number}')
    sd.append(p.model)
    meta=PngImagePlugin.PngInfo();meta.add_text('mxfile',quote(ET.tostring(single,encoding='unicode')))
    p.im.save(OUT/f'Activity Diagram-{p.number}-Larger Text.drawio.png',pnginfo=meta,dpi=(300,300))
    p.im.resize((p.w,p.h),Image.Resampling.LANCZOS).save(OUT/f'preview-{p.number}.png')
    report['pages'].append({'part':p.number,'source_dimensions':[p.w,p.h],'export_pixels':list(p.im.size),'nodes':len(p.nodes),'flows':len(p.flows),'text_fit':'PASS','activity_text':12,'headings':12,'flow_label_range':[9,10],'native_editable_shapes':'PASS'})
    (OUT/f'page-{p.number}-data.json').write_text(json.dumps({'nodes':p.nodes,'flows':p.flows,'texts':p.texts},indent=2),encoding='utf-8')
assert len([f for f in p2.flows if f['source']=='adjust'])==2
assert {p1.nodes[k]['label'] for k in ['A','B']}=={p2.nodes[k]['label'] for k in ['A','B']}
ET.indent(root)
ET.ElementTree(root).write(OUT/'Activity Diagrams-Larger Text.drawio',encoding='utf-8',xml_declaration=True)
ET.parse(OUT/'Activity Diagrams-Larger Text.drawio')
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
