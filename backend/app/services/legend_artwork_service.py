from hashlib import sha256
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException
from sqlalchemy import select
from app.models import LegendArtwork, SymbolLegend
from app.services.activity_log import record


def latest(db, legend_id):
    return db.scalar(select(LegendArtwork).where(LegendArtwork.legend_id == legend_id).order_by(LegendArtwork.id.desc()).limit(1))


def append_png(db, user, legend_id, data, origin):
    digest = sha256(data).hexdigest()
    previous = latest(db, legend_id)
    if previous and previous.sha256 == digest:
        return False
    db.add(LegendArtwork(legend_id=legend_id, png=data, sha256=digest, created_by_user_id=user.id))
    record(db, user, 'LEGEND_ARTWORK_UPDATED', 'legend', legend_id,
           f'{origin}: 2D legend artwork saved. Device identities and geometry unchanged.')
    return True


def matching_legends(db, legend_id, legend_ids=None):
    ids = list(dict.fromkeys(legend_ids or [legend_id]))
    if legend_id not in ids or len(ids) > 256 or any(type(value) is not int or value < 1 for value in ids):
        raise HTTPException(422, 'Choose matching legend entries.')
    rows = list(db.scalars(select(SymbolLegend).where(SymbolLegend.id.in_(ids)).order_by(SymbolLegend.id).with_for_update()))
    if len(rows) != len(ids):
        raise HTTPException(404, 'Legend not found.')
    from app.services.legend_identity import same_meaning
    if len(rows) > 1 and not same_meaning([row.name for row in rows]):
        raise HTTPException(422, 'Only duplicate definitions of the same device can be updated together.')
    return rows


def save(db, user, legend_id, content, *, legend_ids=None, reference_id=None):
    if user.role.name != 'ADMIN':
        raise HTTPException(403, 'Only Admin can change legend images.')
    rows = matching_legends(db, legend_id, legend_ids)
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(422, 'Choose a PNG, JPEG or WebP image up to 2 MB.')
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width > 4096 or image.height > 4096 or image.width < 1 or image.height < 1:
                raise ValueError()
            image.load()
            normalized = image.convert('RGBA')
            normalized.thumbnail((512, 512))
            output = BytesIO(); normalized.save(output, format='PNG', optimize=True)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(422, 'This image could not be read. Use PNG, JPEG or WebP, at most 4096 × 4096 pixels.') from None
    data = output.getvalue()
    digest = sha256(data).hexdigest()
    for row in rows:
        origin = f'Supplied PEC reference {reference_id}' if reference_id else 'Uploaded image'
        append_png(db, user, row.id, data, origin)
    db.commit()
    return {'status': 'saved', 'sha256': digest, 'legend_ids': [row.id for row in rows]}
