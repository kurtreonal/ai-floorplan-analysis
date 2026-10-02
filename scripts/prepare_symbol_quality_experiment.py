"""Versioned replay of all existing classes plus recovered placements and reviewed negatives.

Negative regions require explicit local inspection records; never mine all unlabeled
pixels as negatives. This development tool does not approve or activate a model.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def recovery_window(width, height, box):
    """Match the shared inference lattice, retaining unclipped seam targets."""
    x1, y1, x2, y2 = box
    available = [(x, y) for x, y in tile_positions(width, height, dual_phase=True)
                 if x <= x1 < x2 <= x+256 and y <= y1 < y2 <= y+256]
    if available:
        x, y = max(available, key=lambda p: min(x1-p[0], y1-p[1], p[0]+256-x2, p[1]+256-y2))
        return x, y, 'native_inference_window'
    return (max(0, min(max(0, width-256), round((x1+x2)/2-128))),
            max(0, min(max(0, height-256), round((y1+y2)/2-128))),
            'centered_fallback_no_full_native_window')


def build(base, recovered_path, review_path, source_root, checkpoint, output):
    if output.exists():
        raise FileExistsError('Experiment versions are immutable')
    data = json.loads((base / 'manifest.json').read_text())
    recovered = json.loads(recovered_path.read_text())
    review = json.loads(review_path.read_text())
    if data.get('required_loss') != 'positive_and_reviewed_box_only' or not data.get('all_eligible_entries'):
        raise ValueError('Expected existing all-class positive-box training manifest')
    if review.get('reviewer') != 'assistant_visual_inspection' or review.get('scope') != 'local_development_only':
        raise ValueError('Explicit inspection provenance required')
    if len(review.get('sheets', [])) > 32 or sum(len(s.get('regions', [])) for s in review['sheets']) > 128:
        raise ValueError('Negative review bounds exceeded')
    by_key = {r['legend_entry']: r['id'] for r in data['classes']}
    existing = {r['record_id'] for r in data['reviewed_targets']}
    new = [r for r in recovered['records'] if r['id'] not in existing and r['legend_entry'] in by_key]
    deferred = [r for r in recovered['records'] if r['legend_entry'] not in by_key]
    protected = {'sheet-51', 'sheet-52'}
    train_sources = {(r['sheet_id'], r['source_sha256']) for r in recovered['records']
                     if r.get('split') == 'train' and 1 <= int(r.get('group', 0)) <= 22}
    images = {}
    def source(sheet_id, expected):
        if sheet_id in protected or Path(sheet_id).name != sheet_id:
            raise ValueError('Excluded source')
        path = source_root / f'{sheet_id}.jpg'
        if path.stat().st_size > 25_000_000 or digest(path) != expected:
            raise ValueError('Source image integrity mismatch')
        if sheet_id not in images:
            with Image.open(path) as im:
                if im.width * im.height > 60_000_000 or max(im.size) > 10000:
                    raise ValueError('Image bound exceeded')
                if sum(v.width*v.height for v in images.values()) + im.width*im.height > 128_000_000:
                    raise ValueError('Source cache memory bound exceeded')
                images[sheet_id] = im.convert('RGB')
        return images[sheet_id]

    # Validate all new sources before producing a version.
    for row in new:
        if row.get('split') != 'train' or not 1 <= int(row['group']) <= 22:
            raise ValueError('Protected or unauthorized placement')
        source(row['sheet_id'], row['source_sha256'])
    for sheet in review['sheets']:
        if (sheet['sheet_id'], sheet['source_sha256']) not in train_sources:
            raise ValueError('Negative source is outside the authorized development train partition')
        source(sheet['sheet_id'], sheet['source_sha256'])
    shutil.copytree(base / 'images', output / 'images')
    shutil.copytree(base / 'labels', output / 'labels')
    result = deepcopy(data)
    result['base_model_sha256'] = digest(checkpoint)
    result['required_loss'] = 'positive_boxes_and_explicit_reviewed_background'
    result['parent_dataset_sha256'] = digest(base / 'manifest.json')
    result['recovery_manifest_sha256'] = digest(recovered_path)
    result['negative_review_sha256'] = digest(review_path)
    result['deferred_new_class_records'] = deferred
    result['class_scope'] = 'frozen_parent_class_head; additional recovered identities explicitly deferred'
    result['recovered_window_policy'] = 'shared dual-phase inference lattice; unclipped fallback at seams'
    # All 56 numeric identities stay fixed. New distinct identities are reported,
    # never coerced into a vaguely similar class to fit an existing model head.
    for row in new:
        image = images[row['sheet_id']]
        x1, y1, x2, y2 = row['bbox']
        if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height) or max(x2-x1, y2-y1) > 256:
            raise ValueError('Recovered box outside bounds')
        x, y, alignment = recovery_window(image.width, image.height, row['bbox'])
        target = {'record_id': row['id'], 'sheet_id': row['sheet_id'], 'source_sha256': row['source_sha256'],
                  'legend_entry': row['legend_entry'], 'class_id': by_key[row['legend_entry']], 'source_box': row['bbox']}
        result['reviewed_targets'].append(target)
        name = f"recovered-{row['id']}"
        image.crop((x, y, x+256, y+256)).save(output / 'images/train' / f'{name}.png')
        neighbors = [r for r in recovered['records'] if r['source_sha256'] == row['source_sha256']
                     and r['legend_entry'] in by_key and r['bbox'][0] >= x and r['bbox'][1] >= y
                     and r['bbox'][2] <= x+256 and r['bbox'][3] <= y+256]
        lines = []
        for neighbor in neighbors:
            a,b,c,d = neighbor['bbox']
            lines.append(f"{by_key[neighbor['legend_entry']]} {(a+c-2*x)/512} {(b+d-2*y)/512} {(c-a)/256} {(d-b)/256}")
        (output / 'labels/train' / f'{name}.txt').write_text('\n'.join(lines)+'\n')
        result['images'].append({**target, 'record_id': name, 'source_crop': [x,y,x+256,y+256],
                                 'recovered_placement': True, 'grid_alignment': alignment})
    negatives = []
    contact = []
    for sheet in review['sheets']:
        image = images[sheet['sheet_id']]
        for index, bounds in enumerate(sheet['regions']):
            if len(bounds) != 4 or not (0 <= bounds[0] < bounds[2] <= 1 and 0 <= bounds[1] < bounds[3] <= 1):
                raise ValueError('Invalid reviewed region')
            box = [round(bounds[i] * (image.width if i%2 == 0 else image.height)) for i in range(4)]
            # No negative region may touch a reviewed electrical positive, including
            # a deferred new class. Unresolved-region inspection remains explicit.
            for target in recovered['records']:
                if target['source_sha256'] != sheet['source_sha256']:
                    continue
                a,b,c,d = target['bbox']
                if max(a,box[0]) < min(c,box[2]) and max(b,box[1]) < min(d,box[3]):
                    raise ValueError('Reviewed negative overlaps an electrical target')
            if min(box[2]-box[0],box[3]-box[1]) <= 0 or max(box[2]-box[0],box[3]-box[1]) > 256:
                raise ValueError('Negative crop exceeds native detail window')
            patch = image.crop(box)
            contact.append((sheet['sheet_id'], index, patch))
            for variant, factor in enumerate((0.85, 1., 1.1, 1.)):
                resized = patch.resize((round(patch.width*factor), round(patch.height*factor)))
                if max(resized.size) > 256: raise ValueError('Augmented crop clipped')
                canvas = Image.new('RGB', (256,256), 'white')
                offset = ((256-resized.width)//2, (256-resized.height)//2)
                if variant == 3: offset = (0, 0)
                canvas.paste(resized, offset)
                name = f"reviewed-negative-{sheet['sheet_id']}-{index:03d}-{variant}"
                path = output / 'images/train' / f'{name}.png'
                canvas.save(path)
                (output / 'labels/train' / f'{name}.txt').write_text('')
                negatives.append({'image_id': name, 'sha256': digest(path), 'sheet_id': sheet['sheet_id'],
                                  'source_sha256': sheet['source_sha256'], 'source_box': box,
                                  'reviewer': review['reviewer'], 'meaning': sheet['meaning'],
                                  'synthetic_variant': variant, 'scale': factor})
    result['reviewed_background_images'] = negatives
    counts = Counter(r['class_id'] for r in result['reviewed_targets'])
    for cls in result['classes']: cls['samples'] = counts[cls['id']]
    (output / 'manifest.json').write_text(json.dumps(result, indent=2))
    yaml = (base / 'data.yaml').read_text()
    lines = [f'path: {output.resolve().as_posix()}' if line.startswith('path:') else line for line in yaml.splitlines()]
    (output / 'data.yaml').write_text('\n'.join(lines)+'\n')
    board = Image.new('RGB',(800,180*((len(contact)+4)//5)), 'white')
    draw = ImageDraw.Draw(board)
    for i,(sheet_id,index,patch) in enumerate(contact):
        thumbnail = patch.copy(); thumbnail.thumbnail((150,145))
        x,y = (i%5)*160, (i//5)*180
        board.paste(thumbnail,(x,y+25)); draw.text((x,y),f'{sheet_id} / {index}',fill='black')
    board.save(output / 'reviewed-negatives-contact.png')
    return {'classes':len(by_key), 'recovered_placements':len(new), 'deferred_new_class_records':len(deferred),
            'reviewed_negative_regions':len(contact), 'synthetic_negative_images':len(negatives),
            'manifest_sha256':digest(output/'manifest.json')}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','recovered','review','source-root','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.base,args.recovered,args.review,args.source_root,args.checkpoint,args.output)))
