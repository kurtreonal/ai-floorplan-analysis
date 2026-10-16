from copy import deepcopy
import pytest
from app.geometry.wire_network import wire_networks
from app.schemas.demo_interpretation import DemoObservedWiringReview


def paths():
    return [dict(id='segment-0001',disposition='corrected',points=[dict(x=0,y=20),dict(x=50,y=20),dict(x=100,y=20)],
        junction_attachments=[dict(junction_id='junction-0001',point_index=1)]),
        dict(id='segment-0002',disposition='corrected',points=[dict(x=50,y=20),dict(x=50,y=100)],
        junction_attachments=[dict(junction_id='junction-0001',point_index=0)])]


def test_explicit_topology_not_crossing_or_proximity_and_legacy_serialization():
    wires=paths();before=deepcopy(wires)
    assert len(set(wire_networks(wires).values()))==1
    assert wires==before
    for wire in wires:wire.pop('junction_attachments')
    assert len(set(wire_networks(wires).values()))==2
    old=dict(id='segment-0001',disposition='unresolved',points=[dict(x=0,y=0),dict(x=10,y=0)],completeness='partial')
    result=DemoObservedWiringReview.model_validate(old).model_dump()
    assert 'junction_attachments' not in result and 'circuit_id' not in result


@pytest.mark.parametrize('case',['position','height','circuit','installation','orphan','index'])
def test_invalid_network_rejected(case):
    wires=paths()
    if case=='position':wires[1]['points'][0]['x']+=1
    elif case=='height':wires[1]['elevation_meters']=3
    elif case=='circuit':wires[1]['circuit_id']='C2'
    elif case=='installation':wires[1]['installation_method']='concealed_under_floor'
    elif case=='orphan':wires[1]['disposition']='rejected'
    else:wires[1]['junction_attachments'][0]['point_index']=99
    with pytest.raises(ValueError):wire_networks(wires)
