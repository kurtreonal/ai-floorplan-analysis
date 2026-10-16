import pytest

from app.geometry.path_lengths import unique_polyline_length


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
