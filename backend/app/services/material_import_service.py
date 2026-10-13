"""Admin-only, all-or-nothing price import with optimistic revision checks."""
from datetime import datetime, timezone
from decimal import Decimal
import logging

from app.repositories import material_catalog_repository as catalog
from app.repositories import material_price_repository as prices
from app.schemas.material_price import MaterialPriceWrite
from app.services.material_price_service import update_material_price
from app.services.material_workbook import extract_prices, WorkbookError

logger = logging.getLogger(__name__)


def _admin(user):
    if getattr(getattr(user, 'role', None), 'name', None) != 'ADMIN':
        raise PermissionError('Only an Admin can import prices.')


def preview(session, user, data):
    _admin(user)
    parsed = extract_prices(data)
    for row in parsed['rows']:
        material = catalog.by_code(session, row['code'])
        previous = prices.last_revision(session, material.id) if material else None
        reason = ('Existing material is inactive.' if material and not material.is_active else
            'Existing unit/name differs; do not overwrite its identity.' if material and
            (material.unit != row['unit'] or material.name != row['name']) else None)
        row.update(current_price=str(previous.unit_price) if previous else None,
            current_currency=previous.currency if previous else None, version=previous.version_number if previous else 0,
            eligible=reason is None, reason=reason)
    return parsed


def apply(session, user, data, selection):
    _admin(user)
    parsed = extract_prices(data)
    if parsed['file_sha256'] != selection.file_sha256:
        raise WorkbookError('File changed. Preview it again.')
    rows = {row['row_id']: row for row in parsed['rows']}
    if not set(selection.expected_versions).issubset(rows):
        raise WorkbookError('An import row is unavailable. Preview again.')
    result = dict(file_sha256=parsed['file_sha256'], created=0, updated=0, unchanged=0)
    now = datetime.now(timezone.utc)
    for row in sorted((rows[key] for key in selection.expected_versions), key=lambda item: item['code']):
        material = catalog.by_code(session, row['code'], lock=True)
        previous = prices.last_revision(session, material.id) if material else None
        if (previous.version_number if previous else 0) != selection.expected_versions[row['row_id']]:
            raise WorkbookError('A price changed since preview. Reload before applying.')
        if material and (not material.is_active or material.unit != row['unit'] or material.name != row['name']):
            raise WorkbookError('A material identity changed. Preview again.')
        if not material:
            material = catalog.create(session, {key: row[key] for key in ('code', 'name', 'unit', 'category')})
            result['created'] += 1
        amount = Decimal(row['unit_price'])
        if previous and previous.unit_price == amount and previous.currency == selection.currency:
            result['unchanged'] += 1
            continue
        update_material_price(session, current_user=user, material_id=material.id,
            request=MaterialPriceWrite(unit_price=amount, currency=selection.currency, effective_at=now))
        result['updated'] += 1
    session.commit()
    logger.info('MATERIAL_PRICES_IMPORTED user_id=%s file_sha256=%s created=%s updated=%s unchanged=%s',
        user.id, result['file_sha256'], result['created'], result['updated'], result['unchanged'])
    return result
