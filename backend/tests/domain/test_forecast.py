import pytest

from planner.domain.forecast import HourlySeries, weather_at
from planner.domain.risk import RAIN_IN_HR, RiskLevel

H = 3600
T14 = 1_800_014_400  # a timestamp on the hour; call it 14:00
T15, T16 = T14 + H, T14 + 2 * H


def series(**overrides) -> HourlySeries:
    """Three hourly stamps: 14:00, 15:00, 16:00."""
    values = {
        "wind_mph": [10.0, 20.0, 30.0],
        "gust_mph": [15.0, 28.0, 40.0],
        "rain_in": [0.0, 0.2, 0.4],
        "showers_in": [0.0, 0.05, 0.0],
        "snowfall_in": [0.0, 0.0, 1.2],
    }
    values.update(overrides)
    return HourlySeries(start_ts=T14, **values)


def test_mid_hour_uses_the_bucket_ending_after_the_eta():
    result = weather_at(series(), T14 + 20 * 60)  # 14:20

    assert result.hour_ending_ts == T15
    assert result.rain_in_hr == pytest.approx(0.25)  # 15:00 rain + showers
    assert result.snow_in_hr == 0
    assert result.gust_mph == 28


def test_wind_is_interpolated_between_the_surrounding_hours():
    assert weather_at(series(), T14 + 30 * 60).wind_mph == pytest.approx(15)
    assert weather_at(series(), T14 + 20 * 60).wind_mph == 13.3  # 13.33, at the shown precision


def test_wind_is_classified_at_the_precision_it_is_shown():
    # 34.96 would show as "35.0" next to Moderate; it is rounded first, so it is High.
    result = weather_at(series(wind_mph=[34.92, 35.0, 0.0]), T14 + 30 * 60)

    assert result.wind_mph == 35.0


def test_gust_is_never_below_the_sustained_wind():
    # Wind interpolated toward the next hour can pass the hour's peak gust.
    result = weather_at(series(wind_mph=[30.0, 50.0, 0.0], gust_mph=[0.0, 35.0, 0.0]), T14 + 45 * 60)

    assert result.wind_mph == 45.0
    assert result.gust_mph == 45.0


def test_eta_exactly_on_the_hour_uses_that_stamp():
    result = weather_at(series(), T15)

    assert result.hour_ending_ts == T15
    assert result.wind_mph == 20
    assert result.rain_in_hr == pytest.approx(0.25)


def test_one_second_past_the_hour_moves_to_the_next_bucket():
    result = weather_at(series(), T15 + 1)

    assert result.hour_ending_ts == T16
    assert result.snow_in_hr == pytest.approx(1.2)


def test_float_sum_is_rounded_so_thresholds_are_not_missed():
    # 0.01 + 0.09 is 0.09999999999999999 in floating point, which would read as Low.
    result = weather_at(series(rain_in=[0.0, 0.01, 0.0], showers_in=[0.0, 0.09, 0.0]), T15)

    assert result.rain_in_hr == 0.1
    assert RAIN_IN_HR.classify(result.rain_in_hr) == RiskLevel.MODERATE


def test_last_partial_hour_is_covered():
    assert weather_at(series(), T15 + 30 * 60) is not None  # 15:30 needs 15:00 and 16:00


@pytest.mark.parametrize(
    "eta",
    [
        T16 + 60,  # needs a 17:00 stamp the series does not have
        T14 - 60,  # before the series starts
    ],
)
def test_outside_the_forecast_is_unknown_not_calm(eta):
    assert weather_at(series(), eta) is None


def test_missing_value_makes_the_sample_unknown():
    assert weather_at(series(snowfall_in=[0.0, None, 0.0]), T15) is None


def test_missing_gust_does_not_hide_the_sample():
    result = weather_at(series(gust_mph=[None, None, None]), T15)

    assert result is not None
    assert result.gust_mph is None


def test_lookup_off_the_hour_grid_returns_none():
    s = series()

    assert s.value(s.wind_mph, T14 + 1) is None
    assert s.value(s.wind_mph, T14) == 10
