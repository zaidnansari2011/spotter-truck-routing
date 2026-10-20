import pytest

from planner.domain.checkpoints import (
    Anchor,
    _locate,
    build_profile,
    checkpoint_miles,
    covered_miles,
    place_checkpoints,
)
from planner.domain.geo import METERS_PER_MILE, cumulative_m, haversine_m

DEPARTURE_TS = 1_800_000_000.0


def meridian_route(total_miles: float, n_points: int = 200) -> list[tuple[float, float]]:
    """Straight north-bound polyline of the given length along longitude -100."""
    degrees = total_miles * METERS_PER_MILE / haversine_m((0, -100), (1, -100))
    return [(degrees * i / (n_points - 1), -100.0) for i in range(n_points)]


def constant_speed_profile(total_miles: float, mph: float = 60):
    points = meridian_route(total_miles)
    meters = total_miles * METERS_PER_MILE
    return build_profile(points, [], meters, total_miles / mph * 3600)


def test_haversine_one_degree_of_latitude():
    assert haversine_m((0, 0), (1, 0)) == pytest.approx(111_195, abs=1)


def test_cumulative_distance_starts_at_zero_and_grows():
    totals = cumulative_m([(0, 0), (0, 1), (0, 2)])

    assert totals[0] == 0
    assert totals[2] == pytest.approx(2 * totals[1])


@pytest.mark.parametrize(
    ("total", "interval", "expected"),
    [
        (103, 25, [0, 25, 50, 75, 100, 103]),
        (100, 25, [0, 25, 50, 75, 100]),  # destination on an exact multiple is not duplicated
        (7, 10, [0, 7]),  # route shorter than the interval: origin and destination only
        (120, 50, [0, 50, 100, 120]),
        (30, 10, [0, 10, 20, 30]),
    ],
)
def test_checkpoint_miles(total, interval, expected):
    assert checkpoint_miles(total, interval) == pytest.approx(expected)


def test_checkpoint_miles_rejects_non_positive_interval():
    with pytest.raises(ValueError):
        checkpoint_miles(100, 0)


def test_covered_miles_split_half_interval_each_side():
    assert covered_miles([0, 25, 50, 75, 100, 103]) == pytest.approx([12.5, 25, 25, 25, 14, 1.5])


@pytest.mark.parametrize("miles", [[0, 7], [0, 10, 20, 25.5], [0, 50, 100, 120]])
def test_covered_miles_sum_to_route_length(miles):
    assert sum(covered_miles(miles)) == pytest.approx(miles[-1])


def test_profile_fills_missing_origin_and_destination_anchors():
    profile = constant_speed_profile(100)

    assert profile.meters[0] == 0
    assert profile.seconds[0] == 0
    assert profile.total_miles == pytest.approx(100)
    assert profile.total_seconds == pytest.approx(100 / 60 * 3600)


def test_profile_rejects_decreasing_anchors():
    points = meridian_route(10, n_points=5)
    anchors = [Anchor(2, 8000, 600), Anchor(3, 7000, 700)]

    with pytest.raises(ValueError):
        build_profile(points, anchors, 16_000, 1200)


def test_profile_needs_two_points():
    with pytest.raises(ValueError):
        build_profile([(0, 0)], [], 0, 0)


def test_checkpoints_on_a_constant_speed_route():
    profile = constant_speed_profile(103, mph=60)

    checkpoints = place_checkpoints(profile, 25, DEPARTURE_TS)

    assert [round(c.mile, 6) for c in checkpoints] == [0, 25, 50, 75, 100, 103]
    assert [c.index for c in checkpoints] == list(range(6))
    # 60 mph: one mile per minute
    assert [c.elapsed_s for c in checkpoints] == pytest.approx([0, 1500, 3000, 4500, 6000, 6180])
    assert checkpoints[2].eta_ts == pytest.approx(DEPARTURE_TS + 3000)
    assert sum(c.covered_miles for c in checkpoints) == pytest.approx(103)


def test_eta_follows_anchor_speeds_not_an_average():
    # 100 miles: the first half at 60 mph (50 min), the second half at 30 mph (100 min).
    points = meridian_route(100, n_points=101)
    half = 50 * METERS_PER_MILE
    anchors = [Anchor(0, 0, 0), Anchor(50, half, 50 * 60), Anchor(100, 2 * half, 150 * 60)]
    profile = build_profile(points, anchors, 2 * half, 150 * 60)

    by_mile = {round(c.mile): c for c in place_checkpoints(profile, 25, DEPARTURE_TS)}

    assert by_mile[25].elapsed_s == pytest.approx(25 * 60, rel=1e-6)
    assert by_mile[75].elapsed_s == pytest.approx(50 * 60 + 50 * 60, rel=1e-6)
    assert by_mile[100].elapsed_s == pytest.approx(150 * 60)


def test_anchor_distances_are_respected_when_geometry_disagrees():
    # The API's reported length (120 mi) differs from the polyline's length (100 mi).
    points = meridian_route(100, n_points=11)
    profile = build_profile(points, [], 120 * METERS_PER_MILE, 7200)

    checkpoints = place_checkpoints(profile, 50, DEPARTURE_TS)

    assert [round(c.mile, 6) for c in checkpoints] == [0, 50, 100, 120]
    assert checkpoints[-1].lat == pytest.approx(points[-1][0])


def test_checkpoint_position_is_interpolated_inside_a_segment():
    points = [(0.0, -100.0), (1.0, -100.0)]
    total = haversine_m(points[0], points[1])
    profile = build_profile(points, [], total, 3600)

    mid = place_checkpoints(profile, total / METERS_PER_MILE / 2, DEPARTURE_TS)[1]

    assert mid.lat == pytest.approx(0.5)
    assert mid.lon == pytest.approx(-100.0)
    assert mid.elapsed_s == pytest.approx(1800)


def test_zero_length_spans_do_not_divide_by_zero():
    # Repeated points (common at leg joins) must not break interpolation.
    points = [(0.0, -100.0), (0.0, -100.0), (0.5, -100.0), (0.5, -100.0), (1.0, -100.0)]
    total = haversine_m(points[0], points[-1])
    profile = build_profile(points, [Anchor(1, 0, 0), Anchor(3, total / 2, 900)], total, 1800)

    checkpoints = place_checkpoints(profile, total / METERS_PER_MILE / 4, DEPARTURE_TS)

    assert [c.elapsed_s for c in checkpoints] == pytest.approx([0, 450, 900, 1350, 1800])


def test_locating_past_the_end_clamps_to_the_destination():
    # Floating-point rounding of miles -> meters can overshoot the last point slightly.
    profile = constant_speed_profile(10)

    lat, lon, elapsed = _locate(profile, profile.meters[-1] + 0.001)

    assert (lat, lon) == profile.points[-1]
    assert elapsed == profile.total_seconds


def test_clock_turns_driving_time_into_elapsed_time():
    profile = constant_speed_profile(100, mph=10)  # 10 hours of driving

    plain = place_checkpoints(profile, 50, DEPARTURE_TS)
    rested = place_checkpoints(profile, 50, DEPARTURE_TS, clock=lambda s: s * 2)

    assert [c.elapsed_s for c in rested] == [c.elapsed_s for c in plain]  # driving time unchanged
    assert rested[-1].eta_ts - DEPARTURE_TS == pytest.approx(2 * plain[-1].elapsed_s)
