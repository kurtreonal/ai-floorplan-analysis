"""Replay the existing classes plus synthetic targets from authorized PDF legends.

Targets are known composite placements, not pseudo-labels or human-reviewed
layout boxes. The original PDF and every parent numeric class remain intact.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['YOLO_OFFLINE'] = 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extend_head(model, additions):
    """Append logits only; keep every existing class and localization parameter."""
    import torch
    old_names = dict(model.names)
    if set(old_names) != set(range(len(old_names))) or not additions:
        raise ValueError('Expected contiguous parent class identities')
    head = model.model[-1]
    if type(head).__name__ != 'Detect' or getattr(head, 'end2end', False):
        raise ValueError('Unsupported detection head; no architecture substitution')
    old_count, new_count = len(old_names), len(old_names) + len(additions)
    for branch in head.cv3:
        old = branch[-1]
        if not isinstance(old, torch.nn.Conv2d) or old.out_channels != old_count or old.groups != 1:
            raise ValueError('Unsupported classifier branch')
        replacement = torch.nn.Conv2d(old.in_channels, new_count, old.kernel_size,
            stride=old.stride, padding=old.padding, bias=True, device=old.weight.device,
            dtype=old.weight.dtype)
        with torch.no_grad():
            replacement.weight[:old_count].copy_(old.weight)
            replacement.bias[:old_count].copy_(old.bias)
            for offset, addition in enumerate(additions):
                seed = addition['seed_parent_class_id']
                if type(seed) is not int or seed not in old_names:
                    raise ValueError('Invalid transfer-learning seed')
                replacement.weight[old_count + offset].copy_(old.weight[seed])
                replacement.bias[old_count + offset].copy_(old.bias[seed] - 2)
        branch[-1] = replacement
    head.nc, head.no = new_count, new_count + head.reg_max * 4
    model.yaml['nc'] = new_count
    model.names = {**old_names, **{old_count + i: row['label'] for i, row in enumerate(additions)}}
    return model


def synthetic_tile(glyph, index, randomizer):
    """Known location, isotropic size and quarter-turn augmentation; no flips."""
    pixels = np.asarray(glyph.convert('L'))
    ys, xs = np.where(pixels < 220)
    if not len(xs):
        raise ValueError('Empty authored glyph')
    tight = glyph.crop((max(0, xs.min()-2), max(0, ys.min()-2),
                        min(glyph.width, xs.max()+3), min(glyph.height, ys.max()+3)))
    scale = (.65, .85, 1., 1.25)[index % 4]
    size = tuple(max(2, round(v*scale)) for v in tight.size)
    symbol = tight.resize(size, Image.Resampling.LANCZOS)
    if (index // 4) % 4:
        symbol = symbol.rotate(90 * ((index // 4) % 4), expand=True)
    if max(symbol.size) > 190:
        raise ValueError('Glyph exceeds bounded training tile')
    image = Image.new('RGB', (256, 256), (248, 248, 248) if index % 3 == 0 else 'white')
    pen = ImageDraw.Draw(image)
    x, y = randomizer.randint(20, 236-symbol.width), randomizer.randint(20, 236-symbol.height)
    # Construction-time context is not a real-world negative-region review.
    if index % 2:
        pen.line((10, y+symbol.height//2, 246, y+symbol.height//2), fill='black', width=2)
    if index % 3:
        pen.line((x+symbol.width//2, 10, x+symbol.width//2, 246), fill='black', width=2)
    image.paste(symbol, (x, y))
    box = [x, y, x+symbol.width, y+symbol.height]
    symbol.close()
    tight.close()
    return image, box


def build(parent, prepared, specification, checkpoint, output, *, examples=64):
    parent, prepared, output = Path(parent), Path(prepared), Path(output)
    if output.exists():
        raise FileExistsError('Dataset/head revisions are immutable')
    if not 16 <= examples <= 64:
        raise ValueError('Synthetic-example bound exceeded')
    data = json.loads((parent/'manifest.json').read_text())
    source = json.loads((prepared/'manifest.json').read_text())
    permission = json.loads((prepared/'source-authorization.json').read_text())
    spec = json.loads(Path(specification).read_text())
    if (source['source_sha256'] != digest(prepared/'original.pdf')
            or source['authorization_sha256'] != digest(prepared/'source-authorization.json')
            or permission['source_sha256'] != source['source_sha256']
            or permission['authorization_kind'] != 'user_attested_source_permission'
            or 'training' not in permission['allowed_purposes']
            or spec['source_manifest_sha256'] != digest(prepared/'manifest.json')):
        raise ValueError('Source authorization or preparation identity differs')
    if (not data['all_eligible_entries'] or len(data['classes']) != 56
            or data['required_loss'] != 'positive_boxes_and_explicit_reviewed_background'):
        raise ValueError('Expected pinned parent 56-class replay dataset')
    if spec['parent_dataset_sha256'] != digest(parent/'manifest.json') or spec['parent_checkpoint_sha256'] != digest(checkpoint):
        raise ValueError('Parent replay or weights differ')
    additions = spec['additions']
    if len(additions) != 4 or len({r['legend_entry'] for r in additions}) != 4:
        raise ValueError('Expected four distinct requested authored-legend classes')
    regions = {r['region_id']: r for r in source['regions']}
    glyphs = []
    for row in additions:
        region = regions[row['region_id']]
        if (region['kind'] != 'symbol_legend' or region['proposed_label'] != row['label']
                or row['legend_entry'] != f"pdf-{source['source_sha256'][:12]}:p{region['page_number']}:{region['region_id']}"
                or Path(region['filename']).name != region['filename']
                or digest(prepared/region['filename']) != region['crop_sha256']):
            raise ValueError('Authored legend identity or crop differs')
        with Image.open(prepared/region['filename']) as opened:
            if max(opened.size) > 512 or opened.width*opened.height > 262144:
                raise ValueError('Legend crop allocation exceeded')
            glyphs.append(opened.convert('RGB'))
    from ultralytics import YOLO
    loaded = YOLO(str(checkpoint))
    expected = {row['id']: row['label'] for row in data['classes']}
    # Existing public model names use ASCII; dataset wording remains unchanged.
    import unicodedata
    expected = {i: unicodedata.normalize('NFKD', n).encode('ascii','ignore').decode() for i,n in expected.items()}
    if loaded.names != expected:
        raise ValueError('Parent checkpoint class ordering differs')
    extend_head(loaded.model, additions)
    loaded.ckpt['ema'] = None  # Never reload the stale 56-class EMA over the expanded model.
    loaded.ckpt['optimizer'] = None
    output.mkdir(parents=True)
    shutil.copytree(parent/'images', output/'images')
    shutil.copytree(parent/'labels', output/'labels')
    loaded.save(output/'initialized-head.pt')
    result = deepcopy(data)
    result.update({'parent_dataset_sha256': digest(parent/'manifest.json'),
        'parent_checkpoint_sha256': digest(checkpoint), 'base_model_sha256': digest(output/'initialized-head.pt'),
        'authored_source_manifest_sha256': digest(prepared/'manifest.json'),
        'authored_source_sha256': source['source_sha256'], 'source_approval_kind': permission['authorization_kind'],
        'class_scope': 'parent56_plus_four_authored_lamp_and_outlet_definitions',
        'authored_legend_synthetic_images': [], 'new_real_page_reviewed_targets': 0,
        'new_real_world_independent_examples': 0})
    randomizer = random.Random(20261004)
    for offset, (addition, glyph) in enumerate(zip(additions, glyphs)):
        class_id = 56 + offset
        result['classes'].append({'id': class_id, 'label': addition['label'],
            'legend_entry': addition['legend_entry'], 'samples': 1,
            'source_reference_examples': 1, 'synthetic_examples': examples,
            'real_page_reviewed_targets': 0})
        for index in range(examples):
            image, box = synthetic_tile(glyph, index, randomizer)
            stem = f'authored-legend-{class_id}-{index:03d}'
            image_path, label_path = output/'images/train'/f'{stem}.png', output/'labels/train'/f'{stem}.txt'
            image.save(image_path)
            image.close()
            x1,y1,x2,y2 = box
            label_path.write_text(f'{class_id} {(x1+x2)/512:.8f} {(y1+y2)/512:.8f} {(x2-x1)/256:.8f} {(y2-y1)/256:.8f}\n')
            result['authored_legend_synthetic_images'].append({'image_id': stem, 'class_id': class_id,
                'legend_entry': addition['legend_entry'], 'box': box, 'image_sha256': digest(image_path),
                'label_sha256': digest(label_path), 'label_origin': 'known_synthetic_composite_geometry',
                'human_review_claim': False, 'source_reference_examples': 1,
                'source_sha256': source['source_sha256'], 'split': 'train'})
        glyph.close()
    result['warnings'].append('Additional legend classes use synthetic reference-derived targets, not reviewed real-layout boxes or independent evaluation.')
    (output/'manifest.json').write_text(json.dumps(result, indent=2))
    with (output/'data.yaml').open('x', encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in result['classes']:
            label = unicodedata.normalize('NFKD', row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    shutil.copy2(specification, output/'source-extension-specification.json')
    return {'classes': len(result['classes']), 'synthetic_targets': len(result['authored_legend_synthetic_images']),
            'new_real_page_reviewed_targets': 0, 'manifest_sha256': digest(output/'manifest.json')}


def build_learning_check(dataset, checkpoint, output):
    """Eight readable lamp examples; full numeric head, diagnostic-only scope."""
    dataset, checkpoint, output = Path(dataset), Path(checkpoint), Path(output)
    if output.exists():
        raise FileExistsError('Learning check revisions are immutable')
    parent = json.loads((dataset/'manifest.json').read_text())
    if parent.get('class_scope') != 'parent56_plus_four_authored_lamp_and_outlet_definitions':
        raise ValueError('Expected authorized authored-legend extension')
    # Native horizontal, 1.0-scale glyphs: the numeral must remain clearly readable.
    chosen = [row for row in parent['authored_legend_synthetic_images']
              if row['class_id'] in (56,57) and int(row['image_id'].rsplit('-',1)[1]) % 16 == 2]
    if len(chosen) != 8:
        raise ValueError('Expected four readable repeats for each lamp subtype')
    for row in chosen:
        name = row['image_id']
        if (Path(name).name != name or row.get('human_review_claim') is not False
                or digest(dataset/'images/train'/f'{name}.png') != row['image_sha256']
                or digest(dataset/'labels/train'/f'{name}.txt') != row['label_sha256']):
            raise ValueError('Synthetic learning-check source differs')
    output.mkdir(parents=True)
    (output/'images/train').mkdir(parents=True)
    (output/'labels/train').mkdir(parents=True)
    for row in chosen:
        name = row['image_id']
        shutil.copy2(dataset/'images/train'/f'{name}.png',output/'images/train'/f'{name}.png')
        shutil.copy2(dataset/'labels/train'/f'{name}.txt',output/'labels/train'/f'{name}.txt')
    data = deepcopy(parent)
    data.update({'diagnostic_only': True, 'all_eligible_entries': False,
        'required_loss':'synthetic_complete_known_composite_only',
        'parent_dataset_sha256':digest(dataset/'manifest.json'), 'base_model_sha256':digest(checkpoint),
        'authored_legend_synthetic_images':chosen, 'reviewed_targets':[], 'images':[],
        'reviewed_background_images':[], 'scope':'eight-example lamp-numeral memorization; never deploy this checkpoint'})
    for row in data['classes']:
        row['samples'] = sum(item['class_id'] == row['id'] for item in chosen)
        if row['id'] >= 56:
            row['synthetic_examples'] = row['samples']
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    import unicodedata
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            label = unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    return {'diagnostic_only':True,'training_images':len(chosen),'classes_in_numeric_head':len(data['classes'])}


def revise_synthetic_supervision(dataset, checkpoint, output):
    """Version the full replay without rewriting any original target or source."""
    dataset, checkpoint, output = Path(dataset), Path(checkpoint), Path(output)
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    data=json.loads((dataset/'manifest.json').read_text())
    if (data.get('diagnostic_only') or len(data['classes']) != 60
            or not data.get('all_eligible_entries')
            or data.get('class_scope') != 'parent56_plus_four_authored_lamp_and_outlet_definitions'):
        raise ValueError('Expected complete authorized extension replay')
    for row in data['authored_legend_synthetic_images']:
        name=row['image_id']
        if (Path(name).name != name or row.get('human_review_claim') is not False
                or row.get('label_origin') != 'known_synthetic_composite_geometry'
                or digest(dataset/'images/train'/f'{name}.png') != row['image_sha256']
                or digest(dataset/'labels/train'/f'{name}.txt') != row['label_sha256']):
            raise ValueError('Construction-known synthetic source differs')
    output.mkdir(parents=True)
    shutil.copytree(dataset/'images',output/'images')
    shutil.copytree(dataset/'labels',output/'labels')
    shutil.copy2(dataset/'source-extension-specification.json',output/'source-extension-specification.json')
    data.update({'supervision_parent_manifest_sha256':digest(dataset/'manifest.json'),
        'base_model_sha256':digest(checkpoint),'synthetic_complete_background':True})
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    import unicodedata
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            label=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    return {'classes':60,'synthetic_targets':len(data['authored_legend_synthetic_images']),
            'original_reviewed_targets':len(data['reviewed_targets']),
            'manifest_sha256':digest(output/'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','prepared','specification','checkpoint','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--examples', type=int, default=64)
    args = parser.parse_args()
    print(json.dumps(build(args.parent,args.prepared,args.specification,args.checkpoint,args.output, examples=args.examples)))
