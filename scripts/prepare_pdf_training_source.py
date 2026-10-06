"""Prepare an immutable, authorized PDF source; never invent reviewed labels."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai.floor_plan_interpretation.corpus_intake import (  # noqa: E402
    MAXIMUM_IMAGE_EDGE, MAXIMUM_IMAGE_PIXELS, MAXIMUM_PAGES,
    MAXIMUM_SOURCE_BYTES, _read_source_bounded, _verify_original_digest,
)
from app.services.upload_validation import validate_floor_plan_upload  # noqa: E402


def read_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError('Preparation metadata exceeds bound')
    return raw, json.loads(raw)


def render_size(size, dpi):
    scale = dpi / 72
    if not all(math.isfinite(v) and v > 0 for v in size):
        raise ValueError('Invalid PDF page dimensions')
    width, height = (math.ceil(value * scale) for value in size)
    if max(width, height) > MAXIMUM_IMAGE_EDGE or width * height > MAXIMUM_IMAGE_PIXELS:
        raise ValueError('PDF render exceeds allocation bounds')
    return width, height


def prepare(source, output, permission_path, pages, *, dpi=200, regions_path=None):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('PDF preparation revisions are immutable')
    if type(dpi) is not int or not 72 <= dpi <= 300:
        raise ValueError('DPI must be 72 through 300')
    content, source_hash = _read_source_bounded(source)
    validation = validate_floor_plan_upload(filename=source.name, declared_mime_type='application/pdf',
        content=content, max_file_size_bytes=MAXIMUM_SOURCE_BYTES)
    if validation.page_count > MAXIMUM_PAGES:
        raise ValueError('PDF exceeds page bound')
    if (not pages or any(type(p) is not int or not 1 <= p <= validation.page_count for p in pages)
            or len(set(pages)) != len(pages)):
        raise ValueError('Select distinct, explicit one-based PDF pages')
    permission_raw, permission = read_json(permission_path)
    if (permission.get('source_sha256') != source_hash
            or permission.get('authorization_kind') != 'user_attested_source_permission'
            or not permission.get('user_statement')
            or permission.get('allowed_purposes') != ['reference_grounding', 'training']
            or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}', str(permission.get('project_group_id', '')))):
        raise ValueError('Exact source-bound training permission required')
    regions_raw, regions = read_json(regions_path) if regions_path else (None, [])
    if not isinstance(regions, list) or len(regions) > 200:
        raise ValueError('Invalid region list')
    region_ids = set()
    document = pdfium.PdfDocument(content)
    page_sizes = {}
    try:
        # Validate allocations and every crop before any output is created.
        for number in sorted(pages):
            page = document[number - 1]
            try:
                page_sizes[number] = page.get_size()
                render_size(page_sizes[number], dpi)
            finally:
                page.close()
        for region in regions:
            number, box, identity = region['page_number'], region['bbox_pdf_top_left_points'], region['region_id']
            if (type(number) is not int or number not in page_sizes or not isinstance(identity, str)
                    or not identity.isascii() or not identity.replace('-', '').replace('_', '').isalnum()
                    or len(identity) > 80 or identity in region_ids or len(box) != 4
                    or identity in {f'page-{p:03d}' for p in pages}
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
                raise ValueError('Invalid region identity or coordinates')
            if not 0 <= box[0] < box[2] <= page_sizes[number][0] or not 0 <= box[1] < box[3] <= page_sizes[number][1]:
                raise ValueError('Region outside its source page')
            region_ids.add(identity)
        output.mkdir(parents=True, exist_ok=False)
        for filename, raw in [('original.pdf', content), ('source-authorization.json', permission_raw)]:
            with (output / filename).open('xb') as stream:
                stream.write(raw)
        if regions_raw is not None:
            with (output / 'source-region-proposals.json').open('xb') as stream:
                stream.write(regions_raw)
        manifest = {
            'schema': 'ved-authorized-pdf-preparation-v1', 'source_sha256': source_hash,
            'authorization_sha256': sha256(permission_raw).hexdigest(),
            'pdf_page_count': validation.page_count, 'dpi': dpi,
            'split': 'train', 'project_group_id': permission['project_group_id'],
            'project_relationships_to_existing_corpus': 'unverified_not_scored',
            'training_ready': False, 'reviewed_detection_targets': 0,
            'status': 'source_authorized_labels_pending', 'pages': [], 'regions': [],
            'missing_annotation_policy': 'ignore_unreviewed_not_empty_background',
        }
        for number in sorted(pages):
            page = document[number - 1]
            bitmap = image = text_page = None
            try:
                bitmap = page.render(scale=dpi / 72)
                if (max(bitmap.width, bitmap.height) > MAXIMUM_IMAGE_EDGE
                        or bitmap.width * bitmap.height > MAXIMUM_IMAGE_PIXELS):
                    raise ValueError('Unexpected renderer allocation')
                image = bitmap.to_pil()
                filename = f'page-{number:03d}.png'
                with (output / filename).open('xb') as stream:
                    image.save(stream, format='PNG')
                image_hash = sha256((output / filename).read_bytes()).hexdigest()
                text_page = page.get_textpage()
                count = text_page.count_chars()
                if count > 100_000:
                    raise ValueError('PDF text exceeds extraction bound')
                text = text_page.get_text_range(count=count)
                with (output / f'page-{number:03d}-text.txt').open('x', encoding='utf-8') as stream:
                    stream.write(text)
                manifest['pages'].append({
                    'page_number': number, 'source_page_id': f'{source_hash}:page:{number}',
                    'filename': filename, 'image_sha256': image_hash,
                    'width': image.width, 'height': image.height,
                    'coordinate_frame': 'rendered_page_top_left_points',
                    'pdf_page_rotation_degrees': page.get_rotation(),
                    'pdf_points_to_image': [dpi / 72, 0, 0, 0, dpi / 72, 0],
                    'text_extraction_state': 'available' if text else 'unavailable',
                    'review_state': 'pending', 'task_completeness': 'not_reviewed',
                })
                for region in (r for r in regions if r['page_number'] == number):
                    box = region['bbox_pdf_top_left_points']
                    pixels = [math.floor(box[0] * dpi / 72), math.floor(box[1] * dpi / 72),
                              math.ceil(box[2] * dpi / 72), math.ceil(box[3] * dpi / 72)]
                    crop_name = region['region_id'] + '.png'
                    crop = image.crop(pixels)
                    try:
                        with (output / crop_name).open('xb') as stream:
                            crop.save(stream, format='PNG')
                    finally:
                        crop.close()
                    manifest['regions'].append({**region, 'bbox_source_pixels': pixels,
                        'filename': crop_name, 'crop_sha256': sha256((output / crop_name).read_bytes()).hexdigest(),
                        'source_page_id': f'{source_hash}:page:{number}',
                        'source_image_sha256': image_hash, 'review_state': 'assistant_proposed',
                        'training_eligible': False})
            finally:
                if text_page is not None: text_page.close()
                if image is not None: image.close()
                if bitmap is not None: bitmap.close()
                page.close()
        _verify_original_digest(source, source_hash)
        with (output / 'manifest.json').open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, indent=2)
        return manifest
    finally:
        document.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--permission-record', type=Path, required=True)
    parser.add_argument('--page', type=int, action='append', required=True)
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--regions', type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.output, args.permission_record, args.page,
                     dpi=args.dpi, regions_path=args.regions)
    print(json.dumps({'pages': len(result['pages']), 'regions': len(result['regions']),
                      'status': result['status'], 'reviewed_detection_targets': 0}))
