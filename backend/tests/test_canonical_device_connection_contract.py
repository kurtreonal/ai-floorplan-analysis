"""Independent v4 contract gate; does not depend on draft/renderer integration."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.geometry.canonical import canonical_geometry_from_dict, CanonicalGeometryError
from app.geometry.canonical_extension import canonical_extension_from_dict


def fixture():
    root = Path(__file__).resolve().parents[2] / 'fixtures'
    base = json.loads((root / 'canonical_geometry_v1.json').read_text())
    extension = json.loads((root / 'canonical_extension_v2.json').read_text())
    legacy = deepcopy(extension)
    extension['extension_schema_version'] = 4
    extension['symbol_details'][0]['installation'] = {'elevation_meters': 0, 'wall_id': None}
    point = base['routes'][0]['points'][-1]
    for detail in extension['route_details']:
        detail['device_connections'] = [dict(symbol_id=base['symbols'][0]['id'], point_index=1,
            anchor={key: point[key] for key in ('x', 'y', 'elevation_meters')})]
    return canonical_geometry_from_dict(base), extension, legacy


def test_old_snapshot_unchanged_and_explicit_device_anchor_round_trip():
    base, extension, legacy = fixture()
    assert canonical_extension_from_dict(legacy, base).to_dict() == legacy
    assert canonical_extension_from_dict(extension, base).to_dict() == extension


@pytest.mark.parametrize('case', ['symbol', 'index', 'coordinate', 'height', 'duplicate'])
def test_invalid_reference_or_anchor_rejected(case):
    base, extension, _ = fixture()
    contact = extension['route_details'][0]['device_connections'][0]
    if case == 'symbol': contact['symbol_id'] = 'detected:999999'
    elif case == 'index': contact['point_index'] = 999
    elif case == 'coordinate': contact['anchor']['x'] += .1
    elif case == 'height': contact['anchor']['elevation_meters'] += .1
    else: extension['route_details'][0]['device_connections'].append(deepcopy(contact))
    with pytest.raises(CanonicalGeometryError): canonical_extension_from_dict(extension, base)
