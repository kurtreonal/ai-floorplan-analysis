"""Frozen power-panel checks; same-source development evidence, not accuracy."""
import argparse
from contextlib import ExitStack, closing
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from prepare_authored_legend_extension import digest
from prepare_power_quality_replay import checked_inspection, validate_power_source
from prepare_authorized_pdf_detection import validate_training_sources
from probe_symbol_detector_dev import match_targets, validate_model_classes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from ultralytics import YOLO


def negative_proposals(predictions, regions):
    return [i for i, p in enumerate(predictions) if any(
        r['box'][0] <= (p['bbox'][0] + p['bbox'][2]) / 2 < r['box'][2]
        and r['box'][1] <= (p['bbox'][1] + p['bbox'][3]) / 2 < r['box'][3] for r in regions)]


def validate_probe_inputs(parent, prepared, inspection, checkpoint, frozen_parent=None):
    parent, prepared, inspection, checkpoint = map(Path, (parent, prepared, inspection, checkpoint))
    if inspection.stat().st_size > 1_048_576 or not 0 < checkpoint.stat().st_size <= 30_000_000:
        raise ValueError('Evidence or checkpoint exceeds resource bound')
    data = json.loads((parent / 'manifest.json').read_text())
    evidence = json.loads(inspection.read_text())
    source, region, path = validate_power_source(prepared, evidence)
    expected = evidence['parent_manifest_sha256']
    if digest(parent / 'manifest.json') != expected:
        if frozen_parent is None or digest(Path(frozen_parent) / 'manifest.json') != expected:
            raise ValueError('Explicit exact frozen parent required for candidate comparison')
        frozen = json.loads((Path(frozen_parent) / 'manifest.json').read_text())
        copies = (parent / 'power-inspection.json', parent / 'power-inspections' / f'{digest(inspection)}.json')
        descendant = data
        ancestor_hash = descendant.get('parent_dataset_sha256')
        seen = set()
        for _ in range(4):
            if ancestor_hash == expected:
                break
            if not isinstance(ancestor_hash, str) or len(ancestor_hash) != 64 or any(c not in '0123456789abcdef' for c in ancestor_hash):
                raise ValueError('Invalid comparison lineage identity')
            if ancestor_hash in seen:
                raise ValueError('Comparison ancestry cycle')
            seen.add(ancestor_hash)
            ancestor_path = parent / 'lineage' / f'{ancestor_hash}.json'
            if not ancestor_path.is_file() or digest(ancestor_path) != ancestor_hash:
                raise ValueError('Exact comparison ancestry parent artifact required')
            ancestor = json.loads(ancestor_path.read_text())
            if (ancestor.get('classes') != frozen.get('classes')
                    or any(descendant.get(key, [])[:len(ancestor.get(key, []))] != ancestor.get(key, [])
                           for key in ('power_source_targets', 'power_negative_regions', 'reviewed_targets',
                                       'authorized_pdf_training_images', 'assistant_reviewed_background_regions'))):
                raise ValueError('Comparison ancestry or original training history changed')
            descendant = ancestor
            ancestor_hash = ancestor.get('parent_dataset_sha256')
        if ancestor_hash != expected:
            raise ValueError('Comparison ancestry exceeds bounded depth')
        if (data.get('classes') != frozen.get('classes')
                or not any(p.is_file() and digest(p) == digest(inspection) for p in copies)):
            raise ValueError('Candidate lineage, class identities or inspection revision changed')
        validate_training_sources(Path(frozen_parent), frozen)
    validate_training_sources(parent, data)
    return data, source, evidence, region, path


def probe(parent, prepared, inspection, checkpoint, output, frozen_parent=None, *, box_fusion=False):
    with ExitStack() as resources:
        return _probe(parent, prepared, inspection, checkpoint, output, frozen_parent, resources, box_fusion)


def _probe(parent, prepared, inspection, checkpoint, output, frozen_parent, resources, box_fusion=False):
    parent, prepared, inspection, checkpoint, output = map(Path, (parent, prepared, inspection, checkpoint, output))
    if output.exists(): raise FileExistsError('Evidence revisions are immutable')
    data, source, evidence, region, path = validate_probe_inputs(parent, prepared, inspection, checkpoint, frozen_parent)
    with Image.open(path) as opened:
        if opened.width * opened.height > 60_000_000:
            raise ValueError('Source exceeds allocation bound')
        image = resources.enter_context(closing(opened.convert('RGB')))
    targets, negatives = checked_inspection(evidence, data, source, region, image.size)
    model = YOLO(str(checkpoint)); validate_model_classes(model, data['classes'])
    classes = {r['id']: (r['label'], r['legend_entry']) for r in data['classes']}
    catalog = {'model': model, 'classes': classes,
               'threshold': .5, 'class_groups': runtime.model_class_groups(classes), 'box_fusion':box_fusion}
    output.mkdir(parents=True); outcomes = []
    for scale in (1, .375):
        view = resources.enter_context(closing(image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)))
        start = time.perf_counter()
        predictions, truncated = runtime.shared.locate(np.asarray(view), catalog=catalog)
        sx, sy = view.width / image.width, view.height / image.height
        converted = [{**p, 'bbox': [p['bbox'][0]/sx, p['bbox'][1]/sy, p['bbox'][2]/sx, p['bbox'][3]/sy]} for p in predictions]
        classified = match_targets(targets, converted)
        localized = match_targets(targets, converted, require_class=False)
        false_indices = negative_proposals(converted, negatives)
        # Run structure on original pixels, never on the symbol overlay.
        walls = interpret_floor_plan_demo(np.asarray(view))
        wall_image = resources.enter_context(closing(view.copy())); wall_pen = ImageDraw.Draw(wall_image)
        for wall in walls.walls.items:
            wall_pen.line((wall.start.x,wall.start.y,wall.end.x,wall.end.y), fill='orange', width=3)
        wall_image.save(output / f'walls-s{round(scale*1000)}.png'); wall_image.close()
        pen = ImageDraw.Draw(view)
        for index, target in enumerate(targets):
            a,b,c,d = target['source_box']
            pen.rectangle((a*sx,b*sy,c*sx,d*sy), outline='green' if index in classified else 'red', width=2)
        for index, p in enumerate(predictions):
            pen.rectangle(p['bbox'], outline='magenta' if index in false_indices else 'blue', width=1)
            pen.text(p['bbox'][:2], str(p['class_id']), fill='blue')
        view.save(output / f'symbols-s{round(scale*1000)}.png')
        outcomes.append({'scale': scale, 'image_size': view.size, 'actual_scale_xy': [sx,sy],
            'seconds': round(time.perf_counter()-start,3), 'predictions': converted, 'truncated': truncated,
            'targets': len(targets), 'class_and_location_matches': len(classified), 'localization_matches': len(localized),
            'inspected_negative_proposals': len(false_indices), 'negative_prediction_indices': false_indices,
            'per_class': [{'class_id': cls, 'targets': sum(t['class_id']==cls for t in targets),
                'prediction_count': sum(p['class_id']==cls for p in converted),
                'matched': sum(targets[i]['class_id']==cls for i in classified)} for cls in (58,68,71)],
            'walls': [w.model_dump(mode='json') for w in walls.walls.items],
            'precision': None, 'independent_accuracy': None})
        view.close()
    image.close()
    report = {'schema': 'power-quality-same-source-development-probe-v1', 'source_sha256': digest(path),
        'box_fusion':box_fusion,
        'inspection_sha256': digest(inspection), 'checkpoint_sha256': digest(checkpoint),
        'dataset_manifest_sha256': digest(parent/'manifest.json'), 'threshold': .5,
        'frozen_parent_manifest_sha256': evidence['parent_manifest_sha256'],
        'original_pdf_sha256': source['source_sha256'],
        'source_authorization_sha256': source['authorization_sha256'],
        'matching': 'one-to-one class-aware IoU >= .50 in source coordinates', 'human_review_claim': False,
        'scope': 'Fixed full supplied power panel at native and upload-like scales; partial assistant inspection, development source.',
        'wall_detector_sha256': digest(Path(runtime.REPOSITORY_ROOT)/'backend/app/ai/wall_detection/detector.py'),
        'precision': None, 'independent_accuracy': None, 'outcomes': outcomes}
    (output/'report.json').write_text(json.dumps(report, indent=2))
    return [{k:r[k] for k in ('scale','targets','class_and_location_matches','localization_matches',
                             'inspected_negative_proposals','per_class')} for r in outcomes]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','prepared','inspection','checkpoint','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--frozen-parent', type=Path)
    parser.add_argument('--box-fusion', action='store_true')
    args = parser.parse_args()
    import torch
    torch.set_num_threads(4)
    print(json.dumps(probe(args.parent,args.prepared,args.inspection,args.checkpoint,args.output,args.frozen_parent,
                           box_fusion=args.box_fusion)))
