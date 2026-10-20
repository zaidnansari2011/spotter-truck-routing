import math

import pytest

from planner.domain.risk import (
    RAIN_IN_HR,
    SNOW_IN_HR,
    WIND_MPH,
    RiskLevel,
    assess,
    risk_index,
)

LOW, MOD, HIGH, SEVERE, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, LOW),
        (24.9, LOW),
        (25, MOD),
        (34, MOD),
        (34.9, MOD),  # the table's "25-34" leaves 34-35 undefined; < 35 stays Moderate
        (35, HIGH),
        (44.9, HIGH),
        (45, SEVERE),
        (54.9, SEVERE),
        (55, NT),  # ">= 55" is inclusive
        (80, NT),
    ],
)
def test_wind_bands(mph, expected):
    assert WIND_MPH.classify(mph) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0, LOW),
        (0.099, LOW),
        (0.10, MOD),
        (0.249, MOD),
        (0.25, HIGH),  # 0.25 appears in two bands; lower bound inclusive puts it in High
        (0.50, SEVERE),
        (1.00, SEVERE),  # No Travel is "> 1.00", so 1.00 itself is Severe
        (1.001, NT),
    ],
)
def test_rain_bands(in_hr, expected):
    assert RAIN_IN_HR.classify(in_hr) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0, LOW),
        (0.49, LOW),
        (0.5, MOD),
        (1.0, HIGH),
        (2.0, SEVERE),
        (3.0, SEVERE),  # No Travel is "> 3.0"
        (3.01, NT),
    ],
)
def test_snow_bands(in_hr, expected):
    assert SNOW_IN_HR.classify(in_hr) == expected


def test_calm_weather_is_low_with_no_factors():
    result = assess(wind_mph=5, rain_in_hr=0, snow_in_hr=0, load_lb=20_000)

    assert result.level == LOW
    assert result.factors == ()
    assert result.load_rule is None


def test_worst_condition_wins():
    result = assess(wind_mph=30, rain_in_hr=0.3, snow_in_hr=0, load_lb=10_000)

    assert (result.wind, result.rain, result.snow) == (MOD, HIGH, LOW)
    assert result.level == HIGH
    assert result.factors == ("rain",)


def test_ties_list_every_factor_at_the_final_level():
    result = assess(wind_mph=36, rain_in_hr=0.3, snow_in_hr=0, load_lb=10_000)

    assert result.level == HIGH
    assert result.factors == ("wind", "rain")


@pytest.mark.parametrize(
    ("mph", "load_lb", "expected", "rule_fired"),
    [
        (55, 0, NT, False),  # >= 55 mph is No Travel for any load
        (45, 30_001, NT, True),
        (54.9, 45_000, NT, True),
        (45, 30_000, SEVERE, False),  # rule needs a load strictly over 30,000 lb
        (35, 40_001, SEVERE, True),
        (44.9, 40_001, SEVERE, True),
        (35, 40_000, HIGH, False),  # strictly over 40,000 lb
        (35, 35_000, HIGH, False),  # the 30,000 lb rule only covers 45-54 mph
        (34.9, 50_000, MOD, False),  # below the 35 mph band, no rule applies
    ],
)
def test_load_rules(mph, load_lb, expected, rule_fired):
    result = assess(wind_mph=mph, rain_in_hr=0, snow_in_hr=0, load_lb=load_lb)

    assert result.level == expected
    assert (result.load_rule is not None) == rule_fired
    if rule_fired:
        assert result.factors == ("wind",)
        assert result.weather_level < result.level


def test_load_rules_never_lower_the_level():
    # Rain is already No Travel; the 35-44 mph rule would only give Severe.
    result = assess(wind_mph=40, rain_in_hr=1.5, snow_in_hr=0, load_lb=50_000)

    assert result.level == NT
    assert result.factors == ("rain",)
    assert result.load_rule is None


def test_load_rule_is_not_reported_when_weather_is_already_as_bad():
    # 35-44 mph with a heavy load forces Severe, but snow is Severe on its own.
    result = assess(wind_mph=40, rain_in_hr=0, snow_in_hr=2.5, load_lb=50_000)

    assert result.level == SEVERE
    assert result.load_rule is None
    assert result.factors == ("snow",)


def test_negative_load_is_rejected():
    with pytest.raises(ValueError):
        assess(wind_mph=0, rain_in_hr=0, snow_in_hr=0, load_lb=-1)


def test_level_labels():
    assert [lvl.label for lvl in RiskLevel] == ["Low", "Moderate", "High", "Severe", "No Travel"]


@pytest.mark.parametrize("thresholds", [WIND_MPH, RAIN_IN_HR, SNOW_IN_HR])
def test_index_floor_always_matches_level(thresholds):
    top = thresholds.no_travel * 1.3
    values = [top * i / 2000 for i in range(2001)]
    values += [thresholds.moderate, thresholds.high, thresholds.severe, thresholds.no_travel]

    for value in values:
        assert math.floor(thresholds.index(value)) == thresholds.classify(value), value


def test_index_is_monotonic():
    values = [i / 100 for i in range(0, 7000)]
    indices = [WIND_MPH.index(v) for v in values]

    assert indices == sorted(indices)


def test_combined_index_matches_assessed_level():
    cases = [
        (10, 0, 0, 20_000),
        (30, 0.3, 0, 20_000),
        (47, 0, 0, 35_000),  # load rule -> No Travel
        (38, 0, 0, 45_000),  # load rule -> Severe
        (20, 1.0, 0, 0),  # rain exactly 1.00 -> Severe, index must stay below 4
        (0, 0, 3.2, 0),
    ]
    for wind, rain, snow, load in cases:
        expected = assess(wind, rain, snow, load)
        assert math.floor(risk_index(wind, rain, snow, load)) == expected.level
        assert math.floor(risk_index(wind, rain, snow)) == expected.weather_level
