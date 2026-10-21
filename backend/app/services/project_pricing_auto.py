"""Conservative column and exact-product recognition for one-step pricing uploads."""
import re
from app.repositories import project_pricing_repository as repository
from app.schemas.project_pricing import PreviewRequest
from app.services.client_workbook import read_cells
from app.services.material_workbook import WorkbookError

ALIASES = {
    'name': {'description', 'material', 'materialname', 'materialdescription', 'item', 'itemname', 'itemdescription', 'product', 'productname'},
    'code': {'code', 'sku', 'itemcode', 'materialcode', 'productcode'},
    'specification': {'specification', 'specifications', 'spec', 'specs'},
    'unit': {'unit', 'units', 'purchaseunit', 'uom', 'unitofmeasure'},
    'unit_price': {'unitprice', 'price', 'rate', 'unitcost', 'quotedprice'},
    'currency': {'currency', 'currencycode'},
    'quantity': {'quantity', 'qty', 'clientquantity', 'clientqty'},
    'units_per_purchase': {'catalogunitsperpurchase', 'unitsperpurchase', 'metresperpurchase', 'metersperpurchase'},
}


def _identity(value):
    # Preserve punctuation, dimensions, brand and ratings. Never fuzzy-match SKUs.
    return ' '.join(value.casefold().split())


def table(data, name):
    """Recognize one bounded pricing table without consulting any catalog."""
    sheets = read_cells(data, name)
    candidates = []
    for sheet, rows in sheets.items():
        for row in rows[:20]:
            if row['formulas']:
                continue
            columns, currencies, duplicates = {}, set(), set()
            for column, label in row['cells'].items():
                currency = re.search(r'(?:\(|\s|/)([A-Z]{3})\)?\s*$', label, re.I)
                bare = label[:currency.start()] if currency else label.replace('₱', '')
                key = re.sub(r'[^a-z0-9]', '', bare.casefold())
                if key not in ALIASES['unit_price']:
                    currency = None
                    key = re.sub(r'[^a-z0-9]', '', label.casefold())
                elif '₱' in label:
                    currencies.add('PHP')
                elif currency:
                    currencies.add(currency[1].upper())
                for field, aliases in ALIASES.items():
                    if key in aliases:
                        if field in columns:
                            duplicates.add(field)
                        columns[field] = column
            if {'name', 'unit', 'unit_price'} <= columns.keys():
                if duplicates or len(currencies) > 1:
                    raise WorkbookError('Pricing headers are ambiguous. Keep one Description, Unit and Unit price column.')
                if 'currency' not in columns and not currencies:
                    raise WorkbookError('Include a Currency column, or label the price column with its currency, such as Unit price (PHP).')
                candidates.append((sheet, row['row'], columns, next(iter(currencies), None)))
    if len(candidates) != 1:
        raise WorkbookError('Upload one pricing table with Description, Unit, Unit price and Currency headers. Multiple tables must be uploaded separately.')
    sheet, header, columns, currency = candidates[0]
    return sheets, sheet, header, columns, currency


def selection(session, data, name, *, allow_unresolved=False):
    from app.services.project_pricing_service import _unit
    sheets, sheet, header, columns, currency = table(data, name)
    by_code, by_name = {}, {}
    for material in repository.materials(session):
        if material.is_active:
            by_code.setdefault(_identity(material.code), []).append(material)
            by_name.setdefault(_identity(material.name), []).append(material)
    choices = []
    for row in sheets[sheet]:
        if row['row'] <= header:
            continue
        raw = {field: row['cells'].get(column, '') for field, column in columns.items()}
        if not any(raw.values()) and not set(row['formulas']).intersection(columns.values()):
            continue
        code = raw.get('code', '')
        matches = by_code.get(_identity(code), []) if code else by_name.get(_identity(raw['name']), [])
        if len(matches) != 1:
            if allow_unresolved:
                choices.append(dict(row_id=f'{sheet}:{row["row"]}', material_id=None))
                continue
            raise WorkbookError(f'Row {row["row"]}: no unique catalog match for {(code or raw["name"])[:80]}. Use an exact catalog Code or Description.')
        conversion = '1'
        if _unit(raw['unit']) != matches[0].unit and not allow_unresolved:
            raise WorkbookError(f'Row {row["row"]}: supply the price per {matches[0].unit}, matching the catalog purchase unit. Pack or roll conversions cannot be assumed.')
        if _unit(raw['unit']) != matches[0].unit:
            from decimal import Decimal, InvalidOperation
            try:
                value = Decimal(raw.get('units_per_purchase', ''))
                conversion = str(value) if value.is_finite() and 0 < value <= 100000 else None
            except InvalidOperation:
                conversion = None
        choices.append(dict(row_id=f'{sheet}:{row["row"]}', material_id=matches[0].id, units_per_purchase=conversion))
    return PreviewRequest.model_validate(dict(automatic=True, mapping=dict(
        kind='client_bom' if 'quantity' in columns else 'price_list', sheet=sheet,
        header_row=header, columns=columns, currency=currency), choices=choices))
