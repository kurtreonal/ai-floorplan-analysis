import pytest

from app.geometry.path_lengths import unique_polyline_length, unique_paths_length, unique_metric_edges


def points(*xy):
    return [dict(x=x, y=y) for x, y in xy]


@pytest.mark.parametrize('scale', [.1, 1, 10])
def test_unique_centerline_length_not_traversal_or_conductor_quantity(scale):
    path = points((0, 0), (10, 0), (5, 0), (5, 4), (5, 0), (15, 0))
    assert unique_polyline_length([{k: v*scale for k, v in p.items()} for p in path]) == pytest.approx(19*scale)


def test_crossing_and_parallel_spans_are_not_erased():
    assert unique_polyline_length(points((0, 0), (10, 0), (10, 1), (0, 1))) == 21
    assert unique_polyline_length(points((0, 0), (10, 10), (10, 0), (0, 10))) == pytest.approx(20*2**.5+10)


def test_diagonal_partial_overlap_and_closed_loop():
    assert unique_polyline_length(points((0, 0), (10, 10), (5, 5), (15, 15))) == pytest.approx(15*2**.5)
    assert unique_polyline_length(points((0, 0), (4, 0), (4, 3), (0, 3), (0, 0))) == 14
    assert unique_polyline_length(points((1, 1), (1, 1))) == 0


def test_nonfinite_coordinates_fail_explicitly():
    with pytest.raises(ValueError):
        unique_polyline_length(points((0, 0), (float('nan'), 0)))


def test_explicit_network_union_does_not_add_a_bridge_between_paths():
    assert unique_paths_length([points((0,0),(10,0)),points((5,0),(15,0))]) == 15
    assert unique_paths_length([points((0,0),(10,0)),points((100,0),(110,0))]) == 20


def test_metric_network_unions_shared_drops_but_keeps_levels_floors_and_crossings_separate():
    def edge(a,b,floor=2):
        return dict(start=dict(floor_id=floor,x=a[0],y=a[1],elevation_meters=a[2]),end=dict(floor_id=floor,x=b[0],y=b[1],elevation_meters=b[2]))
    edges=[edge((0,0,3),(10,0,3)),edge((5,0,3),(15,0,3)),
           edge((15,0,3),(15,0,1)),edge((15,0,2),(15,0,0))]
    assert unique_metric_edges(edges)==(15,3)
    assert unique_metric_edges(edges+[edge((0,0,4),(10,0,4)),edge((0,0,3),(10,0,3),floor=3)])==(35,3)
    assert unique_metric_edges([edge((0,0,3),(10,10,3)),edge((0,10,3),(10,0,3))])[0]==pytest.approx(20*2**.5)
    with pytest.raises(ValueError):unique_metric_edges([edge((0,0,3),(1,0,2))])
    crossing=edge((0,0,0),(0,0,3));crossing['end']['floor_id']=3
    with pytest.raises(ValueError):unique_metric_edges([crossing])
    crossing['connector_id']='reviewed-riser'
    assert unique_metric_edges([crossing])==(0,3)
