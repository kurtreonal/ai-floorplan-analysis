from copy import deepcopy
from app.geometry import canonical_geometry_from_dict
from app.routing.network_measurements import circuit_network_takeoff
from app.routing.missing_devices import plan_missing_devices
from tests.test_missing_devices import inputs, observed_network


def overlapping_source_case():
    from app.geometry.canonical_extension import canonical_extension_from_dict
    from app.routing.circuit import CircuitPlanningResult, ObservedRouteAssignment
    from tests.test_canonical_junction_contract import fixture
    document, extension = fixture()
    raw=document.to_dict()
    raw['routes'][1]['points'][1]=deepcopy(raw['routes'][0]['points'][0])
    document=canonical_geometry_from_dict(raw)
    extension=canonical_extension_from_dict(extension,document)
    _, request=inputs()
    request=request.model_copy(update={'circuit_id':'C1','observed_route_assignments':[
        ObservedRouteAssignment(floor_id=2,route_id=i)
        for i in (1,2)]})
    planned=CircuitPlanningResult(circuit_id='C1',installation_method='ceiling_service',
        segments=[],branches=[],horizontal_meters=0,vertical_meters=0,total_meters=0)
    return document,extension,request,planned


def test_circuit_preview_and_canonical_takeoff_agree_on_explicit_shared_spans():
    from app.geometry.canonical_takeoff import canonical_path_rows
    document,extension,request,planned=overlapping_source_case()
    expected=float(canonical_path_rows(document,extension)[0]['quantity'])
    measured=circuit_network_takeoff(request,planned,{2:document},extensions={2:extension}).planning_takeoff
    assert measured.observed_meters==expected==1


def test_same_circuit_and_geometry_without_topology_remain_distinct_runs():
    document,_,request,planned=overlapping_source_case()
    measured=circuit_network_takeoff(request,planned,{2:document}).planning_takeoff
    assert measured.observed_meters==2
    assert len(document.routes)==2


def test_conductor_count_and_saved_source_geometry_survive_shared_span_measurement():
    document,extension,request,planned=overlapping_source_case()
    before=deepcopy(document.to_dict())
    measured=circuit_network_takeoff(request.model_copy(update={'conductor_count':3}),
        planned,{2:document},extensions={2:extension}).planning_takeoff
    assert measured.conduit_meters==1 and measured.total_conductor_meters==3
    assert document.to_dict()==before


def test_selected_network_keeps_route_per_conductor_and_total_quantities_separate():
    raw,request=inputs();request,extension=observed_network(raw,request)
    documents={2:canonical_geometry_from_dict(raw)}
    planned=plan_missing_devices(request,documents,{2:extension},None,{'2':5})
    before=deepcopy(planned.model_dump())
    measured=circuit_network_takeoff(request,planned,documents).planning_takeoff
    assert measured.observed_meters==3 and measured.generated_meters==1 and measured.conduit_meters==4
    assert measured.one_conductor_meters is None and measured.total_conductor_meters is None
    configured=request.model_copy(update={'conductor_count':3})
    measured=circuit_network_takeoff(configured,planned,documents).planning_takeoff
    assert measured.one_conductor_meters==4 and measured.total_conductor_meters==12
    assert planned.model_dump()==before


def test_configured_vertical_branches_contribute_to_physical_and_conductor_length_once():
    from app.routing.circuit import CircuitPlanningResult, CircuitBranch
    from app.routing.contracts import Point
    from app.routing.engine import segment
    raw,request=inputs();documents={2:canonical_geometry_from_dict(raw)}
    a=Point(floor_id=2,x=1,y=1,elevation_meters=3)
    b=a.model_copy(update={'x':3});c=b.model_copy(update={'elevation_meters':1.2})
    segments=[segment(a,b,'ceiling_service'),segment(b,c,'wall_drop')]
    result=CircuitPlanningResult(circuit_id='C-1',installation_method='ceiling_service',segments=segments,
        branches=[CircuitBranch(floor_id=2,symbol_id='detected:501',points=[a,b,c],segment_indices=[0,1],horizontal_meters=2,vertical_meters=1.8,total_meters=3.8)],
        horizontal_meters=2,vertical_meters=1.8,total_meters=3.8)
    measured=circuit_network_takeoff(request.model_copy(update={'conductor_count':2}),result,documents).planning_takeoff
    assert measured.conduit_meters==3.8 and measured.total_conductor_meters==7.6
