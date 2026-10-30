"""Dependency-free XLSX rendering of authoritative, captured BOM values.

CSV remains available for integrations. This writer only formats values; it
does not recalculate quantities, purchase units or historical prices.
"""
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
from app.services.bom_export import HEADERS, supplier_rows

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def cell(address, value, style=0):
    if value is None or value == '':
        return f'<c r="{address}" s="{style}"/>'
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{address}" s="{style}"><v>{value}</v></c>'
    # Inline strings cannot execute formulas, even for supplier SKUs beginning =.
    text = ''.join(c for c in str(value or '') if ord(c) >= 32 or c in '\t\n\r')
    return f'<c r="{address}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def supplier_xlsx(rows, totals):
    data = list(supplier_rows(rows))
    sheet_rows = [f'<row r="1" ht="34" customHeight="1">{cell("A1", "VED Electrical Services", 1)}</row>',
        f'<row r="2" ht="25" customHeight="1">{cell("A2", "Bill of materials", 2)}</row>',
        '<row r="4" ht="30" customHeight="1">' + ''.join(cell(f'{chr(65+i)}4', v, 3) for i, v in enumerate(HEADERS)) + '</row>']
    for number, row in enumerate(data, 5):
        # Supplier descriptions and specifications wrap at a readable font size.
        lines = max(1, *((len(str(row[i])) + width-1)//width for i,width in enumerate([17,44,18,23,44])))
        height = min(160, max(34, lines*15+10))
        values = ''.join(cell(f'{chr(65+i)}{number}', v,
            (6 if i in (7,9) else 5 if i == 5 else 4) if number % 2 else
            (9 if i in (7,9) else 8 if i == 5 else 7)) for i,v in enumerate(row))
        sheet_rows.append(f'<row r="{number}" ht="{height}" customHeight="1">{values}</row>')
    for number, (currency, total) in enumerate(sorted(totals.items()), len(data)+6):
        sheet_rows.append(f'<row r="{number}" ht="30" customHeight="1">' +
            ''.join(cell(f'{chr(65+i)}{number}', 'Total' if i == 7 else currency if i == 8 else Decimal(str(total)) if i == 9 else '', 11 if i == 9 else 10) for i in range(10)) + '</row>')
    columns = ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i,width in enumerate([18,46,19,24,46,13,12,17,11,19],1))
    worksheet = (f'<worksheet xmlns="{NS}"><sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<sheetFormatPr defaultRowHeight="22"/><cols>{columns}</cols><sheetData>{"".join(sheet_rows)}</sheetData>'
        f'<autoFilter ref="A4:J{max(4,len(data)+4)}"/><mergeCells count="2"><mergeCell ref="A1:J1"/><mergeCell ref="A2:J2"/></mergeCells>'
        '<printOptions horizontalCentered="1"/><pageMargins left="0.25" right="0.25" top="0.4" bottom="0.4" header="0.2" footer="0.2"/>'
        '<pageSetup paperSize="8" orientation="landscape" fitToWidth="1" fitToHeight="0"/></worksheet>')
    xfs = ['<xf fontId="0" fillId="0" borderId="0" numFmtId="0"/>']
    for font, fill, fmt in [(1,2,0),(2,0,0),(3,3,0),(0,0,0),(0,0,164),(0,0,165),(0,4,0),(0,4,164),(0,4,165),(2,3,0),(2,3,165)]:
        xfs.append(f'<xf fontId="{font}" fillId="{fill}" borderId="1" numFmtId="{fmt}" applyAlignment="1" applyFill="1" applyFont="1" applyNumberFormat="1"><alignment vertical="center" wrapText="1" horizontal="{"right" if fmt else "left"}"/></xf>')
    styles = f'''<styleSheet xmlns="{NS}"><numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0.####"/><numFmt numFmtId="165" formatCode="#,##0.00"/></numFmts>
      <fonts count="4"><font><sz val="11"/><name val="Calibri"/><color rgb="FF25363A"/></font><font><b/><sz val="18"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font><font><b/><sz val="12"/><name val="Calibri"/><color rgb="FF25363A"/></font><font><b/><sz val="11"/><name val="Calibri"/><color rgb="FF25363A"/></font></fonts>
      <fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF263B3A"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFE8CF"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF5F7F6"/></patternFill></fill></fills>
      <borders count="2"><border/><border><bottom style="hair"><color rgb="FFD9DFDC"/></bottom></border></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="12">{''.join(xfs)}</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' + ''.join(f'<Override PartName="/{p}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.{t}+xml"/>' for p,t in [('xl/workbook.xml','sheet.main'),('xl/worksheets/sheet1.xml','worksheet'),('xl/styles.xml','styles')]) + '</Types>'
    rel_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    rel_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    stream = BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for path, text in {'[Content_Types].xml':types,
            '_rels/.rels':f'<Relationships xmlns="{rel_ns}"><Relationship Id="rId1" Type="{rel_type}officeDocument" Target="xl/workbook.xml"/></Relationships>',
            'xl/workbook.xml':f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Bill of materials" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm.Print_Titles" localSheetId="0">\'Bill of materials\'!$1:$4</definedName></definedNames></workbook>',
            'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{rel_ns}"><Relationship Id="rId1" Type="{rel_type}worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{rel_type}styles" Target="styles.xml"/></Relationships>',
            'xl/styles.xml':styles, 'xl/worksheets/sheet1.xml':worksheet}.items():
            archive.writestr(path, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+text)
    return stream.getvalue()
