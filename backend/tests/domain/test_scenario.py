import pytest

from planner.domain.forecast import HOUR_S
from planner.domain.risk import RiskLevel, assess
from planner.domain.scenario import (
    PEAK_SNOW_IN_HR,
    PEAK_WIND_MPH,
    STORM_LIFETIME_H,
    STORM_RADIUS_M,
    SimulatedStorm,
    overlay,
)

T0 = 1_800_000_000.0
STORM = SimulatedStorm(center=(41.0, -96.0), start_ts=T0)


def test_centre_at_full_strength_is_no_travel():
    wind, rain, snow = STORM.conditions((41.0, -96.0), T0)

    assert (wind, rain, snow) == (PEAK_WIND_MPH, 0.0, PEAK_SNOW_IN_HR)
    assert assess(wind, rain, snow, load_lb=0).level == RiskLevel.NO_TRAVEL


def test_strength_falls_off_with_distance():
    near = STORM.conditions((41.0, -95.5), T0)[0]
    far = STORM.conditions((41.0, -94.5), T0)[0]

    assert PEAK_WIND_MPH > near > far > 0


def test_nothing_outside_the_radius():
    outside = (41.0 + (STORM_RADIUS_M + 5_000) / 111_195, -96.0)

    assert STORM.conditions(outside, T0) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("hours", "strength"),
    [(-3, 0.0), (-1, 0.5), (0, 1.0), (STORM_LIFETIME_H / 2, 0.5), (STORM_LIFETIME_H + 1, 0.0)],
)
def test_builds_up_then_dissipates(hours, strength):
    wind = STORM.conditions((41.0, -96.0), T0 + hours * HOUR_S)[0]

    assert wind == pytest.approx(PEAK_WIND_MPH * strength)


def test_the_ring_around_the_core_exercises_the_load_rules():
    # Somewhere between core and edge the wind is in the 35-54 mph band the load rules use.
    winds = [STORM.conditions((41.0, -96.0 + d / 10), T0)[0] for d in range(0, 25)]

    assert any(35 <= w < 45 for w in winds)
    assert any(45 <= w < 55 for w in winds)


def test_overlay_takes_the_worse_value_and_keeps_missing_data_missing():
    assert overlay((30.0, 0.2, 0.0), (10.0, 0.0, 1.5)) == (30.0, 0.2, 1.5)
    assert overlay((None, 0.1, 0.0), (50.0, 0.0, 0.0)) == (None, 0.1, 0.0)
