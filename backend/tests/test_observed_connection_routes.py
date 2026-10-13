from copy import deepcopy
import pytest
from app.geometry.observed_connections import observed_connection_routes


def test_inline_and_shared_connections_have_one_measured_drop_and_stable_symbol_anchor():
    symbols={'symbol-0001':dict(id='symbol-0001',mounting_height_meters=1.2)}
    wire=dict(id='segment-0001',disposition='accepted',source_evidence_required=True,elevation_meters=8.8,
        points=[dict(x=0,y=10),dict(x=20,y=10),dict(x=50,y=10)],
        device_attachments=[dict(symbol_id='symbol-0001',point_index=1)])
    before=deepcopy(wire)
    routes,details,version=observed_connection_routes([wire,{**wire,'id':'segment-0002'}],symbols,{'symbol-0001':'d:1'},
        floor_id=2,floor_elevation=6,scale=10,provenance='test')
    assert version and len(routes)==3
    assert len(routes[0]['points'])==3
    drops=[r for r in routes if len(r['points'])==2]
    assert len(drops)==1
    assert abs(drops[0]['points'][0]['elevation_meters']-drops[0]['points'][1]['elevation_meters'])==pytest.approx(1.6)
    assert details[0]['device_connections'][0]==dict(symbol_id='d:1',point_index=1,
        anchor=dict(x=2,y=1,elevation_meters=7.2))
    assert wire==before
