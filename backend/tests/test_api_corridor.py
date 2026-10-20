import math
from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from planner.api_errors import CorridorThrottle
from planner.domain.forecast import HOUR_S
from tests.support import FakeWeather, body, post

START = datetime.now(timezone.utc) + timedelta(minutes=30)
POINTS = [[-100.0, 40.0], [-99.65, 40.0], [-99.3, 40.35]]


def corridor(data):
    return APIClient().post("/api/corridor/", data, format="json")


def request(**overrides):
    data = {"points": POINTS, "start": START.isoformat(), "load_lb": 20_000}
    data.update(overrides)
    return data


def test_plan_response_includes_the_corridor_grid(fakes):
    fakes()

    data = post(body()).json()

    grid = data["corridor"]
    assert 0 < len(grid["points"]) <= 300
    assert round(grid["spacing_deg"] / 0.05, 6).is_integer()
    lons = [lon for lon, _ in grid["points"]]
    assert min(lons) < -99.5 and max(lons) > -95.5  # covers the trip from end to end


def test_frames_cover_hours_0_to_48_for_every_point(fakes):
    fakes(weather=FakeWeather(lambda lat, lon: (30.0, 0.3, 1.2)))

    data = corridor(request()).json()

    assert len(data["hours"]) == 49
    assert data["hours"][0] == math.floor(START.timestamp() / HOUR_S) * HOUR_S
    assert data["hours"][48] - data["hours"][0] == 48 * HOUR_S
    for key in ("risk", "risk_load", "wind", "rain", "snow"):
        assert len(data[key]) == len(POINTS)
        assert all(len(row) == 49 for row in data[key])
    assert data["wind"][0][0] == 30
    assert data["rain"][0][0] == 30  # hundredths of an inch per hour
    assert data["snow"][0][0] == 120
    assert data["risk"][0][0] // 100 == 2  # High (snow 1.2 in/hr and rain 0.3 in/hr)


def test_load_adjusted_layer_differs_only_when_a_load_rule_applies(fakes):
    fakes(weather=FakeWeather(lambda lat, lon: (47.0, 0.0, 0.0)))

    light = corridor(request(load_lb=30_000)).json()
    heavy = corridor(request(load_lb=30_001)).json()

    assert light["risk"][0][0] // 100 == 3  # Severe on weather alone
    assert light["risk_load"][0][0] // 100 == 3
    assert heavy["risk_load"][0][0] == 400  # No Travel once the load is over 30,000 lb
    assert heavy["risk"][0][0] == light["risk"][0][0]


def test_hours_without_a_forecast_are_null(fakes):
    fakes(weather=FakeWeather(available=False))

    data = corridor(request()).json()

    assert data["risk"][0][0] is None
    assert data["wind"][2][48] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"points": []},
        {"points": [[-100.0]]},
        {"points": [[-100.0, 95.0]]},
        {"points": [[-100.0, 40.0]] * 1001},
        {"start": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()},
        {"start": (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()},
        {"load_lb": 90_000},
    ],
)
def test_invalid_corridor_requests_are_rejected(fakes, overrides):
    fakes()

    response = corridor(request(**overrides))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_input"


def test_corridor_requests_are_rate_limited(fakes, monkeypatch):
    fakes()
    monkeypatch.setattr(CorridorThrottle, "THROTTLE_RATES", {"corridor": "1/hour"})

    assert [corridor(request()).status_code for _ in range(2)] == [200, 429]


def test_corridor_shows_the_demo_storm_when_the_plan_used_one(fakes):
    fakes()
    simulation = {"center": [-99.65, 40.0], "start": START.isoformat()}

    real = corridor(request()).json()
    simulated = corridor(request(simulation=simulation)).json()

    assert max(real["risk"][1]) < 100  # calm
    assert max(simulated["risk"][1]) == 400  # the storm centre is No Travel
    assert max(simulated["wind"][1]) > 55  # peak winds at the centre (it builds up before hour 0)


def test_corridor_rejects_a_bad_simulation_block(fakes):
    fakes()

    response = corridor(request(simulation={"center": [-99.65, 95.0], "start": START.isoformat()}))

    assert response.status_code == 400
