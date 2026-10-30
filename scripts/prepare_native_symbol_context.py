"""Prepare bounded native-context diagnostics, never a complete-page dataset.

Only existing source-bound positive labels and explicitly inspected negative
rectangles supervise pixels. Everything else is ignored, including clipped
positive labels. This does not train, activate, or approve a checkpoint.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def overlap(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def valid_box(box, size):
    return (isinstance(box, list) and len(box) == 4
            and all(type(v) in (int, float) and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])


def context_rows(targets, negatives, size, *, negative_context_only=False):
    """Use the serving lattice, with at most two best-contained views per label."""
    if any(not valid_box(t['source_box'], size) for t in targets):
        raise ValueError('Invalid positive source box')
    if any(not valid_box(n['box'], size) for n in negatives):
        raise ValueError('Invalid negative source box')
    for negative in negatives:
        for target in targets:
            a, b, c, d = overlap(negative['box'], target['source_box'])
            if c > a and d > b:
                raise ValueError('Inspected background overlaps an existing positive')
    positions = tile_positions(*size, dual_phase=True)
    if len(positions) > 500:
        raise ValueError('Serving tile limit exceeded')
    controls = set()
    for target in targets:
        a, b, c, d = target['source_box']
        contained = [(x, y) for x, y in positions if x <= a < c <= x+256 and y <= b < d <= y+256]
        contained.sort(key=lambda p: (-min(a-p[0], b-p[1], p[0]+256-c, p[1]+256-d), p))
        if not negative_context_only:
            controls.update(contained[:2])
    rows = []
    for x, y in positions:
        masks = []
        for negative in negatives:
            a, b, c, d = overlap(negative['box'], [x, y, x+256, y+256])
            if c-a >= 8 and d-b >= 8:
                masks.append({'inspection_id': negative['id'],
                              'box': [(a-x)*1.25, (b-y)*1.25, (c-x)*1.25, (d-y)*1.25]})
        if not masks and (x, y) not in controls:
            continue
        positive = [t for t in targets if x <= t['source_box'][0] < t['source_box'][2] <= x+256
                    and y <= t['source_box'][1] < t['source_box'][3] <= y+256]
        rows.append({'image_id': f'native-{x}-{y}', 'source_origin': [x, y],
                     'reviewed_background': False, 'context_only': True,
                     'negative_regions_training_pixels': masks,
                     'supervised_records': [t['record_id'] for t in positive],
                     'labels': [[t['class_id'], ((t['source_box'][0]+t['source_box'][2])/2-x)/256,
                                 ((t['source_box'][1]+t['source_box'][3])/2-y)/256,
                                 (t['source_box'][2]-t['source_box'][0])/256,
                                 (t['source_box'][3]-t['source_box'][1])/256] for t in positive]})
    if not rows or len(rows) > 64:
        raise ValueError('Native diagnostic requires 1–64 windows')
    return rows


def prepare(source, dataset, inspection, output, *, negative_context_only=False):
    if output.exists():
        raise FileExistsError('Diagnostic revisions are immutable')
    source_hash = digest(source)
    data = json.loads(dataset.read_text(encoding='utf-8'))
    evidence = json.loads(inspection.read_text(encoding='utf-8'))
    if (evidence.get('schema') != 'ved-native-symbol-inspection-v1'
            or evidence.get('source_sha256') != source_hash
            or evidence.get('dataset_sha256') != digest(dataset)
            or evidence.get('annotation_origin') != 'assistant_visual_under_user_development_authorization'
            or evidence.get('human_review_claim') is not False
            or evidence.get('production_approval') is not False
            or evidence.get('missing_annotation_policy') != 'ignore_unreviewed_not_empty_background'):
        raise ValueError('Exact source-bound development inspection required')
    negatives = evidence.get('background_regions', [])
    if (not 1 <= len(negatives) <= 32 or len({n['id'] for n in negatives}) != len(negatives)
            or any(not n.get('meaning') for n in negatives)):
        raise ValueError('Bounded unique explained negatives required')
    targets = [t for t in data['reviewed_targets'] if t['source_sha256'] == source_hash]
    definitions = {c['id']: c for c in data['classes']}
    if (not targets or len({t['record_id'] for t in targets}) != len(targets)
            or any(t['class_id'] not in definitions or
                   definitions[t['class_id']]['legend_entry'] != t['legend_entry'] for t in targets)):
        raise ValueError('Existing unique source labels and exact legend identities required')
    with Image.open(source) as original:
        if max(original.size) > 10000 or original.width * original.height > 60_000_000:
            raise ValueError('Source dimension bounds exceeded')
        rows = context_rows(targets, negatives, original.size,
                            negative_context_only=negative_context_only)
        output.mkdir(parents=True)
        with original.convert('RGB') as image:
            for row in rows:
                x, y = row['source_origin']
                path = output / (row['image_id'] + '.png')
                with image.crop((x, y, x+256, y+256)) as crop:
                    crop.save(path)
                row['image_sha256'] = digest(path)
            with image.copy() as overlay:
                pen = ImageDraw.Draw(overlay)
                for target in targets:
                    pen.rectangle(target['source_box'], outline='green', width=3)
                for region in negatives:
                    pen.rectangle(region['box'], outline='orange', width=3)
                    pen.text(region['box'][:2], region['id'], fill='red')
                overlay.save(output / 'supervision-overlay.png')
    if digest(source) != source_hash:
        raise ValueError('Original source changed')
    manifest = {'schema': 'ved-native-symbol-context-v1', 'diagnostic_only': True,
                'source_sha256': source_hash, 'dataset_sha256': digest(dataset),
                'inspection_sha256': digest(inspection), 'checkpoint_changed': False,
                'human_review_claim': False, 'production_approval': False,
                'independent_evaluation': False, 'precision': None,
                'missing_annotation_policy': 'ignore_unreviewed_not_empty_background',
                'native_window_size': 256, 'training_size': 320,
                'negative_context_only': negative_context_only,
                'included_positive_record_ids': sorted({record for row in rows for record in row['supervised_records']}),
                'positive_records': targets, 'background_regions': negatives,
                'images': rows, 'classes': data['classes']}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'windows': len(rows), 'positive_records': len(targets), 'negative_regions': len(negatives),
            'all_model_classes_preserved': len(data['classes']), 'checkpoint_changed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'dataset', 'inspection', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--negative-context-only', action='store_true',
                        help='Keep windows intersecting inspected negatives; preserve any contained positives')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.dataset, args.inspection, args.output,
                             negative_context_only=args.negative_context_only)))
