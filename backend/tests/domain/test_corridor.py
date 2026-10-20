import pytest

from planner.domain.corridor import CORRIDOR_BUFFER_M, corridor_grid, densify
from planner.domain.geo import haversine_m


def straight(lat0, lon0, lat1, lon1, n=50):
    return [(lat0 + (lat1 - lat0) * i / (n - 1), lon0 + (lon1 - lon0) * i / (n - 1)) for i in range(n)]


def distance_to(route, p):
    return min(haversine_m(p, q) for q in densify(route, 1_000))


def test_densify_caps_the_gap_between_samples():
    dense = densify([(40, -100), (40, -99)], step_m=5_000)

    assert dense[0] == (40, -100) and dense[-1] == (40, -99)
    assert max(haversine_m(a, b) for a, b in zip(dense, dense[1:], strict=False)) <= 5_000
    assert densify([]) == []


def test_every_grid_point_is_inside_the_corridor_and_coverage_is_complete():
    route = straight(40, -100, 40, -95)

    points, spacing = corridor_grid([route])

    assert len(points) <= 600
    assert all(distance_to(route, p) <= CORRIDOR_BUFFER_M + 2_500 for p in points)
    # every spot on the route has a grid point within one grid diagonal
    diagonal_m = spacing * 111_195 * 1.5
    assert all(min(haversine_m(q, p) for p in points) <= diagonal_m for q in densify(route, 20_000))


def test_spacing_is_a_multiple_of_005_and_points_sit_on_the_forecast_grid():
    points, spacing = corridor_grid([straight(41.88, -87.63, 39.74, -104.98)])

    assert round(spacing / 0.05, 6).is_integer()
    assert all(round(lat / 0.05, 6).is_integer() and round(lon / 0.05, 6).is_integer() for lat, lon in points)


def test_long_corridors_get_coarser_spacing_but_stay_under_the_cap():
    short, short_spacing = corridor_grid([straight(32.78, -96.80, 32.75, -97.33)])  # Dallas -> Fort Worth
    long, long_spacing = corridor_grid([straight(41.88, -87.63, 39.74, -104.98)])  # Chicago -> Denver

    assert short_spacing < long_spacing
    assert len(short) <= 600 and len(long) <= 600
    assert len(long) > 300  # the cap is used well, not wasted


def test_three_routes_share_one_grid():
    routes = [straight(40, -100, 40, -95), straight(41, -100, 41, -95), straight(39, -100, 39, -95)]

    points, _ = corridor_grid(routes)

    assert len(points) == len(set(points))
    for route in routes:
        assert any(distance_to(route, p) < 20_000 for p in points)


def test_custom_cap_is_respected():
    points, _ = corridor_grid([straight(40, -100, 40, -90)], max_points=100)

    assert 0 < len(points) <= 100


def test_needs_a_route():
    with pytest.raises(ValueError):
        corridor_grid([[]])
