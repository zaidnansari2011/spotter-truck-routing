import math
from datetime import datetime, timedelta, timezone

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from planner.api_errors import PlanThrottle
from planner.domain.checkpoints import Anchor
from planner.domain.forecast import HOUR_S, HourlySeries
from planner.domain.geo import cumulative_m
from planner.services import trip
from planner.services.openmeteo import WeatherError
from planner.services.tomtom import NoRouteError, Place, RouteData, TomTomError


def line(mid_lat, n=400):
    """Origin (40, -100) -> (mid_lat, -97.5) -> destination (40, -95)."""
    half = n // 2
    first = [(40 + (mid_lat - 40) * i / half, -100 + 2.5 * i / half) for i in range(half)]
    second = [(mid_lat + (40 - mid_lat) * i / half, -97.5 + 2.5 * i / half) for i in range(half + 1)]
    return first + second


def route(mid_lat, hours, source="tomtom"):
    points = line(mid_lat)
    length = cumulative_m(points)[-1]
    return RouteData(points, [Anchor(0, 0, 0)], length, hours * HOUR_S, 120, source)


ROUTES = [route(40, 5), route(41, 6), route(39, 7)]  # A straight and fastest, B north, C south


class FakeTomTom:
    def __init__(self, routes=ROUTES, error=None):
        self.routes, self.error, self.route_calls, self.suggest_calls = routes, error, 0, 0

    def route_options(self, origin, destination, departure, load_lb):
        self.route_calls += 1
        if self.error:
            raise self.error
        return self.routes

    def suggest(self, query):
        self.suggest_calls += 1
        if self.error:
            raise self.error
        return [Place("Denver, CO", 39.74, -104.98)]


class FakeWeather:
    """Constant-in-time weather chosen per location by `conditions(lat, lon) -> (wind, rain, snow)`."""

    def __init__(self, conditions=lambda lat, lon: (5.0, 0.0, 0.0), available=True, error=None):
        self.conditions, self.available, self.error = conditions, available, error

    def hourly(self, cells, start_ts, end_ts):
        if self.error:
            raise self.error
        start = math.floor(start_ts / HOUR_S) * HOUR_S
        hours = math.ceil((end_ts - start) / HOUR_S) + 1
        result = {}
        for lat, lon in cells:
            wind, rain, snow = self.conditions(lat, lon) if self.available else (None, None, None)
            result[(lat, lon)] = HourlySeries(
                start,
                [wind] * hours,
                [wind] * hours,
                [rain] * hours,
                [0.0 if self.available else None] * hours,
                [snow] * hours,
            )
        return result


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fakes(monkeypatch):
    def install(tomtom=None, weather=None):
        tomtom, weather = tomtom or FakeTomTom(), weather or FakeWeather()
        monkeypatch.setattr(trip, "tomtom_client", lambda: tomtom)
        monkeypatch.setattr(trip, "openmeteo_client", lambda: weather)
        return tomtom, weather

    return install


def body(**overrides):
    departure = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    data = {
        "origin": {"label": "West", "lat": 40.0, "lon": -100.0},
        "destination": {"label": "East", "lat": 40.0, "lon": -95.0},
        "departure": departure,
        "load_lb": 20_000,
    }
    data.update(overrides)
    return data


def post(data):
    return APIClient().post("/api/plan/", data, format="json")


def comparison_with(ranking, route_id):
    return next(c for c in ranking["comparisons"] if c["other_id"] == route_id)


def storm_on_route_a(lat, lon):
    # Severe wind (50 mph) on the straight line, east of -98.5, where only route A runs.
    return (50.0, 0.0, 0.0) if abs(lat - 40) < 0.06 and -98.5 < lon < -96.5 else (5.0, 0.0, 0.0)


def test_calm_weather_recommends_the_fastest_route(fakes):
    fakes()

    response = post(body())

    assert response.status_code == 200
    data = response.json()
    assert [r["id"] for r in data["routes"]] == ["A", "B", "C"]
    assert set(data["rankings"]) == {"10", "25", "50"}
    ranking = data["rankings"]["25"]
    assert ranking["recommended_id"] == "A"
    assert ranking["comparisons"][0]["decided_by"] == "duration"
    assert ranking["tradeoff"] is None
    assert data["notices"] == []


def test_response_shape_for_routes_and_checkpoints(fakes):
    fakes()

    data = post(body()).json()

    route_a = data["routes"][0]
    assert route_a["source"] == "tomtom"
    assert route_a["duration_s"] == 5 * HOUR_S
    assert route_a["geometry"][0] == [-100.0, 40.0]  # GeoJSON order: lon, lat
    assert len(route_a["geometry"]) == 2  # a straight line simplifies to its endpoints
    checkpoints = route_a["intervals"]["50"]["checkpoints"]
    assert checkpoints[0]["mile"] == 0
    assert checkpoints[-1]["mile"] == route_a["distance_mi"]
    first = checkpoints[1]
    assert first["forecast"] is True
    assert first["level"] == "Low" and first["level_score"] == 0
    assert set(first) >= {
        "eta",
        "lat",
        "lon",
        "wind_mph",
        "gust_mph",
        "rain_in_hr",
        "snow_in_hr",
        "factors",
        "load_rule",
    }
    summary = route_a["intervals"]["50"]["summary"]
    assert summary["miles_by_level"]["Low"] == pytest.approx(route_a["distance_mi"], abs=0.2)
    assert summary["avg_risk"] == 0
    assert data["assumptions"]["gross_weight_kg_sent_to_routing"] == round(55_000 * 0.45359237)


def test_checkpoint_etas_follow_departure_and_route_time(fakes):
    fakes()
    departure = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    if departure < datetime.now(timezone.utc):
        departure = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(
            minute=0, second=0, microsecond=0
        )

    data = post(body(departure=departure.isoformat())).json()

    route_a = data["routes"][0]
    last = route_a["intervals"]["25"]["checkpoints"][-1]
    assert last["eta"] == (departure + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    assert route_a["arrival"] == last["eta"]


def test_storm_on_the_fastest_route_moves_the_recommendation(fakes):
    fakes(weather=FakeWeather(storm_on_route_a))

    data = post(body(load_lb=20_000)).json()

    ranking = data["rankings"]["10"]
    assert ranking["order"] == ["B", "C", "A"]
    assert comparison_with(ranking, "C")["decided_by"] == "duration"
    assert comparison_with(ranking, "A")["decided_by"] == "severe_miles"
    assert ranking["tradeoff"]["faster_id"] == "A"
    assert ranking["tradeoff"]["note"].startswith("Route A is 1 h faster but has")
    severe = [c for c in data["routes"][0]["intervals"]["10"]["checkpoints"] if c["level"] == "Severe"]
    assert severe and all(c["factors"] == ["wind"] for c in severe)


def test_heavy_load_turns_the_same_storm_into_no_travel(fakes):
    fakes(weather=FakeWeather(storm_on_route_a))

    data = post(body(load_lb=35_000)).json()

    route_a = data["routes"][0]["intervals"]["10"]
    assert route_a["summary"]["do_not_travel"] is True
    flagged = [c for c in route_a["checkpoints"] if c["level"] == "No Travel"]
    assert flagged and all(c["load_rule"] == "45-54 mph wind with a load over 30,000 lb" for c in flagged)
    assert all(c["weather_level"] == "Severe" for c in flagged)
    assert comparison_with(data["rankings"]["10"], "A")["decided_by"] == "no_travel_miles"


@pytest.mark.parametrize(("load_lb", "level"), [(40_000, "High"), (40_001, "Severe")])
def test_load_rule_threshold_through_the_api(fakes, load_lb, level):
    fakes(weather=FakeWeather(lambda lat, lon: (40.0, 0.0, 0.0)))

    data = post(body(load_lb=load_lb)).json()

    assert {c["level"] for c in data["routes"][0]["intervals"]["50"]["checkpoints"]} == {level}


def test_missing_forecast_is_reported_as_unknown_not_low(fakes):
    fakes(weather=FakeWeather(available=False))

    data = post(body()).json()

    checkpoint = data["routes"][0]["intervals"]["25"]["checkpoints"][1]
    assert checkpoint["forecast"] is False
    assert checkpoint["level"] is None
    summary = data["routes"][0]["intervals"]["25"]["summary"]
    assert summary["avg_risk"] is None
    assert summary["unknown_miles"] == pytest.approx(data["routes"][0]["distance_mi"], abs=0.2)


def test_fewer_routes_and_waypoint_routes_are_explained(fakes):
    fakes(tomtom=FakeTomTom(routes=[route(40, 5), route(41, 6, source="via-waypoint")]))

    data = post(body()).json()

    assert [r["id"] for r in data["routes"]] == ["A", "B"]
    assert data["routes"][1]["source"] == "via-waypoint"
    assert "only 2 distinct road routes" in data["notices"][0]
    assert "waypoint" in data["notices"][1]


def test_single_route_notice_wording(fakes):
    fakes(tomtom=FakeTomTom(routes=[route(40, 5)]))

    data = post(body()).json()

    assert data["rankings"]["25"]["comparisons"] == []
    assert "only 1 distinct road route " in data["notices"][0]


def test_identical_requests_reuse_cached_routes(fakes):
    tomtom, _ = fakes()
    data = body()

    post(data)
    post(data)

    assert tomtom.route_calls == 1


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"origin": None}, "origin"),
        ({"load_lb": -1}, "load_lb"),
        ({"load_lb": 80_001}, "load_lb"),
        ({"departure": "2026-10-22T08:00:00"}, "departure"),  # no UTC offset
        ({"departure": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}, "departure"),
        ({"departure": (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()}, "departure"),
        ({"origin": {"label": "x", "lat": 91, "lon": 0}}, "origin"),
        ({"destination": {"label": "Same", "lat": 40.001, "lon": -100.0}}, "destination"),
    ],
)
def test_invalid_input_is_rejected_with_a_readable_message(fakes, overrides, field):
    fakes()

    response = post(body(**overrides))

    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "invalid_input"
    assert field in data["fields"]
    assert data["message"]


def test_departure_within_the_15_minute_grace_is_accepted(fakes):
    fakes()
    recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    assert post(body(departure=recent)).status_code == 200


def test_zero_load_is_allowed(fakes):
    fakes()

    assert post(body(load_lb=0)).status_code == 200


@pytest.mark.parametrize(
    ("tomtom_error", "weather_error", "status", "code"),
    [
        (NoRouteError("NO_ROUTE_FOUND"), None, 422, "no_route"),
        (TomTomError("HTTP 403"), None, 502, "routing_unavailable"),
        (None, WeatherError("HTTP 429"), 502, "weather_unavailable"),
    ],
)
def test_upstream_errors_map_to_clear_responses(fakes, tomtom_error, weather_error, status, code):
    fakes(tomtom=FakeTomTom(error=tomtom_error), weather=FakeWeather(error=weather_error))

    response = post(body())

    assert response.status_code == status
    assert response.json()["code"] == code
    assert "HTTP" not in response.json()["message"]  # internal details stay in the logs


def test_plan_requests_are_rate_limited(fakes, monkeypatch):
    fakes()
    monkeypatch.setattr(PlanThrottle, "THROTTLE_RATES", {"plan": "2/hour"})

    statuses = [post(body()).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    assert post(body()).json()["code"] == "rate_limited"


def test_suggest_returns_places_and_caches_them(fakes):
    tomtom, _ = fakes()
    client = APIClient()

    first = client.get("/api/suggest/", {"q": "  Denv  "})
    client.get("/api/suggest/", {"q": "denv"})

    assert first.status_code == 200
    assert first.json() == [{"label": "Denver, CO", "lat": 39.74, "lon": -104.98}]
    assert tomtom.suggest_calls == 1


def test_suggest_ignores_one_letter_queries(fakes):
    tomtom, _ = fakes()

    response = APIClient().get("/api/suggest/", {"q": "d"})

    assert response.json() == []
    assert tomtom.suggest_calls == 0


def test_suggest_upstream_failure(fakes):
    fakes(tomtom=FakeTomTom(error=TomTomError("HTTP 500")))

    response = APIClient().get("/api/suggest/", {"q": "denver"})

    assert response.status_code == 502
    assert response.json()["code"] == "routing_unavailable"


def test_wrong_method_uses_the_same_error_shape():
    response = APIClient().get("/api/plan/")

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
