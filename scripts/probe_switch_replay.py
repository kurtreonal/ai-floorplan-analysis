"""Full drawing-panel switch probes; partial-label precision stays unscored."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO
from prepare_authored_legend_extension import digest
from prepare_authorized_pdf_detection import validate_training_sources
from probe_symbol_detector_dev import match_targets, validate_model_classes
from probe_authorized_pdf_detection import score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ai.floor_plan_interpretation.experimental_symbol_detector import locate
from app.ai.floor_plan_interpretation import experimental_symbol_detector as detector_runtime
from app.ai.floor_plan_interpretation.legend_equivalence import model_class_groups


def probe(dataset,checkpoint,output, *, capture_raw=False, box_fusion=False):
    dataset,checkpoint,output=map(Path,(dataset,checkpoint,output))
    if output.exists():raise FileExistsError('Probe revisions are immutable')
    data=json.loads((dataset/'manifest.json').read_text());validate_training_sources(dataset,data)
    model=YOLO(str(checkpoint));validate_model_classes(model,data['classes'])
    catalog={'model':model,'threshold':.5,'classes':{r['id']:(r['label'],r['legend_entry']) for r in data['classes']},
             'box_fusion':box_fusion}
    if box_fusion:
        catalog['class_groups']=model_class_groups(catalog['classes'])
    evidence=json.loads((dataset/'switch-inspection.json').read_text())
    views=[]
    for e in evidence['sources']:
        root=Path(e['prepared']);source=json.loads((root/'manifest.json').read_text())
        if digest(root/'manifest.json')!=e['prepared_manifest_sha256']:raise ValueError('Prepared identity changed')
        name='lighting-layout' if e['page_number']==7 else 'p3-third-lighting'
        region=next(r for r in source['regions'] if r['region_id']==name)
        if digest(root/region['filename'])!=region['crop_sha256']:raise ValueError('Panel changed')
        targets=[t for t in data['switch_source_targets'] if t['source_sha256']==e['source_image_sha256']]
        views.append((e['source_sha256'][:12],root/region['filename'],region['bbox_source_pixels'][:2],targets))
    e=evidence['upload'];path=dataset/'original-upload.png'
    if digest(path)!=e['source_sha256']:raise ValueError('Upload changed')
    views.append(('upload',path,[0,0],[t for t in data['switch_source_targets'] if t['source_sha256']==e['source_sha256']]))
    output.mkdir(parents=True);results=[]
    for name,path,origin,targets in views:
        with Image.open(path) as opened:image=opened.convert('RGB')
        observations=[]
        original_fuse=detector_runtime.fuse
        def observe(rows, **kwargs):
            observations.extend(dict(row) for row in rows)
            return original_fuse(rows, **kwargs)
        if capture_raw:
            with patch.object(detector_runtime, 'fuse', side_effect=observe):
                raw,truncated=locate(np.asarray(image),catalog=catalog)
        else:
            raw,truncated=locate(np.asarray(image),catalog=catalog)
        x,y=origin
        predictions=[{**p,'bbox':[p['bbox'][0]+x,p['bbox'][1]+y,p['bbox'][2]+x,p['bbox'][3]+y]} for p in raw]
        matches=match_targets(targets,predictions);pen=ImageDraw.Draw(image)
        for i,t in enumerate(targets):
            a,b,c,d=t['source_box'];pen.rectangle([a-x,b-y,c-x,d-y],outline='green' if i in matches else 'red',width=2)
        for p in raw:
            pen.rectangle(p['bbox'],outline='blue',width=1)
            pen.text(p['bbox'][:2],str(p['class_id']),fill='blue')
        image.save(output/f'{name}-overlay.png');image.close()
        results.append({'source':name,'truncated':truncated,'targets':targets,'predictions':predictions,
            **({'raw_observations':[ {**p, 'bbox':[p['bbox'][0]+x,p['bbox'][1]+y,
                    p['bbox'][2]+x,p['bbox'][3]+y], 'tile_origin':[p['tile_origin'][0]+x,p['tile_origin'][1]+y]}
                    for p in observations]} if capture_raw else {}),
            'summary':score(targets,predictions),'per_class':[{'class_id':cls,
            'label':data['classes'][cls]['label'],'prediction_count':sum(p['class_id']==cls for p in predictions),
            **score([t for t in targets if t['class_id']==cls],predictions)} for cls in (62,63,64)]})
    report={'kind':'switch_grid_phase_same_source_development_probe_v1',
        'dataset_manifest_sha256':digest(dataset/'manifest.json'),'checkpoint_sha256':digest(checkpoint),
        'threshold':.5,'matching':'maximum one-to-one class-aware IoU >= .50',
        'raw_observations_captured':capture_raw,
        'box_fusion':box_fusion,
        'region_rule':'Complete pre-recorded lighting panels; exact upload including title, independent of target positions.',
        'sources':results,'precision':None,'independent_accuracy':None,'human_review_claim':False,
        'scope':'Same training sources; PDF and derivative upload are one project. All proposals unresolved.'}
    (output/'report.json').write_text(json.dumps(report,indent=2))
    return {r['source']:r['summary'] for r in results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','checkpoint','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--capture-raw',action='store_true')
    parser.add_argument('--box-fusion',action='store_true')
    args=parser.parse_args()
    import torch
    torch.set_num_threads(4)
    print(json.dumps(probe(args.dataset,args.checkpoint,args.output,capture_raw=args.capture_raw,box_fusion=args.box_fusion)))
