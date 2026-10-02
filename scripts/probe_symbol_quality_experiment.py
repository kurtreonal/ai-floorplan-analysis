"""Compare checkpoints through the shared tiler, without activating either one.

Only class+IoU reviewed-positive recall and explicitly inspected negative-region
proposal counts are measured. Partial-page precision and generalization stay unscored.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
import unicodedata
os.environ['YOLO_OFFLINE'] = 'true'
os.environ['YOLO_AUTOINSTALL'] = 'false'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO
from app.ai.floor_plan_interpretation import experimental_symbol_detector as runtime
from probe_symbol_detector_dev import match_targets, digest


def in_negative(box, regions):
    cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
    return any(a <= cx <= c and b <= cy <= d for a,b,c,d in regions)


def probe(dataset, reviews, source_root, checkpoint, output, reuse_shared_probe=None):
    if output.exists(): raise FileExistsError('Probe versions are immutable')
    manifest = json.loads((dataset/'manifest.json').read_text())
    review = json.loads(reviews.read_text())
    if manifest.get('negative_review_sha256') != digest(reviews): raise ValueError('Review manifest changed')
    classes = {r['id']:(r['label'],r['legend_entry']) for r in manifest['classes']}
    model = YOLO(str(checkpoint))
    expected_names={i:unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
                    for i,(name,_) in classes.items()}
    if model.names != expected_names: raise ValueError('Model numeric class identities differ')
    cached = {}
    if reuse_shared_probe:
        old=json.loads(reuse_shared_probe.read_text())
        if (old.get('checkpoint_sha256') != digest(checkpoint) or old.get('threshold') != .5
                or old.get('shared_runtime') is not True
                or old.get('tiling') != {'size':256,'stride':192,'model_input':320,
                    'second_phase_offset':128,'duplicate_suppression':'same-class IoU >= 0.5'}):
            raise ValueError('Cached probe configuration differs')
        cached={p['source_sha256']:p for p in old['pages']}
    targets = manifest['reviewed_targets']
    sheets = {row['sheet_id']:row['source_sha256'] for row in targets}
    sheets.update({row['sheet_id']:row['source_sha256'] for row in review['sheets']})
    output.mkdir(parents=True)
    pages = []
    for sheet_id, expected in sorted(sheets.items()):
        source = source_root/f'{sheet_id}.jpg'
        if digest(source) != expected: raise ValueError('Source changed')
        with Image.open(source) as opened:
            if max(opened.size)>10000 or opened.width*opened.height>60_000_000: raise ValueError('Source bounds')
            image = opened.convert('RGB')
        start=time.perf_counter()
        if expected in cached:
            predictions=cached[expected]['predictions']; truncated=cached[expected].get('truncated',False)
        else:
            predictions,truncated=runtime.locate(np.asarray(image),catalog={'classes':classes,'model':model,'threshold':0.5})
        seconds=round(time.perf_counter()-start,3)
        if digest(source) != expected: raise ValueError('Source changed during inference')
        selected = [r for r in targets if r['source_sha256']==expected]
        classified=match_targets(selected,predictions)
        localized=match_targets(selected,predictions,require_class=False)
        records=[r for r in review['sheets'] if r['sheet_id']==sheet_id]
        negatives=[[v*(image.width if i%2==0 else image.height) for i,v in enumerate(b)]
                   for r in records for b in r['regions']]
        bad=[i for i,p in enumerate(predictions) if in_negative(p['bbox'],negatives)]
        overlay=image.copy(); draw=ImageDraw.Draw(overlay)
        for i,p in enumerate(predictions):
            draw.rectangle(p['bbox'],outline='red' if i in bad else 'orange',width=2)
            draw.text((p['bbox'][0],p['bbox'][1]),str(p['class_id']),fill='red')
        for i,t in enumerate(selected): draw.rectangle(t['source_box'],outline='green' if i in classified else 'magenta',width=3)
        overlay.thumbnail((1200,2000)); overlay.save(output/f'{sheet_id}-overlay.jpg',quality=90)
        pages.append({'sheet_id':sheet_id,'source_sha256':expected,'seconds':seconds,
                      'cached_predictions':expected in cached,
                      'predictions':predictions,'truncated':truncated,'reviewed_positive_count':len(selected),
                      'class_matches':len(classified),'localization_matches':len(localized),
                      'known_negative_proposals':len(bad),'known_negative_prediction_indices':bad,
                      'matched_by_class':dict(Counter(selected[i]['class_id'] for i in classified)),
                      'matched_record_ids':[selected[i]['record_id'] for i in classified]})
    matched_counts = Counter()
    for page in pages:
        matched_counts.update({int(key): value for key, value in page['matched_by_class'].items()})
    target_counts = Counter(row['class_id'] for row in targets)
    per_class = [{'class_id': i, 'label': name, 'legend_entry': key,
                  'reviewed_positives': target_counts[i],
                  'localized_and_classified': matched_counts[i]}
                 for i, (name, key) in classes.items()]
    result={'checkpoint_sha256':digest(checkpoint),'dataset_sha256':digest(dataset/'manifest.json'),
            'dataset_manifest_sha256':digest(dataset/'manifest.json'),
            'negative_review_sha256':digest(reviews),
            'reused_probe_sha256':digest(reuse_shared_probe) if reuse_shared_probe else None,
            'threshold':0.5,'tiling':'shared 256px/192 stride + bounded 128 offset; 200 proposals cap',
            'precision':None,'independent_accuracy':None,'evaluation':'development / partly training sources',
            'known_negative_rule':'proposal center lies in assistant-inspected non-electrical region',
            'pages':pages,'summary':{'reviewed_positive_count':sum(p['reviewed_positive_count'] for p in pages),
            'class_matches':sum(p['class_matches'] for p in pages),'localization_matches':sum(p['localization_matches'] for p in pages),
            'known_negative_proposals':sum(p['known_negative_proposals'] for p in pages),
            'proposals':sum(len(p['predictions']) for p in pages),'truncated_pages':sum(p['truncated'] for p in pages),
            'per_class':per_class}}
    (output/'report.json').write_text(json.dumps(result,indent=2))
    return {key: value for key, value in result['summary'].items() if key != 'per_class'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','reviews','source-root','checkpoint','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reuse-shared-probe',type=Path)
    args=parser.parse_args()
    print(json.dumps(probe(args.dataset,args.reviews,args.source_root,args.checkpoint,args.output,args.reuse_shared_probe)))
