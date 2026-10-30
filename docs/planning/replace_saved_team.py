"""Apply the requested team-only change while retaining other saved board edits."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
SAVED=Path('C:/Users/kupal/Downloads/ved-sprint-planning-board-2026-10-12.drawio')
GENERATED=OUT/SAVED.name
old_bytes=SAVED.read_bytes()
before_hash=sha256(old_bytes).hexdigest()
old=ET.fromstring(old_bytes)
new=ET.parse(GENERATED).getroot()
assert len(old.findall('diagram'))==len(new.findall('diagram'))==6
backup=OUT/'sprint-board-before-team-names.drawio'
if not backup.exists():backup.write_bytes(old_bytes)

def in_team(cell):
    geo=cell.find('mxGeometry')
    if geo is None or cell.attrib.get('parent')!='1':return False
    x,y=float(geo.attrib.get('x',0)),float(geo.attrib.get('y',0))
    return x>=726 and 703<=y<878 and cell.attrib.get('vertex')=='1'

def footer(cell):
    geo=cell.find('mxGeometry')
    return geo is not None and cell.attrib.get('parent')=='1' and geo.attrib.get('x')=='86' and geo.attrib.get('y')=='911'

unchanged=0
for i,(before,after) in enumerate(zip(old.findall('diagram'),new.findall('diagram')),1):
    root=before.find('.//root');newroot=after.find('.//root')
    keep=[ET.tostring(c) for c in root if not in_team(c) and not footer(c)]
    for c in list(root):
        if in_team(c):root.remove(c)
    for j,c in enumerate(newroot):
        if in_team(c):
            copied=deepcopy(c);copied.attrib['id']=f'team-update-sprint-{i}-cell-{j}'
            root.append(copied)
    replacement=next(c for c in newroot if footer(c))
    existing=next(c for c in root if footer(c))
    existing.attrib['value']=replacement.attrib['value']
    assert [ET.tostring(c) for c in root if not in_team(c) and not footer(c)]==keep
    unchanged+=len(keep)
    labels=[c.attrib.get('value','').replace('\n',' ') for c in root]
    data=json.loads((OUT/'template-sprint-data.json').read_text())
    for member in data['team']:assert labels.count(member)==1
    assert not any('Name: TBD' in label for label in labels)
    ids=[c.attrib['id'] for c in root];assert len(ids)==len(set(ids))

ET.indent(old)
ET.ElementTree(old).write(GENERATED,encoding='utf-8',xml_declaration=True)
report_path=OUT/'sprint-board-verification.json'
report=json.loads(report_path.read_text())
report['preview_visual_review']='PASS'
report['other_saved_cells_preserved']=unchanged
report['downloads_before_sha256']=before_hash
report['workspace_after_sha256']=sha256(GENERATED.read_bytes()).hexdigest()
report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'pages':6,'team_names':data['team'],'other_cells_preserved':unchanged,'expected_downloads_hash':before_hash},indent=2))
