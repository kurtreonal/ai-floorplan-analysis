"""Replay inspected power symbols and explicit non-device regions, locally only.

Preserve the full model head, prior annotations, ignored unknown areas and source
identities. Assistant proposals under delegated development authorization are
not human review, independent evaluation, or production approval.
"""
import argparse
from copy import deepcopy
from contextlib import ExitStack, closing
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
import yaml

from prepare_authored_legend_extension import digest
from prepare_authorized_pdf_detection import validate_training_sources, validate_authorization
from prepare_real_lamp_replay import transformed_labels

ORIGIN = 'assistant_visual_under_user_development_authorization'


def validate_power_source(prepared, evidence):
    prepared = Path(prepared)
    source = json.loads((prepared / 'manifest.json').read_text())
    region = next(r for r in source['regions'] if r['region_id'] == evidence['layout_region_id'])
    if Path(region['filename']).name != region['filename']:
        raise ValueError('Prepared region must be a local source artifact')
    path = prepared / region['filename']
    permission_path = prepared / 'source-authorization.json'
    permission = json.loads(permission_path.read_text())
    if (digest(prepared / 'manifest.json') != evidence['prepared_manifest_sha256']
            or digest(prepared / 'original.pdf') != source['source_sha256']
            or digest(permission_path) != source['authorization_sha256']
            or permission.get('source_sha256') != source['source_sha256']
            or 'training' not in permission.get('allowed_purposes', [])
            or digest(path) != region['crop_sha256']
            or digest(path) != evidence['source_image_sha256']):
        raise ValueError('Authorization or original source revision changed')
    return source, region, path


def checked_inspection(evidence, parent, source, region, size):
    width, height = size
    if (evidence.get('schema') != 'ved-delegated-power-quality-inspection-v1'
            or evidence.get('human_review_claim') is not False
            or evidence.get('production_approval') is not False
            or evidence.get('annotation_origin') != ORIGIN
            or evidence.get('missing_annotation_policy') != 'ignore_unreviewed_not_empty_background'
            or not evidence.get('user_statement')
            or evidence.get('source_sha256') != source['source_sha256']
            or evidence.get('project_group_id') != source['project_group_id']
            or evidence.get('layout_region_id') != region['region_id']
            or evidence.get('source_image_sha256') != region['crop_sha256']
            or evidence.get('page_number') != region['page_number']
            or len(parent['classes']) != 80 or parent.get('diagnostic_only')
            or any(type(row.get('id')) is not int or row['id'] != index for index, row in enumerate(parent['classes']))
            or parent.get('all_eligible_entries') is not True
            or not 0 <= len(evidence.get('targets', [])) <= 50
            or not 1 <= len(evidence.get('background_regions', [])) <= 64):
        raise ValueError('Exact source-bound delegated inspection and complete head required')
    identities = set()

    def check_box(row):
        name, box = row['id'], row['box']
        if (not isinstance(name, str) or not name.replace('-', '').isalnum() or name in identities
                or len(box) != 4 or any(type(v) is not int for v in box)
                or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
            raise ValueError('Invalid or duplicate inspection box')
        identities.add(name)
        return box

    targets = []
    prior_targets = [t for t in parent.get('power_source_targets', [])
                     if t.get('source_sha256') == region['crop_sha256']
                     and t.get('pdf_sha256') == source['source_sha256']]
    if not evidence['targets'] and not prior_targets:
        raise ValueError('Background-only revisions require prior source-bound positive review')
    regions = {r['region_id']: r for r in source['regions']}
    for row in evidence['targets']:
        box = check_box(row)
        class_id = row['class_id']
        definition = regions.get(row['legend_region_id'])
        if (type(class_id) is not int or not 0 <= class_id < 80 or definition is None
                or definition.get('kind') != 'symbol_legend' or not row.get('meaning_evidence')
                or max(box[2] - box[0], box[3] - box[1]) > 190
                or definition['proposed_label'].casefold() != parent['classes'][class_id]['label'].casefold()):
            raise ValueError('Source legend does not establish the model class meaning')
        targets.append({'record_id': row['id'], 'source_box': box, 'class_id': class_id,
            'label': parent['classes'][class_id]['label'], 'legend_entry': parent['classes'][class_id]['legend_entry'],
            'source_legend_entry': f"pdf-{source['source_sha256'][:12]}:p{definition['page_number']}:{row['legend_region_id']}",
            'source_sha256': region['crop_sha256'], 'pdf_sha256': source['source_sha256'],
            'page_number': region['page_number'], 'project_group_id': source['project_group_id'],
            'split': 'train', 'annotation_origin': ORIGIN, 'human_review_claim': False,
            'meaning_evidence': row['meaning_evidence']})
    backgrounds = []
    for row in evidence['background_regions']:
        box = check_box(row)
        if not row.get('reason') or max(box[2] - box[0], box[3] - box[1]) > 256:
            raise ValueError('Background region exceeds an inspected detail window')
        if any(max(box[0], t['source_box'][0]) < min(box[2], t['source_box'][2])
               and max(box[1], t['source_box'][1]) < min(box[3], t['source_box'][3])
               for t in (*targets, *prior_targets)):
            raise ValueError('A reviewed-positive region cannot become negative background')
        backgrounds.append(deepcopy(row))
    return targets, backgrounds


def power_views(image, targets):
    # Include the actual small upload scale, not only centered native-size crops.
    if not targets:
        return
    for scale in (.375, .5, .75, 1):
        view = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        try:
            if min(view.size) < 256:
                raise ValueError('Source is too small for the frozen detail-window scales')
            for target in targets:
                a, b, c, d = target['source_box']
                for dx in (-64, 0, 64):
                    for dy in (-64, 0, 64):
                        left = max(0, min(view.width - 256, round((a + c) / 2 * scale - 128 + dx)))
                        top = max(0, min(view.height - 256, round((b + d) / 2 * scale - 128 + dy)))
                        lines, ids = transformed_labels(targets, scale, left, top)
                        if target['record_id'] in ids:
                            yield view.crop((left, top, left + 256, top + 256)), lines, ids, scale, [left, top], target
        finally:
            view.close()


def prepare(parent, prepared, inspection, checkpoint, output):
    with ExitStack() as resources:
        return _prepare(parent, prepared, inspection, checkpoint, output, resources)


def _prepare(parent, prepared, inspection, checkpoint, output, resources):
    parent, prepared, inspection, checkpoint, output = map(Path, (parent, prepared, inspection, checkpoint, output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    if inspection.stat().st_size > 1_048_576:
        raise ValueError('Inspection exceeds bound')
    data = json.loads((parent / 'manifest.json').read_text())
    validate_training_sources(parent, data)
    evidence = json.loads(inspection.read_text())
    source, region, path = validate_power_source(prepared, evidence)
    if digest(parent / 'manifest.json') != evidence['parent_manifest_sha256']:
        raise ValueError('Parent revision changed')
    with Image.open(path) as opened:
        if opened.width * opened.height > 60_000_000:
            raise ValueError('Source exceeds allocation bound')
        image = resources.enter_context(closing(opened.convert('RGB')))
    targets, backgrounds = checked_inspection(evidence, data, source, region, image.size)
    phase_offsets=evidence.get('background_phase_offsets',[0])
    if (not isinstance(phase_offsets,list) or not 1<=len(phase_offsets)<=3
            or any(type(v) is not int or not -64<=v<=64 for v in phase_offsets)
            or len(set(phase_offsets))!=len(phase_offsets)):
        raise ValueError('Inspected-background phase offsets exceed bounds')
    if {t['record_id'] for t in targets} & {t['record_id'] for t in data.get('power_source_targets', [])}:
        raise ValueError('Do not overwrite annotation history')
    if {r['id'] for r in backgrounds} & {r['id'] for r in data.get('power_negative_regions', [])}:
        raise ValueError('Do not overwrite negative review history')
    revision_hash = digest(inspection)
    revision_key = revision_hash[:12]
    shutil.copytree(parent, output, ignore=shutil.ignore_patterns('*.cache'))
    lineage = output / 'lineage'
    lineage.mkdir(exist_ok=True)
    parent_hash = evidence['parent_manifest_sha256']
    parent_archive = lineage / f'{parent_hash}.json'
    if not parent_archive.exists():
        shutil.copy2(parent / 'manifest.json', parent_archive)
    if digest(parent_archive) != parent_hash:
        raise ValueError('Archived parent manifest identity changed')
    if not (output / 'power-inspection.json').exists():
        shutil.copy2(inspection, output / 'power-inspection.json')
    archive = output / 'power-inspections'
    archive.mkdir(exist_ok=True)
    inspection_name = f'power-inspections/{revision_hash}.json'
    if (output / inspection_name).exists():
        raise ValueError('Inspection revision already exists')
    shutil.copy2(inspection, output / inspection_name)
    auth = {**evidence, 'schema': 'ved-user-authorized-development-label-preparation-v1',
            'local_development_training': True, 'delegated_assistant_annotation': True}
    auth_name = f'power-development-authorization-{revision_key}.json'
    (output / auth_name).write_text(json.dumps(auth, indent=2))
    validate_authorization(output / auth_name, source['source_sha256'], digest(prepared / 'manifest.json'))
    data['additional_training_authorizations'].append({'filename': auth_name, 'sha256': digest(output / auth_name),
        'source_sha256': source['source_sha256'], 'prepared_manifest_sha256': digest(prepared / 'manifest.json')})
    data['base_model_sha256'] = digest(checkpoint)
    data['parent_dataset_sha256'] = digest(parent / 'manifest.json')
    data.setdefault('power_source_targets', []).extend(targets)
    data.setdefault('power_negative_regions', []).extend(backgrounds)
    source_identity = {k: evidence[k] for k in ('source_sha256', 'source_image_sha256',
        'prepared_manifest_sha256', 'project_group_id', 'page_number', 'layout_region_id')}
    data.setdefault('power_source_identity', source_identity)
    revision = {'inspection_filename': inspection_name, 'inspection_sha256': revision_hash,
                'parent_manifest_sha256': evidence['parent_manifest_sha256'],
                'source_identity': source_identity, 'target_ids': [t['record_id'] for t in targets],
                'negative_ids': [r['id'] for r in backgrounds]}
    data.setdefault('power_replay_revisions', []).append(revision)
    generated = 0
    views = resources.enter_context(closing(power_views(image, targets)))
    for index, (tile, lines, ids, scale, origin, target) in enumerate(views):
        name = f'pdfdev-power-quality-{revision_key}-{index:04d}'
        ip, lp = output / 'images/train' / f'{name}.png', output / 'labels/train' / f'{name}.txt'
        with closing(tile):
            if ip.exists() or lp.exists():
                raise ValueError('Training identity already exists')
            tile.save(ip)
        lp.write_text('\n'.join(lines) + '\n')
        data['authorized_pdf_training_images'].append({'image_id': name, 'source_sha256': source['source_sha256'],
            'source_image_sha256': region['crop_sha256'], 'image_sha256': digest(ip), 'label_sha256': digest(lp),
            'tile_origin': origin, 'isotropic_view_scale': scale, 'primary_class_id': target['class_id'],
            'supervised_record_ids': ids, 'human_review_claim': False, 'annotation_origin': ORIGIN,
            'independent_example': False, 'split': 'train'})
        generated += 1
    # Only these visually inspected, wholly non-device patches supervise empty
    # anchors. No inferred outside-wall mask or whole-page negative assumption.
    contact = resources.enter_context(closing(Image.new('RGB', (4 * 256, math.ceil(len(backgrounds) / 4) * 280), 'white')))
    for index, region_row in enumerate(backgrounds):
        tile = resources.enter_context(closing(Image.new('RGB', (256, 256), 'white')))
        with closing(image.crop(region_row['box'])) as crop:
            tile.paste(crop, ((256 - crop.width) // 2, (256 - crop.height) // 2))
        x, y = (index % 4) * 256, (index // 4) * 280
        contact.paste(tile, (x, y)); ImageDraw.Draw(contact).text((x + 4, y + 259), region_row['id'], fill='black')
        for scale in (1, .75, .5):
            with closing(tile.resize((round(256 * scale), round(256 * scale)), Image.Resampling.LANCZOS)) as view:
                for phase_y in phase_offsets:
                    for phase_x in phase_offsets:
                        with closing(Image.new('RGB',(256,256),'white')) as negative:
                            # Only inspected pixels and known-white padding; no unknown drawing space.
                            negative.paste(view,((256-view.width)//2+phase_x,(256-view.height)//2+phase_y))
                            name=f"reviewed-negative-pdfdev-power-{revision_key}-{index:02d}-s{round(scale*100)}"
                            if phase_offsets!=[0]:name+=f'-phase{phase_x:+d}-{phase_y:+d}'
                            ip,lp=output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
                            if ip.exists() or lp.exists():raise ValueError('Negative identity already exists')
                            negative.save(ip);lp.write_text('')
                        row={'image_id':name,'sha256':digest(ip),'source_sha256':source['source_sha256'],
                            'source_image_sha256':evidence['source_image_sha256'],'box':region_row['box'],
                            'scale':scale,'reason':region_row['reason'],'annotation_origin':ORIGIN,
                            'human_review_claim':False,'independent_example':False,'split':'train'}
                        if phase_offsets!=[0]:row['dependent_phase_offset']=[phase_x,phase_y]
                        data['reviewed_background_images'].append(row)
                        data.setdefault('assistant_reviewed_background_regions',[]).append(row)
        tile.close()
    contact.save(output / 'negative-contact.png'); contact.close()
    pen = ImageDraw.Draw(image)
    for t in targets:
        pen.rectangle(t['source_box'], outline='green', width=2)
        pen.text(t['source_box'][:2], f"{t['class_id']} {t['record_id']}", fill='green')
    image.save(output / 'target-overlay.png'); image.close()
    sampling = {'scales': [.375, .5, .75, 1], 'phase_offsets': [-64, 0, 64],
        'dependent_positive_views': generated, 'negative_views': len(backgrounds) * 3 * len(phase_offsets)**2,
        'independent_examples': False, 'unknown_regions': 'ignored'}
    data.setdefault('power_sampling', sampling)
    revision['sampling'] = sampling
    if phase_offsets!=[0]:revision['sampling']['background_phase_offsets']=phase_offsets
    data['warnings'].append('Power quality replay: assistant-inspected same-project positives and explicit non-device patches; no independent precision, human review claim or production approval.')
    (output / 'manifest.json').write_text(json.dumps(data, indent=2))
    config = yaml.safe_load((parent / 'data.yaml').read_text()); config['path'] = output.resolve().as_posix()
    (output / 'data.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    validate_training_sources(output, data)
    return {'classes': 80, 'positive_targets': len(targets), 'inspected_negative_regions': len(backgrounds),
        'dependent_positive_views': generated, 'manifest_sha256': digest(output / 'manifest.json')}


def replay_negatives(parent, checkpoint, output, *, hard_mining=False):
    """Translate only wholly inspected negatives; no new real examples/review."""
    parent, checkpoint, output = map(Path, (parent, checkpoint, output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    data = json.loads((parent / 'manifest.json').read_text())
    validate_training_sources(parent, data)
    selected = [r for r in data.get('assistant_reviewed_background_regions', [])
                if r['image_id'].startswith('reviewed-negative-pdfdev-power-')]
    if (len(data.get('classes', [])) != 80 or data.get('all_eligible_entries') is not True
            or data.get('required_loss') != 'positive_boxes_and_explicit_reviewed_background'
            or data.get('power_negative_replay') or not 1 <= len(selected) <= 192
            or not data.get('power_source_targets')):
        raise ValueError('One bounded full-head power-negative replay required')
    parent_hash = digest(parent / 'manifest.json')
    shutil.copytree(parent, output, ignore=shutil.ignore_patterns('*.cache'))
    archive = output / 'lineage'
    archive.mkdir(exist_ok=True)
    shutil.copy2(parent / 'manifest.json', archive / f'{parent_hash}.json')
    offsets = [(x,y) for x in (-64,0,64) for y in (-64,0,64) if (x,y) != (0,0)]
    for index, original in enumerate(selected):
        with Image.open(parent / 'images/train' / f"{original['image_id']}.png") as opened:
            if opened.size != (256,256):
                raise ValueError('Reviewed-negative detail window changed')
            with closing(opened.convert('RGB')) as image:
                for phase, (dx,dy) in enumerate(offsets):
                    name = f'reviewed-negative-pdfdev-power-phase-{parent_hash[:12]}-{index:03d}-{phase}'
                    ip, lp = output / 'images/train' / f'{name}.png', output / 'labels/train' / f'{name}.txt'
                    if ip.exists() or lp.exists():
                        raise ValueError('Negative sampling identity already exists')
                    with closing(Image.new('RGB', (256,256), 'white')) as tile:
                        tile.paste(image, (dx,dy))
                        tile.save(ip)
                    lp.write_text('')
                    row = {**original, 'image_id': name, 'sha256': digest(ip),
                           'sampling_parent': original['image_id'], 'augmentation_offset': [dx,dy],
                           'independent_example': False, 'human_review_claim': False}
                    data['reviewed_background_images'].append(row)
                    data['assistant_reviewed_background_regions'].append(row)
    data['base_model_sha256'] = digest(checkpoint)
    data['parent_dataset_sha256'] = parent_hash
    data['power_negative_replay'] = {'parent_manifest_sha256': parent_hash,
        'original_inspected_negative_views': len(selected), 'translated_negative_views': len(selected)*8,
        'offsets': offsets, 'padding': 'construction-known white', 'unknown_regions': 'ignored',
        'independent_examples': False, 'human_review_claim': False}
    if hard_mining:
        data['reviewed_background_sampling'] = 'top_score_anchors'
        data['power_negative_replay']['hard_negative_anchor_budget'] = 32
    data['warnings'].append('Dependent phase-shift sampling of inspected power negatives only; no additional independent observations or human approval.')
    (output / 'manifest.json').write_text(json.dumps(data, indent=2))
    config = yaml.safe_load((parent / 'data.yaml').read_text())
    config['path'] = output.resolve().as_posix()
    (output / 'data.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    validate_training_sources(output, data)
    return data['power_negative_replay']


def restore_switch_replay(parent, checkpoint, output):
    """One exact positive-window replay; no new boxes, classes or background."""
    parent, checkpoint, output = map(Path, (parent, checkpoint, output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    data = json.loads((parent / 'manifest.json').read_text())
    validate_training_sources(parent, data)
    selected = [r for r in data.get('authorized_pdf_training_images', [])
                if r['image_id'].startswith('pdfdev-switch-')]
    targets = {r['record_id']: r for r in data.get('switch_source_targets', [])}
    if (len(data.get('classes', [])) != 80 or data.get('all_eligible_entries') is not True
            or data.get('diagnostic_only') or data.get('power_switch_retention_replay')
            or data.get('required_loss') != 'positive_boxes_and_explicit_reviewed_background'
            or not 1 <= len(selected) <= 800 or not targets
            or len({r['image_id'] for r in selected}) != len(selected)
            or len(targets) != len(data['switch_source_targets'])
            or len(selected) + len(data.get('restorative_replay_sampling', {}).get('replicas', [])) > 1600):
        raise ValueError('One bounded full-head switch retention replay required')
    for row in selected:
        cls = row.get('primary_class_id')
        if (cls not in (62, 63, 64) or row.get('independent_example') is not False
                or row.get('human_review_claim') is not False
                or not any(targets.get(record_id, {}).get('class_id') == cls
                           for record_id in row.get('supervised_record_ids', []))):
            raise ValueError('Existing switch source supervision required')
    parent_hash = digest(parent / 'manifest.json')
    shutil.copytree(parent, output, ignore=shutil.ignore_patterns('*.cache'))
    archive = output / 'lineage'
    archive.mkdir(exist_ok=True)
    shutil.copy2(parent / 'manifest.json', archive / f'{parent_hash}.json')
    replicas = []
    for index, row in enumerate(selected):
        name = f'restored-replay-power-switch-{parent_hash[:12]}-{index:04d}'
        replica = {'image_id': name, 'sampling_parent': row['image_id'],
                   'class_id': row['primary_class_id'], 'split': 'train', 'independent_example': False}
        for folder, suffix, key in (('images/train', 'png', 'image_sha256'),
                                   ('labels/train', 'txt', 'label_sha256')):
            source = parent / folder / f"{row['image_id']}.{suffix}"
            destination = output / folder / f'{name}.{suffix}'
            if destination.exists() or digest(source) != row[key]:
                raise ValueError('Retained source window changed')
            shutil.copy2(source, destination)
            replica[key] = digest(destination)
            if replica[key] != row[key]:
                raise ValueError('Retention copy differs from original')
        labels = {int(line.split()[0]) for line in (output / 'labels/train' / f'{name}.txt').read_text().splitlines()}
        if replica['class_id'] not in labels:
            raise ValueError('Retained switch class is not supervised')
        replicas.append(replica)
        # sampling_parent references the unchanged authorized source/box/legend record.
    data['power_switch_retention_replay'] = {'parent_manifest_sha256': parent_hash,
        'replicas': replicas, 'independent_examples_added': 0,
        'reason': 'Restore measured switch regression without relabeling or changing partial masks'}
    data['base_model_sha256'] = digest(checkpoint)
    data['parent_dataset_sha256'] = parent_hash
    data['warnings'].append('Switch retention uses byte-identical existing train windows; all head IDs, original reviews and inspected negatives retained. No new independent data.')
    (output / 'manifest.json').write_text(json.dumps(data, indent=2))
    config = yaml.safe_load((parent / 'data.yaml').read_text())
    config['path'] = output.resolve().as_posix()
    (output / 'data.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    validate_training_sources(output, data)
    return {'retained_switch_views': len(replicas), 'classes': 80,
            'manifest_sha256': digest(output / 'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'checkpoint', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('prepared', 'inspection'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--negative-phase-replay', action='store_true')
    parser.add_argument('--hard-negative-mining', action='store_true')
    parser.add_argument('--switch-retention-replay', action='store_true')
    args = parser.parse_args()
    if args.switch_retention_replay:
        if args.prepared or args.inspection or args.negative_phase_replay or args.hard_negative_mining:
            parser.error('Switch retention uses existing immutable training windows only')
        print(json.dumps(restore_switch_replay(args.parent, args.checkpoint, args.output)))
    elif args.negative_phase_replay:
        if args.prepared or args.inspection:
            parser.error('Negative replay uses existing inspected artifacts only')
        print(json.dumps(replay_negatives(args.parent, args.checkpoint, args.output, hard_mining=args.hard_negative_mining)))
    else:
        if args.hard_negative_mining:
            parser.error('Hard-negative mining requires the explicit inspected-negative replay')
        if not args.prepared or not args.inspection:
            parser.error('Source preparation requires prepared source and exact inspection')
        print(json.dumps(prepare(args.parent, args.prepared, args.inspection, args.checkpoint, args.output)))
