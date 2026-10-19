"""Bounded source cells for explicit column mapping; never evaluate a workbook."""
import csv
from io import BytesIO, StringIO
from pathlib import PurePosixPath
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile
from app.services.material_workbook import MAX_FILE, NS, WorkbookError, _xml, validate_archive

MAX_ROWS = 1000


def filename(value):
    # A display name only; source bytes live in the database, never at this path.
    name = PurePosixPath((value or '').replace('\\', '/')).name
    if not name or len(name) > 255 or any(ord(char) < 32 for char in name):
        raise WorkbookError('Choose a bounded XLSX or CSV filename.')
    return name


def _column(index):
    value = ''
    while index:
        index, tail = divmod(index - 1, 26)
        value = chr(65 + tail) + value
    return value


def read_cells(data, name):
    if not data or len(data) > MAX_FILE:
        raise WorkbookError('Choose an XLSX or UTF-8 comma-separated CSV file up to 5 MB.')
    name = filename(name)
    try:
        if name.lower().endswith('.csv'):
            rows = []
            for number, values in enumerate(csv.reader(StringIO(data.decode('utf-8-sig')), strict=True), 1):
                if number > 10000 or len(values) > 100 or any(len(value) > 2000 or '\x00' in value for value in values):
                    raise WorkbookError('CSV exceeds the row, column or cell limits.')
                if not any(value.strip() for value in values):
                    continue
                cells = {_column(index): value.strip() for index, value in enumerate(values, 1)}
                formulas = [key for key, value in cells.items() if value.startswith(('=', '+', '@'))]
                rows.append(dict(row=number, cells=cells, formulas=formulas))
                if len(rows) > MAX_ROWS + 20:
                    raise WorkbookError('Import is limited to 1,000 data rows plus headers.')
            return {'CSV': rows}
        if not name.lower().endswith('.xlsx'):
            raise WorkbookError('Only XLSX and UTF-8 comma-separated CSV are supported.')
        with ZipFile(BytesIO(data)) as archive:
            validate_archive(archive)
            if any('externallinks/' in path.lower() for path in archive.namelist()):
                raise WorkbookError('External workbook links are not supported.')
            relationships = {}
            for relation in _xml(archive, 'xl/_rels/workbook.xml.rels'):
                if relation.attrib.get('TargetMode') == 'External':
                    raise WorkbookError('External workbook links are not supported.')
                relationships[relation.attrib['Id']] = relation.attrib.get('Target', '')
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                strings = [''.join(item.itertext()) for item in _xml(archive, 'xl/sharedStrings.xml')]
            sheets = {}
            for sheet in _xml(archive, 'xl/workbook.xml').find(NS + 'sheets'):
                label = sheet.attrib['name']
                if not label or len(label) > 100 or label in sheets:
                    raise WorkbookError('Invalid or duplicate worksheet name.')
                target = relationships.get(sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'), '')
                path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
                if not path.startswith('xl/worksheets/') or path not in archive.namelist():
                    raise WorkbookError('Unsupported worksheet relationship.')
                rows, seen = [], set()
                for row in _xml(archive, path).findall(f'{NS}sheetData/{NS}row'):
                    number = int(row.attrib['r'])
                    if number < 1 or number > 10000 or number in seen:
                        raise WorkbookError('Invalid or duplicate source row.')
                    seen.add(number)
                    cells, formulas = {}, []
                    for cell in row:
                        match = re.fullmatch(r'([A-Z]{1,2})([1-9]\d*)', cell.attrib.get('r', ''))
                        if not match or int(match[2]) != number or match[1] in cells:
                            raise WorkbookError('Invalid or duplicate cell address.')
                        column = match[1]
                        value = cell.findtext(NS + 'v', '')
                        if cell.attrib.get('t') == 's':
                            index = int(value)
                            if index < 0:
                                raise WorkbookError('Invalid shared string.')
                            value = strings[index]
                        elif cell.attrib.get('t') == 'inlineStr':
                            inline = cell.find(NS + 'is')
                            value = ''.join(inline.itertext()) if inline is not None else ''
                        if cell.find(NS + 'f') is not None:
                            formulas.append(column)
                        if len(value) > 2000 or '\x00' in value:
                            raise WorkbookError('Source cell exceeds safe limits.')
                        cells[column] = value.strip()
                    if any(cells.values()) or formulas:
                        rows.append(dict(row=number, cells=cells, formulas=formulas))
                    if len(rows) > MAX_ROWS + 20:
                        raise WorkbookError('Import is limited to 1,000 data rows plus headers.')
                sheets[label] = sorted(rows, key=lambda row: row['row'])
            if not sheets:
                raise WorkbookError('No worksheets found.')
            return sheets
    except WorkbookError:
        raise
    except (BadZipFile, KeyError, IndexError, ET.ParseError, TypeError, OverflowError, ValueError, UnicodeError, csv.Error) as error:
        raise WorkbookError('Invalid or unsupported spreadsheet.') from error
