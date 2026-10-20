"""Explicit client mappings and immutable quotes; no catalog updates or quantity replacement."""
from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import logging
import re
from app.repositories import project_pricing_repository as repository
from app.schemas.project_pricing import VersionSummary
from app.services.client_workbook import MAX_ROWS, filename, read_cells
from app.services.material_workbook import WorkbookError
from app.services.project_service import get_accessible_project

logger = logging.getLogger(__name__)


class PricingConflict(WorkbookError):
    pass


def _access(session, user, project_id, write=False):
    if write and user.role.name != 'DESIGNER':
        raise PermissionError('A Designer must confirm project imports.')
    get_accessible_project(session, current_user=user, project_id=project_id)


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _unit(value):
    return {'m': 'meter', 'meters': 'meter', 'metre': 'meter', 'metres': 'meter',
        'pc': 'piece', 'pcs': 'piece', 'pieces': 'piece'}.get(value.lower(), value.lower())


def _amount(value, label):
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount >= Decimal('1e12') or amount.as_tuple().exponent < -4:
            raise ValueError()
        return str(amount)
    except (InvalidOperation, ValueError):
        raise WorkbookError(label + ' needs a nonnegative number with up to four decimals; blanks are not zero.') from None


def inspect_file(session, user, project_id, data, name, sheet=None, header_row=1):
    _access(session, user, project_id, write=True)
    sheets = read_cells(data, name)
    selected = sheet or next(iter(sheets))
    if selected not in sheets:
        raise WorkbookError('Choose an existing worksheet.')
    header = next((row for row in sheets[selected] if row['row'] == header_row), None)
    if header is None or header['formulas']:
        raise WorkbookError('Choose a populated, non-formula header row.')
    return dict(file_sha256=sha256(data).hexdigest(), sheets=list(sheets), sheet=selected,
        header_row=header_row, columns=[dict(id=key, label=value or key) for key, value in header['cells'].items()],
        sample=[row for row in sheets[selected] if row['row'] > header_row][:3])


def preview(session, user, project_id, data, name, request, lock=False):
    _access(session, user, project_id, write=True)
    sheets = read_cells(data, name)
    mapping = request.mapping
    if mapping.sheet not in sheets or not any(row['row'] == mapping.header_row for row in sheets[mapping.sheet]):
        raise WorkbookError('The selected worksheet or header is unavailable.')
    choices = {row.row_id: row for row in request.choices}
    materials = {row.id: row for row in repository.materials(session)}
    if lock:
        for material in repository.materials(session, ids=sorted({row.material_id for row in request.choices if row.material_id}), lock=True):
            materials[material.id] = material
    columns = mapping.columns.model_dump(exclude_none=True)
    rows = []
    for source in sheets[mapping.sheet]:
        if source['row'] <= mapping.header_row:
            continue
        raw = {field: source['cells'].get(column, '') for field, column in columns.items()}
        if not any(raw.values()) and not set(source['formulas']).intersection(columns.values()):
            continue
        row_id = mapping.sheet + ':' + str(source['row'])
        choice = choices.get(row_id)
        row = dict(row_id=row_id, source=raw, name=raw.get('name', ''), code=raw.get('code', ''),
            specification=raw.get('specification', ''), unit=_unit(raw.get('unit', '')),
            unit_price=None, currency=raw.get('currency', '') if mapping.columns.currency else mapping.currency,
            client_quantity=None, material_id=choice.material_id if choice else None,
            units_per_purchase=None, excluded=bool(choice and choice.excluded), reasons=[])
        if set(source['formulas']).intersection(columns.values()):
            row['reasons'].append('Mapped formula cells are not evaluated. Supply literal values.')
        if not row['name'] or len(row['name']) > 255 or len(row['code']) > 64 or len(row['specification']) > 500:
            row['reasons'].append('A description (up to 255 characters), bounded code and specification are required.')
        if not row['unit'] or len(row['unit']) > 32 or row['unit'].startswith(('=', '+', '-', '@')) or any(ord(char) < 32 for char in row['unit']):
            row['reasons'].append('Specify the quoted purchase unit.')
        if not re.fullmatch(r'[A-Z]{3}', row['currency'] or ''):
            row['reasons'].append('Specify a three-letter uppercase currency.')
        for field, target, label in [('unit_price', 'unit_price', 'Unit price'),
                *([('quantity', 'client_quantity', 'Client quantity')] if mapping.kind == 'client_bom' else [])]:
            try:
                row[target] = _amount(raw.get(field, ''), label)
            except WorkbookError as error:
                row['reasons'].append(str(error))
        material = materials.get(row['material_id'])
        if material is None or not material.is_active:
            row['reasons'].append('Select an active catalog material explicitly.')
        else:
            row.update(catalog_code=material.code, catalog_name=material.name, catalog_unit=material.unit)
            if request.usage == 'item_selection':
                from app.services.product_compatibility import family, specifications_match
                source_text = row['name'] + ' ' + row['specification']
                source_family = family(source_text)
                catalog_family = family(material.category + ' ' + material.name)
                if ((source_family and source_family != catalog_family) or
                        not specifications_match(source_text,material.name)):
                    row['reasons'].append('The selected catalog product conflicts with the quoted type or specification.')
            same_unit = row['unit'] == material.unit
            conversion = choice.units_per_purchase if choice else None
            if same_unit and conversion not in (None, Decimal(1)):
                row['reasons'].append('Identical purchase units require a conversion of one.')
            elif same_unit:
                row['units_per_purchase'] = '1'
            elif conversion is None:
                row['reasons'].append('Specify catalog units per quoted purchase unit; no pack/roll size is assumed.')
            else:
                row['units_per_purchase'] = str(conversion)
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise WorkbookError('Import is limited to 1,000 data rows.')
    if not rows or not set(choices).issubset({row['row_id'] for row in rows}):
        raise WorkbookError('No mapped data rows, or a row decision no longer exists.')
    selected = [row for row in rows if not row['excluded']]
    codes = Counter(row['code'].casefold() for row in selected if row['code'])
    ids = Counter(row['material_id'] for row in selected if row['material_id'])
    for row in rows:
        if not row['excluded'] and ((row['code'] and codes[row['code'].casefold()] > 1) or
                (row['material_id'] and ids[row['material_id']] > 1)):
            row['reasons'].append('Duplicate source code or material mapping. Explicitly exclude a duplicate or correct the source.')
    document = dict(mapping=mapping.model_dump(mode='json'), rows=rows)
    if document['mapping']['columns'].get('units_per_purchase') is None:
        document['mapping']['columns'].pop('units_per_purchase', None)
    if request.usage == 'item_selection':
        document['usage'] = request.usage
    if request.automatic:
        document['matching_method'] = 'automatic_exact_identity'
    return dict(file_sha256=sha256(data).hexdigest(), preview_token=_hash(document),
        expected_version=repository.latest_version(session, project_id, lock=lock), document=document,
        ready=bool(selected) and all(not row['reasons'] for row in selected),
        materials=[dict(id=row.id, code=row.code, name=row.name, unit=row.unit) for row in materials.values() if row.is_active])


def automatic_preview(session, user, project_id, data, name, *, usage='project_default'):
    from app.services.project_pricing_auto import selection
    _access(session, user, project_id, write=True)
    recognized = selection(session, data, name, allow_unresolved=usage == 'item_selection')
    if usage == 'item_selection':
        recognized = recognized.model_copy(update={'automatic':False, 'usage':usage})
        return preview(session, user, project_id, data, name, recognized)
    result = preview(session, user, project_id, data, name, recognized)
    for row in result['document']['rows']:
        if row['reasons']:
            raise WorkbookError(f'{row["row_id"]}: {row["reasons"][0]} Use the catalog purchase unit and literal prices.')
    if not result['ready']:
        raise WorkbookError('The file contains no usable material prices.')
    return result


def apply(session, user, project_id, data, name, request):
    _access(session, user, project_id, write=True)
    name = filename(name)
    source_hash = sha256(data).hexdigest()
    # Keep the request identity of pre-automatic imports compatible for retries.
    excluded = ({'automatic'} if not request.automatic else set()) | ({'usage'} if request.usage == 'project_default' else set())
    identity = request.model_dump(mode='json', exclude=excluded) | {'actual_file_sha256': source_hash, 'filename': name}
    if identity['mapping']['columns'].get('units_per_purchase') is None:
        identity['mapping']['columns'].pop('units_per_purchase', None)
    request_hash = _hash(identity)
    repository.lock_project(session, project_id)
    previous = repository.retry(session, project_id, str(request.request_id))
    if previous:
        if previous.request_hash != request_hash:
            raise PricingConflict('This retry contains different inputs. Preview again.')
        session.commit()
        return VersionSummary.model_validate(previous)
    if request.automatic:
        from app.services.project_pricing_auto import selection
        recognized = selection(session, data, name)
        if recognized.mapping != request.mapping or recognized.choices != request.choices:
            raise PricingConflict('The recognized materials changed. Upload the file again.')
    result = preview(session, user, project_id, data, name, request, lock=True)
    if source_hash != request.file_sha256 or result['preview_token'] != request.preview_token:
        raise PricingConflict('The source or material mapping changed. Preview again.')
    if result['expected_version'] != request.expected_version:
        raise PricingConflict('Another import was saved. Preview again.')
    if not result['ready']:
        raise WorkbookError('Resolve or explicitly exclude every incomplete/duplicate row before saving.')
    record = repository.append(session, project_id=project_id, version_number=request.expected_version + 1,
        created_by_user_id=user.id, request_id=str(request.request_id), request_hash=request_hash,
        filename=name, file_sha256=source_hash, kind=request.mapping.kind,
        document=result['document'], source_bytes=data)
    session.commit()
    logger.info('PROJECT_PRICES_IMPORTED project_id=%s version_id=%s user_id=%s', project_id, record.id, user.id)
    return VersionSummary.model_validate(record)


def list_versions(session, user, project_id):
    _access(session, user, project_id)
    return repository.versions(session, project_id)


def get_version(session, user, project_id, version_id):
    _access(session, user, project_id)
    record = repository.find(session, project_id, version_id)
    if record is None:
        raise LookupError('Project price version not found.')
    return record


def accepted_rows(record):
    return {row['material_id']: row for row in record.document['rows'] if not row['excluded']}


def current_catalog_prices(session, user, project_id, materials):
    """Latest confirmed project quote, expressed per catalog unit for draft takeoff.

    Never mutates the shared catalog, chooses a substitute product, or mixes in
    catalog prices for materials absent from the selected project import.
    """
    _access(session, user, project_id)
    version = repository.current(session, project_id)
    if version is None:
        return materials, None
    quotes = accepted_rows(version)
    result = []
    for material in materials:
        row = dict(material, unit_price=None, currency=None, price_revision_id=None,
            price_source='project', project_price_version_id=version.id,
            price_unavailable_reason='missing_project_material_price')
        quote = quotes.get(material['id'])
        if quote:
            if (quote['catalog_unit'], quote['catalog_code'], quote['catalog_name']) != (
                    material['unit'], material['code'], material['name']):
                row['price_unavailable_reason'] = 'project_material_identity_changed'
            else:
                row.update(unit_price=Decimal(quote['unit_price']) / Decimal(quote['units_per_purchase']),
                    currency=quote['currency'], project_price_row_id=quote['row_id'],
                    price_unavailable_reason=None)
        result.append(row)
    return result, VersionSummary.model_validate(version).model_dump(mode='json')


def compare_estimate(session, user, project_id, record, estimate_id):
    from app.services.estimate_service import retrieve_estimate, EstimateError
    try:
        estimate = retrieve_estimate(session, user, project_id, estimate_id)
    except EstimateError:
        raise LookupError('Estimate not found.') from None
    sources = (estimate.get('source') or {}).get('price_sources')
    result = []
    for row in record.document['rows']:
        if row['excluded']:
            continue
        found = [(index, item) for index, item in enumerate(estimate['items']) if item.material_id == row['material_id']]
        total, reason = Decimal(0), None
        for index, item in found:
            source = sources[index] if sources and index < len(sources) else None
            catalog_unit = source['catalog_unit'] if source else item.unit
            if catalog_unit != row['catalog_unit'] or (source and source['material_id'] != item.material_id):
                reason = 'Estimate units cannot be reconciled with this import without an explicit conversion.'
                break
            total += item.quantity * Decimal(source['units_per_purchase'] if source else '1')
        if not found:
            reason = 'This material is not included in the selected calculated estimate.'
        calculated = total / Decimal(row['units_per_purchase']) if not reason else None
        client = Decimal(row['client_quantity']) if row['client_quantity'] is not None else None
        result.append(dict(row_id=row['row_id'], material_id=row['material_id'], client_quantity=str(client) if client is not None else None,
            calculated_quantity=str(calculated) if calculated is not None else None, unit=row['unit'],
            difference=str(calculated - client) if calculated is not None and client is not None else None, reason=reason))
    return result
