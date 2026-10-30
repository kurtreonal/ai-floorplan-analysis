"""Same-source delegated-label learning check; never independent accuracy."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
from prepare_authored_legend_extension import digest
from probe_symbol_detector_dev import match_targets, validate_model_classes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ai.floor_plan_interpretation.experimental_symbol_detector import locate
from ultralytics import YOLO


def score(targets,predictions):
    localized=match_targets(targets,predictions,require_class=False)
    classified=match_targets(targets,predictions)
    return {'targets':len(targets),'localized':len(localized),'localized_and_classified':len(classified),
            'localization_recall':len(localized)/len(targets) if targets else None,
            'class_recall':len(classified)/len(targets) if targets else None,
            'precision':None,'independent_accuracy':None}


def select_source_targets(manifest, source):
    # A replay manifest can contain several PDFs. Page numbers/coordinates alone
    # cannot identify a source, and must never inflate this probe's denominator.
    return [t for t in manifest['authorized_pdf_targets'] if t['pdf_sha256']==source['source_sha256']]


def probe(dataset,prepared,checkpoint,output):
    dataset,prepared,checkpoint,output=map(Path,(dataset,prepared,checkpoint,output))
    if output.exists():raise FileExistsError('Probe revisions are immutable')
    manifest=json.loads((dataset/'manifest.json').read_text())
    source=json.loads((prepared/'manifest.json').read_text())
    source_targets=select_source_targets(manifest,source)
    authorized=any(r['source_sha256']==source['source_sha256']
                   and r['prepared_manifest_sha256']==digest(prepared/'manifest.json')
                   for r in manifest['additional_training_authorizations'])
    if checkpoint.stat().st_size>30_000_000 or not authorized:
        raise ValueError('Probe source identity or checkpoint bounds differ')
    model=YOLO(str(checkpoint));validate_model_classes(model,manifest['classes'])
    catalog={'model':model,'threshold':.50,'classes':{r['id']:(r['label'],r['legend_entry']) for r in manifest['classes']}}
    output.mkdir(parents=True)
    predictions=[];outcomes=[]
    # Source layout panel boundaries selected during PDF inspection, not target boxes.
    for region in source['regions']:
        if region['region_id'] not in ('p3-third-lighting','p3-third-power'):continue
        path=prepared/region['filename']
        if digest(path)!=region['crop_sha256']:raise ValueError('Probe layout crop changed')
        with Image.open(path) as opened:image=opened.convert('RGB')
        found,truncated=locate(np.asarray(image),catalog=catalog)
        x,y=region['bbox_source_pixels'][:2]
        converted=[{**r,'bbox':[r['bbox'][0]+x,r['bbox'][1]+y,r['bbox'][2]+x,r['bbox'][3]+y]} for r in found]
        predictions.extend(converted)
        bounds=region['bbox_source_pixels']
        targets=[r for r in source_targets if bounds[0]<=r['source_box'][0]<r['source_box'][2]<=bounds[2]
                 and bounds[1]<=r['source_box'][1]<r['source_box'][3]<=bounds[3]]
        matches=match_targets(targets,converted)
        pen=ImageDraw.Draw(image)
        for i,target in enumerate(targets):
            a,b,c,d=target['source_box'];pen.rectangle((a-x,b-y,c-x,d-y),outline='green' if i in matches else 'red',width=3)
        for r in found:
            pen.rectangle(r['bbox'],outline='blue',width=2)
            pen.text(r['bbox'][:2],str(r['class_id']),fill='blue')
        image.save(output/(region['region_id']+'-overlay.png'));image.close()
        outcomes.append({'region':region['region_id'],'truncated':truncated,'predictions':converted,**score(targets,converted)})
    report={'kind':'authorized_development_pdf_same_source_learning_check_v1',
        'dataset_manifest_sha256':digest(dataset/'manifest.json'),'checkpoint_sha256':digest(checkpoint),
        'threshold':.50,'matching':'maximum one-to-one IoU >= 0.50',
        'annotation_origin':'assistant_visual_under_user_development_authorization','human_review_claim':False,
        'full_page_scope':'two complete inspected drawing panels; titles/legend blocks excluded by panel rule',
        'precision':None,'independent_accuracy':None,'regions':outcomes,
        'summary':score(source_targets,predictions),'legend_entries':[]}
    for name,row in manifest['pdf_source_legend_mappings'].items():
        targets=[r for r in source_targets if r['legend_entry']==row['legend_entry']]
        report['legend_entries'].append({'region_id':name,**row,'label':manifest['classes'][row['class_id']]['label'],
            'prediction_count':sum(p['class_id']==row['class_id'] for p in predictions),**score(targets,predictions)})
    report['excluded_wiring_entries']=manifest['pdf_wiring_entries_excluded_from_devices']
    (output/'report.json').write_text(json.dumps(report,indent=2))
    return report['summary']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','prepared','checkpoint','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    import torch
    torch.set_num_threads(4)
    print(json.dumps(probe(args.dataset,args.prepared,args.checkpoint,args.output)))
