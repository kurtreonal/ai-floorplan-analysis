"""Bounded frozen-model whole-PDF diagnostic; partial labels, not accuracy."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from math import floor, ceil
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation import multiclass_symbol_detector as runtime
from app.ai.floor_plan_interpretation.demo_cv import interpret_floor_plan_demo
from app.ai.floor_plan_interpretation.drawing_region import DrawingRegion, interpret_drawing_region, restore_region_predictions
from app.ai.floor_plan_interpretation.candidate import SourcePlane
from app.services.image_normalization import normalize_image
from app.services.pdf_conversion import convert_pdf_page
from probe_symbol_detector_dev import match_targets, validate_model_classes


def digest(path):
    with Path(path).open('rb') as stream:
        result = sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
        return result.hexdigest()


def recover_boxes(predictions, prepared_size, normalized_size):
    """Exact recorded raster scaling, including integer rounding on each axis."""
    if min(*prepared_size, *normalized_size) <= 0:
        raise ValueError('Invalid raster dimensions')
    sx, sy = prepared_size[0] / normalized_size[0], prepared_size[1] / normalized_size[1]
    def recover(row):
        result = {**row, 'bbox': [row['bbox'][0] * sx, row['bbox'][1] * sy,
                                 row['bbox'][2] * sx, row['bbox'][3] * sy]}
        if 'tile_origin' in row:
            result['tile_origin'] = [row['tile_origin'][0] * sx, row['tile_origin'][1] * sy]
        for key in ('localization_observations', 'equivalent_observations'):
            if key in row:
                result[key] = [recover(value) for value in row[key]]
        return result
    return [recover(row) for row in predictions]


def map_drawing_region(region, prepared_size, normalized_size):
    if min(*prepared_size, *normalized_size) <= 0:
        raise ValueError('Invalid raster dimensions')
    a, b, c, d = region['bbox_source_pixels']
    if not 0 <= a < c <= prepared_size[0] or not 0 <= b < d <= prepared_size[1]:
        raise ValueError('Drawing region lies outside its declared source raster')
    sx, sy = normalized_size[0] / prepared_size[0], normalized_size[1] / prepared_size[1]
    left, top, right, bottom = floor(a*sx), floor(b*sy), ceil(c*sx), ceil(d*sy)
    return DrawingRegion(x=left, y=top, width=right-left, height=bottom-top)


def page_targets(data, page, regions):
    """Reconcile declared whole-page and crop-local identities; never guess offsets."""
    frames = {page['image_sha256']: (0, 0, page['width'], page['height'])}
    for region in regions:
        if region['page_number'] == page['page_number']:
            a, b, c, d = region['bbox_source_pixels']
            if not 0 <= a < c <= page['width'] or not 0 <= b < d <= page['height']:
                raise ValueError('Declared source crop lies outside its page')
            frame = (a, b, c-a, d-b)
            if region['crop_sha256'] in frames and frames[region['crop_sha256']] != frame:
                raise ValueError('Ambiguous identical crop identity at different page locations')
            frames[region['crop_sha256']] = frame
    targets = []
    for key in ('lamp_source_targets', 'power_source_targets', 'switch_source_targets'):
        for row in data.get(key, []):
            frame = frames.get(row.get('source_sha256'))
            if row.get('page_number') != page['page_number'] or frame is None:
                continue
            x, y, width, height = frame
            a, b, c, d = row['source_box']
            if not 0 <= a < c <= width or not 0 <= b < d <= height:
                raise ValueError('Target box does not match its declared source frame')
            targets.append({**row, 'source_box': [a+x, b+y, c+x, d+y],
                            'evaluation_frame': page['image_sha256'],
                            'evaluation_offset': [x, y]})
    return targets


def inspect_existing_evidence(report_path, normalized_path, output):
    """Save unmatched source crops for assistant assessment, not false-positive truth."""
    report_path, normalized_path, output = map(Path, (report_path, normalized_path, output))
    if output.exists():
        raise FileExistsError('Inspection evidence revisions are immutable')
    if report_path.stat().st_size > 5_000_000:
        raise ValueError('Inspection report exceeds bounded size')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if digest(normalized_path) != report['normalized_sha256']:
        raise ValueError('Exact diagnostic raster required')
    paired = set(match_targets(report['targets_prepared_frame'], report['predictions_prepared_frame']).values())
    unmatched = [index for index in range(report['prediction_count']) if index not in paired]
    if len(unmatched) > 200:
        raise ValueError('Inspection exceeds existing candidate cap')
    output.mkdir(parents=True)
    with Image.open(normalized_path) as opened:
        if list(opened.size) != report['normalized_size']:
            raise ValueError('Diagnostic raster dimensions changed')
        image = opened.convert('RGB')
    try:
        sx, sy = image.width / report['prepared_size'][0], image.height / report['prepared_size'][1]
        atlas = Image.new('RGB', (300*max(1, min(3, len(unmatched))), 260*max(1, ceil(len(unmatched)/3))), 'white')
        try:
            pen = ImageDraw.Draw(atlas)
            records = []
            for position, index in enumerate(unmatched):
                row = report['predictions_prepared_frame'][index]
                a, b, c, d = row['bbox']
                left, top = max(0, floor(a*sx)-40), max(0, floor(b*sy)-40)
                right, bottom = min(image.width, ceil(c*sx)+40), min(image.height, ceil(d*sy)+40)
                crop = image.crop((left, top, right, bottom))
                try:
                    draw = ImageDraw.Draw(crop)
                    draw.rectangle((a*sx-left, b*sy-top, c*sx-left, d*sy-top), outline='orange', width=1)
                    preview = crop.resize((round(crop.width*2), round(crop.height*2)), Image.Resampling.NEAREST)
                    try:
                        atlas.paste(preview, ((position%3)*300, (position//3)*260+30))
                    finally:
                        preview.close()
                finally:
                    crop.close()
                pen.text(((position%3)*300+5, (position//3)*260+5), f"index {index} / model class {row['class_id']}", fill='black')
                records.append({'prediction_index': index, 'class_id': row['class_id'], 'source_box': row['bbox'],
                                'assessment': 'unmatched inspected positive; false-positive status requires source inspection'})
            atlas.save(output / 'unmatched-source-crops.png')
            (output / 'inspection.json').write_text(json.dumps({'report_sha256': digest(report_path),
                'normalized_sha256': report['normalized_sha256'], 'records': records,
                'human_review_claim': False, 'precision': None}, indent=2), encoding='utf-8')
        finally:
            atlas.close()
        return records
    finally:
        image.close()


def probe(pdf, prepared, dataset, output, *, drawing_regions=False):
    pdf, prepared, dataset, output = map(Path, (pdf, prepared, dataset, output))
    if output.exists():
        raise FileExistsError('Diagnostic evidence revisions are immutable')
    source = json.loads((prepared / 'manifest.json').read_text(encoding='utf-8'))
    data = json.loads((dataset / 'manifest.json').read_text(encoding='utf-8'))
    profiles = getattr(runtime, 'PROFILES', {})
    if 'power80' not in profiles or not callable(getattr(runtime, 'model_class_groups', None)):
        raise ValueError('This diagnostic requires the existing local power80/fusion workspace; no baseline substitution')
    profile = profiles['power80']
    if digest(pdf) != source['source_sha256'] or digest(dataset / 'manifest.json') != profile['training_dataset_sha256']:
        raise ValueError('Exact authorized source and frozen dataset required')
    if digest(profile['checkpoint']) != profile['checkpoint_sha256']:
        raise ValueError('Exact frozen development checkpoint required')
    page = next(row for row in source['pages'] if row['page_number'] == 7)
    if page.get('pdf_page_rotation_degrees') != 0 or digest(prepared / page['filename']) != page['image_sha256']:
        raise ValueError('Prepared page identity or orientation changed')
    for region in source['regions']:
        if region['page_number'] == page['page_number'] and digest(prepared / region['filename']) != region['crop_sha256']:
            raise ValueError('Prepared region identity changed')
    targets = page_targets(data, page, source['regions'])
    if not targets:
        raise ValueError('No identity-matched inspected positives')
    # Synthetic IDs are confined to low-level filesystem helpers; no DB/API write.
    output.mkdir(parents=True)
    rendered = convert_pdf_page(source_path=pdf, processed_directory=output / 'render',
                               floor_plan_id=1, processing_job_id=1, page_number=page['page_number'])
    normalized = normalize_image(source_path=rendered.absolute_output_path, source_mime_type='image/png',
        processed_directory=output / 'normalized', floor_plan_id=1, processing_job_id=1,
        page_number=page['page_number'])
    with Image.open(normalized.absolute_output_path) as opened:
        image = opened.convert('RGB')
    try:
        rgb = np.asarray(image)
        from ultralytics import YOLO
        model = YOLO(str(profile['checkpoint']))
        validate_model_classes(model, data['classes'])
        classes = {row['id']: (row['label'], row['legend_entry']) for row in data['classes']}
        catalog = {'model': model, 'classes': classes, 'threshold': .50, 'box_fusion': True,
                   'class_groups': runtime.model_class_groups(classes)}
        selected_regions = [(row, map_drawing_region(row, (page['width'], page['height']), image.size))
            for row in source['regions'] if row['page_number'] == page['page_number']
            and row['kind'] == 'partially_unannotated_layout'] if drawing_regions else []
        if drawing_regions and not selected_regions:
            raise ValueError('No existing manifest drawing regions')
        # One total page budget, not an increased cap per selected drawing.
        if sum(len(runtime.shared.tile_positions(region.width, region.height, dual_phase=True))
               for _, region in selected_regions) > runtime.shared.MAX_TILES:
            raise ValueError('Selected drawing windows exceed the existing page budget')
        predictions, wall_payloads, region_evidence = [], [], []
        wall_seconds, detection_seconds, truncated = 0., 0., False
        plane = SourcePlane(width_pixels=image.width, height_pixels=image.height)
        for row, region in selected_regions or [(None, None)]:
            started = time.perf_counter()
            walls = (interpret_drawing_region(rgb, region=region) if region is not None
                     else interpret_floor_plan_demo(rgb))
            wall_seconds += time.perf_counter() - started
            wall_payloads.append(walls.model_dump(mode='json'))
            view = rgb[region.y:region.y+region.height, region.x:region.x+region.width] if region is not None else rgb
            started = time.perf_counter()
            raw, partial = runtime.shared.locate(view, catalog=catalog)
            detection_seconds += time.perf_counter() - started
            predictions.extend(restore_region_predictions(raw, region=region, source_plane=plane) if region is not None else raw)
            if len(predictions) > runtime.shared.MAX_CANDIDATES or sum(len(value['walls']['items']) for value in wall_payloads) > 300:
                raise ValueError('Combined diagnostic exceeds the existing page candidate bounds')
            truncated |= partial
            if region is not None:
                region_evidence.append({'source_region_id': row['region_id'], 'source_crop_sha256': row['crop_sha256'],
                    'selection_origin': 'existing assistant-proposed source manifest; not target-derived or human-approved',
                    'normalized_region': region.model_dump(), 'raw_local_predictions': raw,
                    'wall_count': len(walls.walls.items), 'prediction_count': len(raw)})
        recovered = recover_boxes(predictions, (page['width'], page['height']), image.size)
        classified = match_targets(targets, recovered)
        localized = match_targets(targets, recovered, require_class=False)
        counts = Counter(row['class_id'] for row in recovered)
        report = {'schema': 'whole-pdf-frozen-development-probe-v2',
            'scope': 'Same supplied development PDF; inspected positives only; no independent project score.',
            'source_sha256': source['source_sha256'], 'source_page_id': page['source_page_id'],
            'prepared_image_sha256': page['image_sha256'], 'prepared_size': [page['width'], page['height']],
            'render_size': [rendered.width, rendered.height], 'render_dpi': rendered.dpi,
            'normalized_size': list(image.size), 'normalized_sha256': digest(normalized.absolute_output_path),
            'checkpoint_sha256': profile['checkpoint_sha256'], 'dataset_manifest_sha256': digest(dataset / 'manifest.json'),
            'threshold': .50, 'tile_size': runtime.shared.TILE_SIZE, 'tile_stride': runtime.shared.TILE_STRIDE,
            'tile_limit': runtime.shared.MAX_TILES, 'batch_size': 8, 'box_fusion': True,
            'targets': len(targets), 'class_and_location_matches': len(classified),
            'localization_matches': len(localized), 'prediction_count': len(predictions), 'truncated': truncated,
            'per_class': [{'class_id': key, 'targets': sum(row['class_id'] == key for row in targets),
                'matched': sum(targets[index]['class_id'] == key for index in classified), 'predictions': counts[key]}
                for key in sorted({row['class_id'] for row in targets})],
            'predictions_prepared_frame': recovered, 'targets_prepared_frame': targets,
            'analysis_scope': 'existing manifest drawing regions' if drawing_regions else 'whole normalized PDF page',
            'drawing_regions': region_evidence,
            'wall_payloads': wall_payloads,
            'wall_seconds': wall_seconds, 'detection_seconds': detection_seconds,
            'precision': None, 'independent_accuracy': None, 'human_review_claim': False,
            'matching': 'One-to-one class-aware IoU >= .50 in prepared-page coordinates',
            'software_sha256': {name: digest(Path(runtime.REPOSITORY_ROOT) / name) for name in (
                'backend/app/ai/floor_plan_interpretation/demo_cv.py',
                'backend/app/ai/floor_plan_interpretation/drawing_region.py',
                'backend/app/ai/floor_plan_interpretation/multiclass_symbol_detector.py',
                'backend/app/ai/wall_detection/detector.py',
                'backend/app/ai/floor_plan_interpretation/experimental_symbol_detector.py',
                'scripts/probe_whole_pdf_development.py')}}
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        pen = ImageDraw.Draw(image)
        for row in predictions:
            pen.rectangle(tuple(row['bbox']), outline='orange', width=2)
        sx, sy = image.width / page['width'], image.height / page['height']
        for index, target in enumerate(targets):
            a, b, c, d = target['source_box']
            pen.rectangle((a*sx, b*sy, c*sx, d*sy), outline='green' if index in classified else 'red', width=3)
        image.save(output / 'symbols.png')
        with Image.open(normalized.absolute_output_path) as opened:
            wall_image = opened.convert('RGB')
        try:
            pen = ImageDraw.Draw(wall_image)
            for payload in wall_payloads:
                for wall in payload['walls']['items']:
                    pen.line((wall['start']['x'], wall['start']['y'], wall['end']['x'], wall['end']['y']), fill='orange', width=3)
            for _, region in selected_regions:
                pen.rectangle((region.x, region.y, region.x+region.width, region.y+region.height), outline='blue', width=2)
            wall_image.save(output / 'walls.png')
        finally:
            wall_image.close()
        return {key: report[key] for key in ('render_size', 'normalized_size', 'targets',
            'class_and_location_matches', 'localization_matches', 'prediction_count', 'per_class',
            'wall_seconds', 'detection_seconds', 'precision', 'analysis_scope')}
    finally:
        image.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pdf', 'prepared', 'dataset', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--drawing-regions', action='store_true')
    args = parser.parse_args()
    import torch
    torch.set_num_threads(1)
    print(json.dumps(probe(args.pdf, args.prepared, args.dataset, args.output, drawing_regions=args.drawing_regions)))
