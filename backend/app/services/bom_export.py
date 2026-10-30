"""Supplier-facing BOM presentation; diagnostic provenance stays in the API."""
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

HEADERS = ['Category', 'Product name', 'Brand', 'Item number', 'Specification', 'Quantity', 'Unit', 'Unit price', 'Currency', 'Amount']


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def clean(value):
    return re.sub(r'\s*\[(?:pdf-[^\]]+|sheet[- :][^\]]+|u:[^\]]+)\]', '', str(value or ''), flags=re.I).strip()


def category(row):
    if row.get('layout_category'):
        from app.services.layout_materials import LABELS
        return LABELS.get(row['layout_category'],row['layout_category'])
    if row.get('material_kind') == 'wire':
        return 'Wire / cable'
    if row.get('material_kind') == 'conduit':
        return 'Conduit'
    from app.services.product_compatibility import family
    return {'light': 'Lighting', 'switch': 'Switches', 'outlet': 'Outlets', 'data': 'Data outlets',
        'panel': 'Panelboards', 'cctv': 'CCTV'}.get(family(row.get('name', '')), clean(row.get('material_category')) or 'Devices')


def supplier_rows(rows):
    grouped = {}
    for row in rows:
        identity = row.get('product_identity') or {}
        code = row.get('client_product_code') or row.get('material_code') or identity.get('code') or ''
        if not row.get('client_product_code') and re.fullmatch(r'.+-[0-9a-f]{16,64}',code,re.I):
            code = ''  # Internal deduplication hash, not a supplier item number.
        brand = row.get('client_product_brand') or row.get('brand') or identity.get('brand') or ''
        if not brand:
            prefix = code.partition('-')[0].upper()
            brand = prefix if prefix in {'PANASONIC', 'ALANTEK', 'BELDEN', 'COMMSCOPE', 'NICHI', 'AEC', 'VOLTPRO'} else ''
        name = clean(row.get('client_product_name') or row.get('material_name') or row.get('name'))
        spec = clean(row.get('client_product_specification') or row.get('name'))
        if spec == name:
            spec = ''
        key = (category(row), name, brand, code, spec, row['unit'], str(row.get('unit_price')), row.get('currency') or '')
        target = grouped.setdefault(key, dict(quantity=Decimal(0), total=Decimal(0), priced=True))
        target['quantity'] += Decimal(str(row['quantity']))
        if row.get('line_total') is None:
            target['priced'] = False
        else:
            target['total'] += Decimal(str(row['line_total']))
    rank={'Lighting layout':0,'Power layout':1,'Data layout':2}
    for key, value in sorted(grouped.items(), key=lambda x: (rank.get(x[0][0],3),x[0][0], x[0][1])):
        cat, name, brand, code, spec, unit, price, currency = key
        yield [cat, name, brand, code, spec, value['quantity'], unit,
            Decimal(price) if price != 'None' else '', currency,
            value['total'].quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if value['priced'] else '']


def supplier_csv(rows, totals):
    stream = StringIO(newline='')
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
    writer.writerow(['BILL OF MATERIALS'])
    writer.writerow(HEADERS)
    for row in supplier_rows(rows):
        writer.writerow([safe_cell(value) for value in row])
    for currency, total in sorted(totals.items()):
        writer.writerow(['', '', '', '', '', '', '', 'Total', currency,
            Decimal(str(total)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)])
    return '\ufeff' + stream.getvalue()


def assembly_price_csv(assemblies):
    """Current catalog quote presentation, not a project or historical estimate."""
    stream=StringIO(newline='')
    writer=csv.writer(stream,quoting=csv.QUOTE_ALL)
    writer.writerow(['Category','Product name','Brand','Item number','Specification','Unit','Unit price','Currency'])
    for row in sorted(assemblies,key=lambda a:(a['device_type'],a['name'])):
        writer.writerow([safe_cell(value) for value in [row['device_type'].replace('_',' '),clean(row['name']),
            row['brand'],row['code'],clean(row['specifications']),'piece',
            row['unit_price'] if row['unit_price'] is not None else '',row['currency'] or '']])
    return '\ufeff'+stream.getvalue()
