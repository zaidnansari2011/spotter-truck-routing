import pytest

from planner.domain.geo import (
    haversine_m,
    offset_point,
    overlap_fraction,
    point_at_fraction,
    simplify,
)


def straight(lat0, lon0, lat1, lon1, n=500):
    return [(lat0 + (lat1 - lat0) * i / (n - 1), lon0 + (lon1 - lon0) * i / (n - 1)) for i in range(n)]


def test_point_at_fraction_on_a_straight_line():
    line = straight(0, 0, 0, 2, n=3)

    assert point_at_fraction(line, 0.5) == pytest.approx((0, 1))
    assert point_at_fraction(line, 0.25) == pytest.approx((0, 0.5))
    assert point_at_fraction(line, 1.0) == pytest.approx((0, 2))


def test_point_at_fraction_handles_repeated_points():
    assert point_at_fraction([(0, 0), (0, 0), (0, 1)], 0.0) == (0, 0)


def test_offset_point_is_perpendicular_and_the_right_distance():
    start, end = (40.0, -100.0), (40.0, -95.0)  # heading east
    left = offset_point(start, end, (40.0, -97.5), 50_000, side=1)
    right = offset_point(start, end, (40.0, -97.5), 50_000, side=-1)

    assert left[0] > 40 > right[0]  # left of an eastbound line is north
    assert left[1] == pytest.approx(-97.5, abs=1e-9)
    assert haversine_m((40.0, -97.5), left) == pytest.approx(50_000, rel=1e-3)


def test_offset_point_needs_a_direction():
    with pytest.raises(ValueError):
        offset_point((1, 1), (1, 1), (1, 1), 1000, 1)


def test_overlap_of_a_route_with_itself_is_total():
    line = straight(40, -100, 40, -95)

    assert overlap_fraction(line, line) == 1.0


def test_parallel_roads_a_degree_apart_do_not_overlap():
    assert overlap_fraction(straight(40, -100, 40, -95), straight(41, -100, 41, -95)) == 0.0


def test_partial_overlap_is_measured_by_share_of_points():
    shared = straight(40, -100, 40, -97.5, n=250)
    route = shared + straight(40, -97.49, 40, -95, n=250)
    other = shared + straight(40.5, -97.49, 41, -95, n=250)

    assert overlap_fraction(route, other) == pytest.approx(0.5, abs=0.02)


def test_simplify_reduces_a_straight_line_to_its_endpoints():
    line = straight(40, -100, 40, -95, n=1000)

    assert simplify(line, 25) == [line[0], line[-1]]


def test_simplify_keeps_corners_and_respects_tolerance():
    corner = straight(40, -100, 41, -100, n=200) + straight(41, -99.99, 41, -99, n=200)

    result = simplify(corner, 25)

    assert result[0] == corner[0] and result[-1] == corner[-1]
    assert len(result) <= 4
    assert any(abs(lat - 41) < 1e-6 and abs(lon + 100) < 0.02 for lat, lon in result)


def test_simplify_never_strays_further_than_the_tolerance():
    wiggle = [(40 + 0.0001 * (i % 2), -100 + 0.001 * i) for i in range(500)]  # ~11 m zig-zag

    assert simplify(wiggle, 25) == [wiggle[0], wiggle[-1]]
    assert len(simplify(wiggle, 5)) > 400


@pytest.mark.parametrize("points", [[], [(0, 0)], [(0, 0), (1, 1)]])
def test_simplify_short_inputs_unchanged(points):
    assert simplify(points, 10) == points


def test_simplify_handles_a_repeated_start_point():
    points = [(0, 0), (0.5, 0.5), (0.0, 0.0)]  # loop back to the start

    assert simplify(points, 10) == points


def test_haversine_symmetry():
    a, b = (40.0, -100.0), (41.0, -95.0)

    assert haversine_m(a, b) == pytest.approx(haversine_m(b, a))


def test_point_at_fraction_past_the_end_returns_the_last_point():
    line = straight(0, 0, 0, 2, n=3)

    assert point_at_fraction(line, 1.2) == (0, 2)
