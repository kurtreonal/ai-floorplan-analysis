"""Pinned source crops from the supplied PEC reference; never model promotion."""
from functools import lru_cache
from io import BytesIO
import json

from PIL import Image, ImageOps

from app.core.config import REPOSITORY_ROOT
from app.services.pdf_legend_catalog import _verified_file
from app.services.legend_identity import meaning_key

SOURCE = '8fa0851445cbe840c59af1b59042369aec4dc78eef8401f10e18ca22736f3af3'
ROOT = REPOSITORY_ROOT / 'storage/training'
CLEAN = ROOT / 'pec-reference-20261005-clean-v3'
PREPARED = ROOT / 'pec-reference-20261005-v3/prepared'

# Presentation defaults, not class equivalence or electrical specifications.
# Existing drawing artwork and explicit Admin choices take priority.
DISPLAY_DEFAULTS = {
    '1 x 40 watts fluorescent lamp': 'R1_20_5-ceiling',
    'conventional smoke detector': 'R1_36_5-as_shown',
}


@lru_cache(maxsize=1)
def _registry():
    manifest = json.loads(_verified_file(CLEAN, 'manifest.json',
        '44d16ab12d86bf12b0900b33caff5a6021483456b807fa0090a68336cbc50240', 256000))
    prepared = json.loads(_verified_file(PREPARED, 'manifest.json',
        '3cdbe5e0a9453cc7fe3ff213d8a9bc7c3d98ac4e0098895c8e5061c4fab2e5f7', 256000))
    permission = json.loads(_verified_file(PREPARED, 'source-authorization.json', prepared['authorization_sha256'], 64000))
    if (manifest['source_sha256'] != SOURCE or prepared['source_sha256'] != SOURCE
            or permission.get('source_sha256') != SOURCE
            or permission.get('authorization_kind') != 'user_attested_source_permission'
            or 'reference_grounding' not in permission.get('allowed_purposes', [])):
        raise ValueError('PEC reference identity unavailable')
    _verified_file(PREPARED, 'original.pdf', SOURCE, 25 * 1024 * 1024)
    rows = {row['glyph_id']: row for row in manifest['references'] if row['annotation_layer'] == 'symbols'}
    if len(rows) != 62 or any(row['source_sha256'] != SOURCE for row in rows.values()):
        raise ValueError('PEC symbol coverage differs')
    return rows


def reference_images():
    result = []
    for row in _registry().values():
        label = row['proposed_label']
        if row['reference_id'].startswith('1.21.'):
            label = 'Switch — ' + label
        elif row['reference_id'].startswith('1.36.'):
            label = 'Fire alarm — ' + label
        suffix = '' if row['variant'] == 'as_shown' else ' · ' + row['variant']
        result.append(dict(id=row['glyph_id'], label=label + suffix, reference=row['reference_id'],
                           variant=row['variant'], source='Supplied PEC reference'))
    return result


@lru_cache(maxsize=128)
def reference_png(glyph_id):
    row = _registry().get(glyph_id)
    if row is None:
        raise ValueError('Choose a device symbol from the PEC reference list.')
    raw = _verified_file(CLEAN, row['filename'], row['glyph_sha256'], 2 * 1024 * 1024)
    with Image.open(BytesIO(raw)) as source:
        # Display contrast and containment only; retain the source symbol shape.
        image = ImageOps.autocontrast(source.convert('L'))
        image.thumbnail((256, 256))
        output = BytesIO(); image.save(output, format='PNG', optimize=True)
        return output.getvalue()


@lru_cache(maxsize=1)
def _bindings():
    manifest = json.loads(_verified_file(ROOT / 'pec-replay-20261005-v3', 'manifest.json',
        '44ccde85ff0470c462b2d2080bc5240817a49d53bac61aa82309dee290457099', 5_000_000))
    bindings = {}
    for row in manifest['reference_specification']['point_mappings']:
        # Only existing, recorded semantic links; no guessed mounting variant.
        if len(row['glyph_ids']) != 1:
            continue
        labels = [link['label'] for link in row['catalog_links']]
        if row['existing_model_aliases']:
            labels.append(row['model_label'])
        for label in labels:
            bindings.setdefault(meaning_key(label), set()).add(row['glyph_ids'][0])
    return {label: next(iter(ids)) for label, ids in bindings.items() if len(ids) == 1}


def matched_reference_id(name):
    key = meaning_key(name)
    return _bindings().get(key) or DISPLAY_DEFAULTS.get(key)


def matched_reference_png(name):
    identity = matched_reference_id(name)
    return reference_png(identity) if identity else None


def populate_missing_artwork(db, user, legends):
    """Add missing reference icons during an explicit Admin import, not a GET."""
    from app.services.legend_artwork_service import latest, append_png
    added = 0
    for legend in legends:
        if '[pdf-' in legend.name or latest(db, legend.id):
            continue
        identity = matched_reference_id(legend.name)
        if identity is None:
            continue
        with Image.open(BytesIO(reference_png(identity))) as source:
            output = BytesIO(); source.convert('RGBA').save(output, format='PNG', optimize=True)
        added += append_png(db, user, legend.id, output.getvalue(), f'Supplied PEC reference {identity}')
    return added
