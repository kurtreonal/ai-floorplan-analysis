from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy import select
import pytest
from app.api.dependencies import get_current_user
from app.models import Material, MaterialPrice
from app.services.material_workbook import extract_prices, WorkbookError
from app.services.material_import_service import preview
from tests.test_routing_api import context


def workbook(rows):
    def cell(column, row, value):
        return f'<c r="{column}{row}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
    contents = ''.join(f'<row r="{n}">' + ''.join(cell(chr(65 + i), n, value) for i, value in enumerate(row)) + '</row>'
        for n, row in enumerate(rows, 1))
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Devices" sheetId="1" r:id="r1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{contents}</sheetData></worksheet>')
    return stream.getvalue()


def sample(code='WIRE-A', price='100'):
    return workbook([['Code', 'Name', 'Unit', 'Unit price', 'Category'], [code, 'Cable roll', 'roll', price, 'Wiring']])


def test_numeric_units_missing_prices_duplicate_and_preservation():
    data = sample()
    result = extract_prices(data)
    assert result['rows'][0]['unit'] == 'roll'
    assert result['rows'][0]['unit_price'] == '100'
    assert extract_prices(sample(price='0'))['rows'][0]['unit_price'] == '0'
    for price in ('TBA', '-1', 'NaN', '1.12345', '1000000000000'):
        assert not extract_prices(sample(price=price))['rows']
    duplicate = workbook([['Code', 'Name', 'Unit', 'Unit price'], ['X', 'Lamp', 'piece', 1], ['X', 'Lamp', 'piece', 2]])
    assert not extract_prices(duplicate)['rows']
    assert len(extract_prices(duplicate)['issues']) == 2
    assert data == sample()
    with pytest.raises(WorkbookError): extract_prices(b'not a zip')
    with pytest.raises(PermissionError): preview(None, SimpleNamespace(role=SimpleNamespace(name='DESIGNER')), data)


def test_brand_format_ignores_total_and_normalizes_meter():
    result = extract_prices(workbook([['ITEM NUMBER', 'DESCRIPTION', '', 'SELLING PRICE', '', 'QUANTITY', 'UNIT', 'TOTAL VALUE'],
        ['', 'Source notes 2020', '', '', '', '', 'SHEET TOTAL', '=SUM(H3:H5)'],
        ['', 'COPPER CABLE', '', '', '', '', '', ''],
        ['SKU1', 'Wire', '', 12.50, '', '', 'meters', '=D4*F4']]))
    assert len(result['rows']) == 1
    assert result['rows'][0]['unit'] == 'meter'
    assert result['rows'][0]['code'] == 'DEVICES-SKU1'


def test_unresolved_source_price_basis_is_not_a_purchase_unit_price():
    result = extract_prices(workbook([['Code', 'Name', 'Unit', 'Unit price'],
        ['H1', 'Hub [Price basis (per pc vs per pack) not stated in source]', 'pack', 32]]))
    assert result['rows'] == []
    assert 'unresolved' in result['issues'][0]['reason']


def test_role_preview_apply_history_noop_and_changed_file(context):
    client, _, _, session, _, app, _, admin = context
    url = '/api/admin/materials/import'
    data = sample(uuid4().hex)
    files = {'file': ('prices.xlsx', data, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    assert client.post(url + '/preview', files=files).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: admin
    response = client.post(url + '/preview', files=files)
    assert response.status_code == 200, response.text
    body = response.json()
    assert session.scalar(select(Material).where(Material.code == body['rows'][0]['code'])) is None
    import json
    selection = dict(file_sha256=body['file_sha256'], currency='PHP', expected_versions={body['rows'][0]['row_id']: 0}, confirmed=True)
    response = client.post(url + '/apply', files=files, data={'selection': json.dumps(selection)})
    assert response.status_code == 200, response.text
    assert response.json()['created'] == 1
    material = session.scalar(select(Material).where(Material.code == body['rows'][0]['code']))
    price = session.scalar(select(MaterialPrice).where(MaterialPrice.material_id == material.id))
    assert price.changed_by_user_id == admin.id and price.unit == 'roll'
    # Stale previews cannot overwrite another revision.
    assert client.post(url + '/apply', files=files, data={'selection': json.dumps(selection)}).status_code == 422
    selection['expected_versions'][body['rows'][0]['row_id']] = 1
    same = client.post(url + '/apply', files=files, data={'selection': json.dumps(selection)})
    assert same.json()['unchanged'] == 1
    changed = sample(material.code, '110')
    assert client.post(url + '/apply', files={'file': ('prices.xlsx', changed)}, data={'selection': json.dumps(selection)}).status_code == 422
    assert len(session.scalars(select(MaterialPrice).where(MaterialPrice.material_id == material.id)).all()) == 1
    app.dependency_overrides.pop(get_current_user)
    assert client.post(url + '/preview', files=files).status_code == 401


def test_import_rollback_when_one_selected_identity_conflicts(context):
    client, _, _, session, _, app, _, admin = context
    app.dependency_overrides[get_current_user] = lambda: admin
    code = 'A-' + uuid4().hex
    second = 'Z-' + uuid4().hex
    data = workbook([['Code', 'Name', 'Unit', 'Unit price'], [code, 'New item', 'piece', 10], [second, 'Existing item', 'meter', 20]])
    session.add(Material(code=second, name='Existing item', unit='piece', category='Test'))
    session.commit()
    result = client.post('/api/admin/materials/import/preview', files={'file': ('test.xlsx', data)}).json()
    assert result['rows'][1]['eligible'] is False
    import json
    selection = dict(file_sha256=result['file_sha256'], currency='PHP', expected_versions={row['row_id']: 0 for row in result['rows']}, confirmed=True)
    assert client.post('/api/admin/materials/import/apply', files={'file': ('test.xlsx', data)}, data={'selection': json.dumps(selection)}).status_code == 422
    assert session.scalar(select(Material).where(Material.code == code)) is None
