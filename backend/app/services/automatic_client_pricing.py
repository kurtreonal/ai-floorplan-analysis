"""One upload prices existing items from the client's own products, not VED prices."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

from app.repositories import item_price_repository as assignments
from app.repositories import project_pricing_repository as prices
from app.services import project_pricing_service as pricing
from app.services.client_workbook import MAX_ROWS, filename
from app.services.material_workbook import WorkbookError
from app.services.product_compatibility import family, specifications_match
from app.services.project_pricing_auto import table

METHOD = 'automatic_client_specification'


def is_client_quote(quote):
    return quote.get('pricing_basis') == 'client_product'


def parse(data, name):
    sheets, sheet, header, columns, currency = table(data, name)
    rows = []
    for source in sheets[sheet]:
        if source['row'] <= header:
            continue
        raw = {key: source['cells'].get(column, '') for key, column in columns.items()}
        if not any(raw.values()) and not set(source['formulas']).intersection(columns.values()):
            continue
        text = raw['name'] + ' ' + raw.get('specification', '')
        kind = family(text)
        unit = pricing._unit(raw['unit'].strip().rstrip('.'))
        unit = {'unit':'piece', 'ea':'piece', 'each':'piece', 'mtr':'meter', 'mtrs':'meter', 'lm':'meter'}.get(unit, unit)
        row = dict(row_id=f'{sheet}:{source["row"]}', source=raw, name=raw['name'],
            code=raw.get('code', ''), specification=raw.get('specification', ''),
            pricing_basis='client_product', family=kind, unit=unit,
            quantity_unit='meter' if kind in ('wire','conduit') else 'piece',
            currency=(raw.get('currency', '') if 'currency' in columns else currency or '').upper(),
            unit_price=None, units_per_purchase=None, material_id=None, client_quantity=raw.get('quantity'),
            excluded=False, reasons=[])
        if not row['name'] or len(row['name']) > 255 or len(row['code']) > 64 or len(row['specification']) > 500:
            row['reasons'].append('Missing or overlong product description/specification.')
        pricing_columns={column for key,column in columns.items() if key!='quantity'}
        if set(source['formulas']).intersection(pricing_columns):
            row['reasons'].append('Use literal prices; workbook formulas are not executed.')
        if kind is None:
            row['reasons'].append('Device, wire/cable or conduit type was not identified.')
        if not re.fullmatch('[A-Z]{3}', row['currency']):
            row['reasons'].append('Currency is missing or invalid.')
        try:
            row['unit_price'] = pricing._amount(raw['unit_price'], 'Unit price')
        except WorkbookError as error:
            row['reasons'].append(str(error))
        try:
            conversion = Decimal(raw.get('units_per_purchase') or '1')
            if unit != row['quantity_unit']:
                if not raw.get('units_per_purchase'):
                    # Explicit package length is evidence, not a guessed roll size.
                    lengths = re.findall(r'(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\b', text, re.I) if kind in ('wire','conduit') else []
                    if len(set(lengths)) != 1 or unit not in ('roll','stock','length','stick'):
                        raise ValueError()
                    conversion = Decimal(lengths[0])
            elif conversion != 1:
                raise ValueError()
            if (not conversion.is_finite() or not Decimal('.0001') <= conversion <= 100000
                    or conversion.as_tuple().exponent < -4 or len(unit)>32):
                raise ValueError()
            row['units_per_purchase'] = str(conversion)
        except (InvalidOperation, ValueError):
            row['reasons'].append('Purchase unit needs an explicit piece/metre conversion.')
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise WorkbookError('Import is limited to 1,000 data rows.')
    if not rows:
        raise WorkbookError('The file contains no pricing rows.')
    # Exact duplicates are harmless; conflicting repeated codes are not a price choice.
    signatures, codes = {}, {}
    for row in rows:
        signature = pricing._hash({k:row[k] for k in ('code','name','specification','unit','unit_price','currency','units_per_purchase')})
        if signature in signatures:
            row['reasons'].append('Identical duplicate row; price retained once.')
        else:
            signatures[signature] = row['row_id']
        if row['code']:
            codes.setdefault(row['code'].casefold(), set()).add(signature)
    for row in rows:
        if row['code'] and len(codes[row['code'].casefold()]) > 1:
            row['reasons'].append('Conflicting prices/products use the same client code.')
        row['excluded'] = bool(row['reasons'])
    return dict(usage='item_selection', matching_method=METHOD, rows=rows,
        mapping=dict(sheet=sheet,header_row=header,columns=columns,currency=currency,
            kind='client_bom' if 'quantity' in columns else 'price_list'))


def compatible(row, quote):
    if row.get('material_conflict') or quote['excluded']:
        return False
    if row['kind'] == 'device' and row.get('class_id') is None:
        return False
    source = row['name'] + ' ' + (row.get('material_name') or '')
    expected = row.get('material_kind') if row['kind'] == 'path' else family(source)
    return (expected is not None and expected == quote['family'] and
        row['unit'] in (quote['quantity_unit'], 'unit' if quote['quantity_unit']=='piece' else 'source pixel') and
        specifications_match(source,quote['name']+' '+quote['specification']))


def target_fingerprint(row):
    return pricing._hash([row['item_kind'],row.get('class_id'),row['name'],
        row.get('material_id'),row.get('material_name'),row.get('material_kind')])


def quote_for(session, project_id, assignment, row, cache):
    version_id = assignment['price_version_id']
    if version_id not in cache:
        cache[version_id] = prices.find(session,project_id,version_id)
    version = cache[version_id]
    quote = next((q for q in version.document['rows'] if q['row_id']==assignment['price_row_id']),None) if version else None
    if (quote and is_client_quote(quote) and target_fingerprint(row)==assignment['fingerprint'] and compatible(row,quote)):
        return quote


def apply_row(row, quote, assignment, version_number):
    amount = Decimal(quote['unit_price']) / Decimal(quote['units_per_purchase'])
    row.update(client_product_name=quote['name'],client_product_code=quote['code'],
        client_product_specification=quote['specification'],client_unit_price=str(amount),
        client_price_unit=quote['quantity_unit'],price_source='client_upload',
        project_price_version_id=assignment['price_version_id'],project_price_row_id=quote['row_id'],
        item_price_assignment_version=version_number,price_revision_id=None,currency=quote['currency'])
    # Prices can be assigned before calibration/drop inputs exist, but a per-metre
    # quote must never appear as a per-pixel price or create a complete-looking cost.
    if row['unit']=='source pixel':
        row.update(unit_price=None,line_total=None)
    else:
        row['unit_price']=amount
        if not row.get('missing_vertical_inputs') and row['pricing_state'] not in (
                'measurement_incomplete','electrical_assignment_required','network_material_review_required','classification_required','scale_required'):
            row.update(line_total=Decimal(str(row['quantity']))*amount,pricing_state='priced')


def upload(session,user,project_id,data,name,request_id,floor_id=None):
    from app.services.item_pricing_service import inventory
    from app.repositories.routing_repository import lock_context
    from app.repositories.estimate_repository import floor_ids
    pricing._access(session,user,project_id,write=True)
    name=filename(name)
    identity=pricing._hash(dict(file_sha256=sha256(data).hexdigest(),filename=name,floor_id=floor_id,method=METHOD))
    floors=floor_ids(session,project_id)
    if floor_id is not None and floor_id not in floors:
        raise LookupError('Floor not found.')
    lock_context(session,project_id,floors)
    previous=prices.retry(session,project_id,str(request_id))
    if previous:
        if previous.request_hash!=identity:
            raise pricing.PricingConflict('Retry inputs changed. Upload the intended file again.')
        session.commit()
        return previous.document['application'] | dict(price_version_id=previous.id)
    document=parse(data,name)
    planning=inventory(session,user,project_id)
    current=assignments.current(session,project_id,lock=True)
    saved=deepcopy(current.document['assignments']) if current else {}
    rows=[row for row in planning['items'] if floor_id is None or row.get('floor_id')==floor_id]
    quotes=[q for q in document['rows'] if not q['excluded']]
    affected,skipped=[],[]
    for row in rows:
        # Exclude old client display metadata from the target; the original model
        # remains the identity/specification source through every repeated import.
        candidates=[quote for quote in quotes if compatible(row,quote)]
        if len(candidates)!=1:
            reason='Multiple compatible client products; specify the intended product in the file or plan.' if candidates else 'No compatible client product/specification in this file.'
            skipped.append(dict(item_key=row['item_key'],name=row['name'],reason=reason))
        else:
            affected.append((row,candidates[0]))
    report=dict(applied=len(affected),scope='project' if floor_id is None else 'floor',floor_id=floor_id,
        skipped=skipped,skipped_rows=[dict(row_id=q['row_id'],name=q['name'],reason=' '.join(q['reasons'])) for q in document['rows'] if q['excluded']])
    document['application']=report
    record=prices.append(session,project_id=project_id,version_number=prices.latest_version(session,project_id,lock=True)+1,
        created_by_user_id=user.id,request_id=str(request_id),request_hash=identity,filename=name,
        file_sha256=sha256(data).hexdigest(),kind=document['mapping']['kind'],document=document,source_bytes=data)
    for row,quote in affected:
        saved[row['item_key']]=dict(price_version_id=record.id,price_row_id=quote['row_id'],
            source_kind='client_product',fingerprint=target_fingerprint(row))
    if len(saved)>20000:
        raise WorkbookError('This project has reached the saved item-price limit.')
    if affected:
        assignments.append(session,project_id=project_id,version_number=(current.version_number if current else 0)+1,
            created_by_user_id=user.id,request_id=str(request_id),request_hash=identity,
            document=dict(assignments=saved,application=report))
    session.commit()
    return report | dict(price_version_id=record.id)
