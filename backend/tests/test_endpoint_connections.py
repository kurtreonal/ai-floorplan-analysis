from copy import deepcopy
from types import SimpleNamespace as NS
import pytest

from app.routing.endpoint_connections import connect_touching_endpoints


def source(items=None):
    return NS(payload=NS(symbols=NS(items=items or [NS(id='symbol-0001',
        center=NS(x=20, y=20, model_dump=lambda:dict(x=20,y=20)), bounds=NS(x=10, y=10, width=20, height=20),
        training_legend=None, observed_label='Wall switch')])))


def document():
    return dict(symbols=[dict(id='symbol-0001', center=dict(x=20, y=20))],
        observed_wiring=[dict(id='segment-0001', points=[dict(x=29, y=20), dict(x=80, y=20)])])


def test_touching_contact_is_immutable_idempotent_and_serializable():
    value=document(); original=deepcopy(value)
    result=connect_touching_endpoints(source(), value)
    assert result['observed_wiring'][0]['points'][0] == dict(x=20,y=20)
    assert result['observed_wiring'][0]['device_attachments'] == [dict(symbol_id='symbol-0001',point_index=0)]
    assert connect_touching_endpoints(source(), result) == result
    assert value == original


def test_no_crossing_grid_tip_ambiguous_or_disabled_contact():
    for points in [[dict(x=29,y=29),dict(x=80,y=29)],
                   [dict(x=0,y=20),dict(x=20,y=20),dict(x=80,y=20)]]:
        value=document(); value['observed_wiring'][0]['points']=points
        assert not connect_touching_endpoints(source(),value)['observed_wiring'][0].get('device_attachments')
    value=document(); value['observed_wiring'][0]['auto_connect_disabled_endpoints']=[0]
    assert connect_touching_endpoints(source(),value)==value
    second=deepcopy(source().payload.symbols.items[0]); second.id='symbol-0002'
    assert not connect_touching_endpoints(source([source().payload.symbols.items[0],second]),document())['observed_wiring'][0].get('device_attachments')


def test_moved_bounds_follow_device_and_approved_history_is_not_rewritten():
    value=document(); value['symbols'][0]['center']=dict(x=50,y=20)
    value['observed_wiring'][0]['points'][0]=dict(x=59,y=20)
    result=connect_touching_endpoints(source(),value)
    assert result['observed_wiring'][0]['points'][0]==dict(x=50,y=20)
    value['approved_for_layout']=True
    assert connect_touching_endpoints(source(),value)==value


def test_multiple_contacting_runs_keep_identity_but_known_circuit_conflicts_do_not_join():
    value=document()
    value['observed_wiring'].append(dict(id='segment-0002',points=[dict(x=0,y=20),dict(x=11,y=20)]))
    result=connect_touching_endpoints(source(),value)
    assert all(len(w['device_attachments'])==1 for w in result['observed_wiring'])
    for index,wire in enumerate(value['observed_wiring']): wire['circuit_id']=index+1
    result=connect_touching_endpoints(source(),value)
    assert not result['observed_wiring'][1].get('device_attachments')


@pytest.mark.parametrize('revision',['7','8','9','10','99','future'])
def test_new_source_versions_cannot_fall_back_to_proximity_during_review_conversion(revision):
    candidate=source();value=document();original=deepcopy(value)
    points=[NS(x=p['x'],y=p['y'],model_dump=lambda p=p:dict(p))
            for p in value['observed_wiring'][0]['points']]
    candidate.payload.observed_routes=NS(connections=[],segments=[NS(id='segment-0001',points=points)])
    candidate.provenance=NS(inference_parameters=[NS(name='wiring-evidence-version',
        value='raw-source-device-port-evidence-v'+revision)])
    result=connect_touching_endpoints(candidate,value)
    assert result['observed_wiring'][0]['source_evidence_required'] is True
    assert not result['observed_wiring'][0].get('device_attachments')
    assert result['observed_wiring'][0]['points']==original['observed_wiring'][0]['points']
    assert value==original
