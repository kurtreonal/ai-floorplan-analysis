"""Read exact, source-bound legend artwork without changing originals."""
from functools import lru_cache
from io import BytesIO
import json
import re
from PIL import Image, ImageOps

from app.core.config import REPOSITORY_ROOT
from app.services.pdf_legend_catalog import SOURCES, _verified_file


@lru_cache(maxsize=256)
def _drawing_glyph(name):
    identity = re.search(r'\[(pdf-([a-f0-9]{12}):p(\d+):(L\d{2}))\]$', name)
    if identity is None:
        return None
    for folder, manifest_hash, source_hash, page_number, _ in SOURCES:
        if source_hash[:12] != identity[2] or page_number != int(identity[3]):
            continue
        directory = REPOSITORY_ROOT / 'storage/training' / folder
        manifest = json.loads(_verified_file(directory, 'manifest.json', manifest_hash, 256000))
        row = next((r for r in manifest['regions'] if r['region_id'] == identity[4] and r['page_number'] == page_number), None)
        if row is None or row.get('annotation_layer') != 'symbols':
            return None
        content = _verified_file(directory, row['filename'], row['crop_sha256'], 5 * 1024 * 1024)
        with Image.open(BytesIO(content)) as source:
            image = source.convert('RGB')
            ink = ImageOps.invert(image.convert('L')).point(lambda value: 255 if value > 80 else 0)
            bounds = ink.getbbox()
            if bounds:
                image = ImageOps.expand(image.crop(bounds), border=4, fill='white')
            image.thumbnail((256, 256))
            output = BytesIO(); image.save(output, format='PNG')
            return output.getvalue()
    return None


@lru_cache(maxsize=256)
def glyph_png(name):
    drawing = _drawing_glyph(name)
    if drawing is not None:
        return drawing
    from app.services.pec_legend_artwork import matched_reference_png
    return matched_reference_png(name)
