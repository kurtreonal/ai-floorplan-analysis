from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.geometry.canonical import canonical_geometry_from_dict, CanonicalGeometryError
from app.geometry.canonical_extension import canonical_extension_from_dict


def fixture():
    root=Path(__file__).resolve().parents[2]/'fixtures'
    raw=json.loads((root/'canonical_geometry_v1.json').read_text())
    ext=json.loads((root/'canonical_extension_v2_empty.json').read_text())
    anchor=dict(x=2,y=2,elevation_meters=3)
    raw['routes']=[dict(id=1,points=[dict(project_floor_id=2,x=1,y=2,elevation_meters=3),dict(project_floor_id=2,**anchor)]),
                   dict(id=2,points=[dict(project_floor_id=2,**anchor),dict(project_floor_id=2,x=2,y=3,elevation_meters=3)])]
    ext['extension_schema_version']=5
    ext['route_details']=[dict(route_id=i,route_kind='observed',provenance_ref='reviewed:test',circuit_id='C1',device_connections=[],
        junction_connections=[dict(junction_id='junction-0001',point_index=index,anchor=deepcopy(anchor))]) for i,index in [(1,1),(2,0)]]
    return canonical_geometry_from_dict(raw),ext


def test_explicit_v5_junction_roundtrip_does_not_change_base_or_legacy():
    base,ext=fixture();before=deepcopy(ext)
    assert canonical_extension_from_dict(ext,base).to_dict()==ext
    assert ext==before
    old=deepcopy(ext);old['extension_schema_version']=4
    for row in old['route_details']:
        row.pop('junction_connections');row.pop('circuit_id')
    assert canonical_extension_from_dict(old,base).to_dict()==old


@pytest.mark.parametrize('case',['orphan','position','height','index','circuit','identity'])
def test_invalid_canonical_junction_is_rejected(case):
    base,ext=fixture();row=ext['route_details'][1];contact=row['junction_connections'][0]
    if case=='orphan':row['junction_connections']=[]
    elif case=='position':contact['anchor']['x']+=.01
    elif case=='height':contact['anchor']['elevation_meters']+=.01
    elif case=='index':contact['point_index']=99
    elif case=='circuit':row['circuit_id']='C2'
    else:contact['junction_id']='not-an-id'
    with pytest.raises(CanonicalGeometryError):canonical_extension_from_dict(ext,base)
