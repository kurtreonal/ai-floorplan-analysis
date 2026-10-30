"""Frozen, partial-label source-panel check; not independent accuracy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

from prepare_authored_legend_extension import digest
from probe_symbol_detector_dev import validate_model_classes, match_targets
from probe_authorized_pdf_detection import score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
from ultralytics import YOLO


def select_lamp_view(dataset, data, prepared=None, *, upload=False):
    """Hash-bound view/targets; derivative coordinates are not PDF coordinates."""
    if upload:
        source=json.loads((dataset/'upload-preparation.json').read_text())
        path=dataset/'original-upload.png'
        region={'region_id':'full-upload','bbox_source_pixels':[0,0]}
        targets=data['lamp_upload_targets']
        expected_hash=source['source_sha256']
    else:
        prepared=Path(prepared)
        source=json.loads((prepared/'manifest.json').read_text())
        region=next(r for r in source['regions'] if r['region_id']=='lighting-layout')
        path=prepared/region['filename']
        targets=data['lamp_source_targets']
        expected_hash=region['crop_sha256']
    valid_targets=(all(t['source_sha256']==source['source_sha256'] for t in targets) if upload else
                   all(t['pdf_sha256']==source['source_sha256']
                       and t['source_sha256']==region['source_image_sha256']
                       and t['page_number']==region['page_number'] for t in targets))
    if digest(path)!=expected_hash or not valid_targets:
        raise ValueError('Source image or target identity changed')
    return source,region,path,targets


def coverage(dataset, checkpoint, reports, output):
    """Every head identity, with source-specific measurements kept separate."""
    dataset,checkpoint,output=map(Path,(dataset,checkpoint,output))
    if output.exists():raise FileExistsError('Coverage revisions are immutable')
    data=json.loads((dataset/'manifest.json').read_text())
    if (data.get('all_eligible_entries') is not True or data.get('diagnostic_only')
            or {r['id'] for r in data['classes']}!=set(range(80))
            or any(r['samples']<1 for r in data['classes'])):
        raise ValueError('Coverage requires the complete supervised eighty-entry head')
    expected=digest(checkpoint); manifest_hash=digest(dataset/'manifest.json')
    counts={name:Counter(t['class_id'] for t in data.get(key,[]))
            for name,key in (('original_reviewed','reviewed_targets'),('delegated_pdf','authorized_pdf_targets'),
                             ('dependent_upload','lamp_upload_targets'))}
    counts['dependent_upload_switches']=Counter(t['class_id'] for t in data.get('switch_source_targets',[])
                                               if 'parent_pdf_sha256' in t)
    measurements={}
    for name,path in reports.items():
        report=json.loads(Path(path).read_text())
        if report['checkpoint_sha256']!=expected or report['dataset_manifest_sha256']!=manifest_hash:
            raise ValueError('Coverage cannot mix checkpoints or dataset revisions')
        if 'sources' in report:
            for source in report['sources']:
                measurements[f"{name}/{source['source']}"]={
                    'predictions':Counter(p['class_id'] for p in source['predictions']),
                    'matched':{r['class_id']:r['localized_and_classified'] for r in source['per_class']},
                    'report_sha256':digest(Path(path))}
            continue
        predictions=[];matched={}
        if 'pages' in report:
            predictions=[p for page in report['pages'] for p in page['predictions']]
            matched={r['class_id']:r['localized_and_classified'] for r in report['summary']['per_class']}
        elif 'regions' in report:
            predictions=[p for region in report['regions'] for p in region['predictions']]
            matched={r['class_id']:r['localized_and_classified'] for r in report['legend_entries']}
        else:
            predictions=report['predictions']
            matched={r['class_id']:r['localized_and_classified'] for r in report['per_class']}
        measurements[name]={'predictions':Counter(p['class_id'] for p in predictions),'matched':matched,
                            'report_sha256':digest(Path(path))}
    rows=[]
    for cls in data['classes']:
        class_id=cls['id']
        rows.append({**cls,'included_in_training':True,
            'source_legend_aliases':sorted({t['source_legend_entry'] for t in data.get('switch_source_targets',[])
                                           if t['class_id']==class_id}),
            'real_source_box_counts':{name:value[class_id] for name,value in counts.items()},
            'same_source_probes':{name:{'prediction_count':value['predictions'][class_id],
                                        'class_and_location_matches':value['matched'].get(class_id)}
                                  for name,value in measurements.items()},
            'limitations':['Partial labels: unmatched proposals are unresolved, precision is unscored.',
                           'Source-dependent development checks, not independent project evaluation.',
                           *(['No real source boxes for this class; legend/synthetic supervision only.']
                             if not any(value[class_id] for value in counts.values()) else [])]})
    output.mkdir(parents=True)
    (output/'report.json').write_text(json.dumps({'kind':'all_entry_development_coverage_v1',
        'checkpoint_sha256':expected,'dataset_manifest_sha256':manifest_hash,
        'precision':None,'independent_accuracy':None,'entries':rows,
        'probe_hashes':{name:value['report_sha256'] for name,value in measurements.items()}},indent=2))
    return {'entries':len(rows),'real_positive_class_count':sum(any(v[r['id']] for v in counts.values()) for r in rows)}


def probe(dataset, prepared, checkpoint, output, *, baseline=False, upload=False, box_fusion=False):
    dataset,checkpoint,output = map(Path,(dataset,checkpoint,output))
    if output.exists():
        raise FileExistsError('Probe results are immutable')
    if checkpoint.stat().st_size > 30_000_000:
        raise ValueError('Checkpoint exceeds bound')
    data = json.loads((dataset/'manifest.json').read_text())
    source,region,path,targets=select_lamp_view(dataset,data,prepared,upload=upload)
    model = YOLO(str(checkpoint))
    classes = runtime.verify_artifacts() if baseline else {r['id']:(r['label'],r['legend_entry']) for r in data['classes']}
    if baseline:
        if digest(checkpoint)!=runtime.CHECKPOINT_SHA256:
            raise ValueError('Expected exact active baseline')
    else:
        validate_model_classes(model,data['classes'])
    with Image.open(path) as opened:
        image = opened.convert('RGB')
    predictions,truncated = runtime.shared.locate(np.asarray(image),catalog={
        'classes':classes,'model':model,'threshold':.50,
        **({'box_fusion':True,'class_groups':runtime.model_class_groups(classes)} if box_fusion else {})})
    x,y = region['bbox_source_pixels'][:2]
    converted = [{**p,'bbox':[p['bbox'][0]+x,p['bbox'][1]+y,p['bbox'][2]+x,p['bbox'][3]+y]} for p in predictions]
    matches = match_targets(targets,converted)
    pen = ImageDraw.Draw(image)
    for i,t in enumerate(targets):
        a,b,c,d = t['source_box']
        pen.rectangle((a-x,b-y,c-x,d-y),outline='green' if i in matches else 'red',width=3)
    for p in predictions:
        pen.rectangle(p['bbox'],outline='blue',width=2)
        pen.text(p['bbox'][:2],f"{p['class_id']}",fill='blue')
    report = {'kind':'partial_assistant_inspected_lamp_training_source_check_v1',
        'checkpoint_sha256':digest(checkpoint),'dataset_manifest_sha256':digest(dataset/'manifest.json'),
        'source_sha256':source['source_sha256'],'page_number':1 if upload else 7,'region':region['region_id'],
        'source_scope':'entire uploaded image' if upload else 'PDF lighting panel',
        'threshold':.50,'matching':'one-to-one IoU >= 0.50','truncated':truncated,
        'box_fusion':box_fusion,
        'annotation_origin':'assistant_visual_under_user_development_authorization',
        'human_review_claim':False,'independent_accuracy':None,'precision':None,
        'predictions':converted,'prediction_counts':dict(Counter(classes[p['class_id']][0] for p in predictions)),
        'summary':score(targets,converted),
        'per_class':[{ 'class_id':i,'label':data['classes'][i]['label'],
            **score([t for t in targets if t['class_id']==i],converted)} for i in (56,57)],
        'interpretation':'Partial labeled source panel used for development; no global precision or held-out accuracy.'}
    output.mkdir(parents=True); image.save(output/'overlay.png'); image.close()
    (output/'report.json').write_text(json.dumps(report,indent=2))
    return {**report['summary'],'predictions':len(predictions),'prediction_counts':report['prediction_counts']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--prepared',type=Path)
    parser.add_argument('--upload',action='store_true')
    parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--box-fusion',action='store_true')
    args=parser.parse_args()
    if args.upload == bool(args.prepared):
        parser.error('Choose either --upload or --prepared')
    import torch
    torch.set_num_threads(4)
    print(json.dumps(probe(args.dataset,args.prepared,args.checkpoint,args.output,baseline=args.baseline,
                           upload=args.upload,box_fusion=args.box_fusion)))
