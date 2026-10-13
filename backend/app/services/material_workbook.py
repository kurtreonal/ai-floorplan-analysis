"""Bounded XLSX price extraction. Never execute formulas or follow workbook links."""
from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

MAX_FILE = 5 * 1024 * 1024
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


class WorkbookError(ValueError):
    pass


def _xml(archive, path):
    data = archive.read(path)
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise WorkbookError('XML declarations are not supported.')
    return ET.fromstring(data)


def _header(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def extract_prices(data):
    if not data or len(data) > MAX_FILE:
        raise WorkbookError('Choose an XLSX file up to 5 MB.')
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if (len(infos) > 256 or len({i.filename for i in infos}) != len(infos)
                    or sum(i.file_size for i in infos) > 30_000_000
                    or any(i.file_size > 8_000_000 or i.flag_bits & 1 for i in infos)
                    or any('vbaproject' in i.filename.lower() for i in infos)):
                raise WorkbookError('Workbook exceeds safe limits or contains macros.')
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(item.itertext()) for item in _xml(archive, 'xl/sharedStrings.xml')]
            relationships = {r.attrib['Id']: r.attrib.get('Target', '')
                for r in _xml(archive, 'xl/_rels/workbook.xml.rels')
                if r.attrib.get('TargetMode') != 'External'}
            rows, issues = [], []
            for sheet in _xml(archive, 'xl/workbook.xml').find(NS + 'sheets'):
                name = sheet.attrib['name']
                target = relationships.get(sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'))
                path = posixpath.normpath(target.lstrip('/') if target and target.startswith('/') else 'xl/' + (target or ''))
                if not path.startswith('xl/worksheets/') or path not in archive.namelist():
                    raise WorkbookError('Unsupported worksheet relationship.')
                root = _xml(archive, path)
                headings, section = None, name
                for row in root.findall(f'{NS}sheetData/{NS}row'):
                    cells, formulas = {}, set()
                    number = int(row.attrib['r'])
                    if number > 10000:
                        raise WorkbookError('Worksheets are limited to 10,000 rows.')
                    for cell in row:
                        ref = cell.attrib.get('r', '')
                        column = re.sub(r'\d', '', ref)
                        if not re.fullmatch(r'[A-Z]{1,2}', column):
                            raise WorkbookError('Unsupported cell address.')
                        if cell.find(NS + 'f') is not None:
                            formulas.add(column)
                        value = cell.findtext(NS + 'v', '')
                        if cell.attrib.get('t') == 's':
                            value = strings[int(value)]
                        elif cell.attrib.get('t') == 'inlineStr':
                            value = ''.join(cell.find(NS + 'is').itertext())
                        cells[column] = value.strip()
                    if headings is None:
                        normalized = {_header(v): k for k, v in cells.items()}
                        if 'description' in normalized and 'sellingprice' in normalized and 'unit' in normalized:
                            headings = {'name': normalized['description'], 'price': normalized['sellingprice'],
                                'unit': normalized['unit'], 'code': normalized.get('itemnumber')}
                        elif all(k in normalized for k in ('code', 'name', 'unit', 'unitprice')):
                            headings = {'name': normalized['name'], 'price': normalized['unitprice'],
                                'unit': normalized['unit'], 'code': normalized['code'],
                                'category': normalized.get('category')}
                        continue
                    description = cells.get(headings['name'], '')
                    price, unit = cells.get(headings['price'], ''), cells.get(headings['unit'], '')
                    if not description:
                        continue
                    if not price and not unit:
                        section = description[:100]
                        continue
                    identity = f'{name}:{number}'
                    if unit.upper() == 'SHEET TOTAL':
                        continue
                    try:
                        if re.search(r'price\s+basis.*(?:not\s+stated|unclear|unknown)', description, re.I):
                            raise ValueError('Source price basis is unresolved; clarify the purchase unit before importing.')
                        if headings['price'] in formulas:
                            raise ValueError('Formula prices are not evaluated; supply a numeric price.')
                        amount = Decimal(price.replace(',', ''))
                        if not amount.is_finite() or amount < 0 or amount >= Decimal('1e12') or amount.as_tuple().exponent < -4:
                            raise ValueError('Price must be nonnegative, with up to four decimals.')
                        if not unit or len(unit) > 32 or len(description) > 255 or '\x00' in description:
                            raise ValueError('A bounded description and purchase unit are required.')
                        unit = {'m': 'meter', 'meters': 'meter', 'metre': 'meter', 'metres': 'meter',
                            'pcs': 'piece', 'pieces': 'piece', 'pc': 'piece', 'units': 'unit'}.get(unit.lower(), unit.lower())
                        sku = cells.get(headings.get('code'), '')
                        if 'category' in headings:
                            code = sku
                            category = cells.get(headings['category'], '') or name
                        else:
                            prefix = re.sub(r'[^A-Z0-9]+', '-', name.upper()).strip('-')[:18]
                            suffix = re.sub(r'[^A-Z0-9._-]+', '-', sku.upper()).strip('-') if sku else ''
                            code = f'{prefix}-{suffix}' if suffix else f'{prefix}-{sha256(description.casefold().encode()).hexdigest()[:16]}'
                            if len(code) > 64:
                                code = code[:47] + '-' + sha256(code.encode()).hexdigest()[:16]
                            category = section
                        if not code or len(code) > 64 or '\x00' in code or len(category) > 100:
                            raise ValueError('Invalid code or category.')
                        rows.append(dict(row_id=identity, sheet=name, row=number, code=code, name=description,
                            unit=unit, category=category, unit_price=str(amount)))
                    except (InvalidOperation, ValueError) as error:
                        issues.append(dict(row_id=identity, reason=str(error) if not isinstance(error, InvalidOperation)
                            else 'No numeric price (for example TBA); skipped.'))
                    if len(rows) + len(issues) > 5000:
                        raise WorkbookError('Import is limited to 5,000 items.')
            duplicates = {code for code, count in Counter(r['code'] for r in rows).items() if count > 1}
            accepted = []
            for row in rows:
                if row['code'] in duplicates:
                    issues.append(dict(row_id=row['row_id'], reason='Duplicate material code; resolve in source workbook.'))
                else:
                    accepted.append(row)
            if not rows and not issues:
                raise WorkbookError('No supported price table. Use Code, Name, Unit, Unit price, Category, or the supplied brand format.')
            return dict(file_sha256=sha256(data).hexdigest(), rows=accepted, issues=issues)
    except WorkbookError:
        raise
    except (BadZipFile, KeyError, IndexError, ET.ParseError, TypeError, OverflowError, ValueError, UnicodeDecodeError) as error:
        raise WorkbookError('Invalid or unsupported XLSX workbook.') from error
