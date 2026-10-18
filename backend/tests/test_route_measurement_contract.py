from dataclasses import asdict
import json
import math

import pytest
from pydantic import ValidationError

from app.geometry.calibration import known_dimension_scale, transformed_scale
from app.geometry.route_measurement import measure_metric_network
from app.schemas.analysis_settings import ScaleInput


def edge(a, b, **extra):
    def point(p):
        return dict(floor_id=1, x=p[0], y=p[1], elevation_meters=p[2])
    return dict(start=point(a), end=point(b), **extra)


def test_known_lengths_branches_and_one_explicit_drop():
    edges = [edge((0,0,3),(3,0,3)), edge((3,0,3),(3,4,3)),
             edge((3,0,3),(3,0,1))]
    result = measure_metric_network(edges)
    assert (result.horizontal_meters,result.vertical_meters,result.physical_meters) == (7,2,9)
    assert measure_metric_network(json.loads(json.dumps(edges))) == result
    # A split edge and a reversed duplicate represent the SAME physical network.
    split = [edge((0,0,3),(1,0,3)),edge((1,0,3),(3,0,3)),
             edge((3,0,3),(0,0,3)),*edges[1:]]
    assert measure_metric_network(split) == result


def test_overlapping_but_distinct_conduits_and_crossings_are_not_merged():
    one = edge((0,0,3),(3,0,3),physical_path_id='conduit-a')
    two = {**one,'physical_path_id':'conduit-b'}
    assert measure_metric_network([one,two]).physical_meters == 6
    crossing = edge((1,-1,3),(1,1,3),physical_path_id='conduit-c')
    assert measure_metric_network([one,two,crossing]).physical_meters == 8


def test_actual_3d_slope_is_not_full_plan_length_plus_full_space_length():
    span = edge((0,0,0),(3,0,4),slope_supported=True)
    result = measure_metric_network([span])
    assert asdict(result) == dict(horizontal_meters=3,vertical_meters=4,physical_meters=5,
                                 measurement_revision='canonical_centerline_3d_v1')
    assert measure_metric_network([edge((0,0,0),(1.5,0,2),slope_supported=True),
                                  edge((1.5,0,2),(3,0,4),slope_supported=True)]) == result
    with pytest.raises(ValueError,match='explicit support'):
        measure_metric_network([edge((0,0,0),(3,0,4))])


def test_saved_canonical_slope_uses_the_same_backend_measurement():
    from app.geometry.canonical import canonical_geometry_from_dict
    from app.geometry.canonical_takeoff import canonical_path_rows
    from tests.test_canonical_junction_contract import fixture
    base, _ = fixture()
    raw = base.to_dict()
    raw['routes'] = [dict(id=1, points=[
        dict(project_floor_id=2,x=1,y=2,elevation_meters=3),
        dict(project_floor_id=2,x=4,y=2,elevation_meters=7)])]
    reloaded=canonical_geometry_from_dict(json.loads(json.dumps(raw)))
    row=canonical_path_rows(reloaded)[0]
    assert float(row['quantity'])==5
    assert row['horizontal_meters']==3 and row['vertical_meters']==4
    assert not row['missing_vertical_inputs']


def test_interfloor_connector_and_finite_numeric_guards():
    riser = edge((0,0,3),(0,0,6),connector_id='riser-1')
    riser['end']['floor_id']=2
    assert measure_metric_network([riser]).physical_meters==3
    with pytest.raises(ValueError,match='connector'):
        measure_metric_network([{k:v for k,v in riser.items() if k!='connector_id'}])
    for value in [math.inf, math.nan, True, '3']:
        bad=edge((0,0,3),(1,0,3));bad['end']['x']=value
        with pytest.raises(ValueError): measure_metric_network([bad])


def test_known_dimension_uses_existing_append_only_approval_fields():
    payload=dict(pixels_per_meter=None,reference_width_pixels=1000,reference_height_pixels=500,
                 known_dimension=dict(pixel_length=500,real_length_meters=5),evidence_notes='Surveyed wall span')
    approved=ScaleInput.model_validate(payload)
    assert approved.pixels_per_meter == 100
    stored=approved.model_dump()
    assert 'known_dimension' not in stored  # Existing DB columns, no schema reset.
    assert stored['evidence_notes']=='Known dimension: 500 source pixels = 5 metres. Surveyed wall span'
    assert ScaleInput.model_validate(json.loads(json.dumps(stored))).pixels_per_meter==100
    for changes in [dict(pixels_per_meter=20),dict(reference_width_pixels=None),
                    dict(known_dimension=dict(pixel_length=2000,real_length_meters=5)),
                    dict(known_dimension=dict(pixel_length=True,real_length_meters=5))]:
        with pytest.raises(ValidationError): ScaleInput.model_validate({**payload,**changes})


def test_calibration_transform_preserves_crop_rotation_and_uniform_resize():
    ppm=known_dimension_scale(500,5)
    # Rotated/cropped half-resolution view: local->reference pixels.
    transform=dict(a=0,b=2,c=-2,d=0,e=900,f=30)
    assert transformed_scale(ppm,transform)==50
    assert transformed_scale(ppm,dict(a=1,b=0,c=0,d=1,e=40,f=50))==100
    with pytest.raises(ValueError,match='aspect-preserving'):
        transformed_scale(ppm,dict(a=2,b=0,c=0,d=1,e=0,f=0))
