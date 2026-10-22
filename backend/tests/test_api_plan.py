from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from planner.api_errors import PlanThrottle
from planner.domain.forecast import HOUR_S
from planner.services.openmeteo import WeatherError, WeatherRateLimited
from planner.services.tomtom import NoRouteError, TomTomError
from tests.support import FakeTomTom, FakeWeather, TimedWeather, body, post, route


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
    assert data["interval_mi"] == 25  # the default sampling interval
    ranking = data["ranking"]
    assert ranking["recommended_id"] == "A"
    assert ranking["comparisons"][0]["decided_by"] == "duration"
    assert ranking["tradeoff"] is None
    assert data["notices"] == []


def test_response_shape_for_routes_and_checkpoints(fakes):
    fakes()

    data = post(body(interval_mi=50)).json()

    route_a = data["routes"][0]
    assert route_a["source"] == "tomtom"
    assert route_a["duration_s"] == 5 * HOUR_S
    assert route_a["geometry"][0] == [-100.0, 40.0]  # GeoJSON order: lon, lat
    assert len(route_a["geometry"]) == 2  # a straight line simplifies to its endpoints
    checkpoints = route_a["checkpoints"]
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
    summary = route_a["summary"]
    assert summary["miles_by_level"]["Low"] == pytest.approx(route_a["distance_mi"], abs=0.2)
    assert summary["avg_risk"] == 0
    assert data["assumptions"]["gross_weight_kg_sent_to_routing"] == round(55_000 * 0.45359237)


def test_checkpoint_etas_follow_departure_and_route_time(fakes):
    fakes()
    departure = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)

    data = post(body(departure=departure.isoformat())).json()

    route_a = data["routes"][0]
    last = route_a["checkpoints"][-1]
    assert last["eta"] == (departure + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    assert route_a["arrival"] == last["eta"]


def test_storm_on_the_fastest_route_moves_the_recommendation(fakes):
    fakes(weather=FakeWeather(storm_on_route_a))

    data = post(body(load_lb=20_000, interval_mi=10)).json()

    ranking = data["ranking"]
    assert ranking["order"] == ["B", "C", "A"]
    assert comparison_with(ranking, "C")["decided_by"] == "duration"
    assert comparison_with(ranking, "A")["decided_by"] == "severe_miles"
    assert ranking["tradeoff"]["faster_id"] == "A"
    assert ranking["tradeoff"]["note"].startswith("Route A is 1 h faster but has")
    severe = [c for c in data["routes"][0]["checkpoints"] if c["level"] == "Severe"]
    assert severe and all(c["factors"] == ["wind"] for c in severe)


def test_heavy_load_turns_the_same_storm_into_no_travel(fakes):
    fakes(weather=FakeWeather(storm_on_route_a))

    data = post(body(load_lb=35_000, interval_mi=10)).json()

    route_a = data["routes"][0]
    assert route_a["summary"]["do_not_travel"] is True
    flagged = [c for c in route_a["checkpoints"] if c["level"] == "No Travel"]
    assert flagged and all(c["load_rule"] == "45-54 mph wind with a load over 30,000 lb" for c in flagged)
    assert all(c["weather_level"] == "Severe" for c in flagged)
    assert comparison_with(data["ranking"], "A")["decided_by"] == "no_travel_miles"


@pytest.mark.parametrize(("load_lb", "level"), [(40_000, "High"), (40_001, "Severe")])
def test_load_rule_threshold_through_the_api(fakes, load_lb, level):
    fakes(weather=FakeWeather(lambda lat, lon: (40.0, 0.0, 0.0)))

    data = post(body(load_lb=load_lb)).json()

    assert {c["level"] for c in data["routes"][0]["checkpoints"]} == {level}


def test_missing_forecast_is_reported_as_unknown_not_low(fakes):
    fakes(weather=FakeWeather(available=False))

    data = post(body()).json()

    checkpoint = data["routes"][0]["checkpoints"][1]
    assert checkpoint["forecast"] is False
    assert checkpoint["level"] is None
    summary = data["routes"][0]["summary"]
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

    assert data["ranking"]["comparisons"] == []
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


def test_rate_limit_cannot_be_dodged_by_faking_forwarded_for(fakes, monkeypatch):
    fakes()
    monkeypatch.setattr(PlanThrottle, "THROTTLE_RATES", {"plan": "1/hour"})
    client = APIClient()

    # The ingress appends the real client address last; anything before it is the client's own.
    statuses = [
        client.post(
            "/api/plan/", body(), format="json", HTTP_X_FORWARDED_FOR=f"{fake}, 203.0.113.7"
        ).status_code
        for fake in ("1.1.1.1", "2.2.2.2")
    ]

    assert statuses == [200, 429]


def test_suggest_returns_places_and_caches_them(fakes):
    tomtom, _ = fakes()
    client = APIClient()

    first = client.get("/api/suggest/", {"q": "  Denv  "})
    client.get("/api/suggest/", {"q": "denv"})

    assert first.status_code == 200
    assert first.json() == [{"label": "Denver, CO", "lat": 39.74, "lon": -104.98}]
    assert tomtom.suggest_calls == 1


def test_suggest_cache_keys_are_safe_for_any_cache_backend(fakes, recwarn):
    fakes()

    APIClient().get("/api/suggest/", {"q": "Denver, CO"})

    assert not [w for w in recwarn if "CacheKeyWarning" in type(w.message).__name__]


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


def _departure_ts(data):
    return datetime.fromisoformat(data["departure"].replace("Z", "+00:00")).timestamp()


def test_departure_options_cover_the_next_24_hours(fakes):
    fakes()

    data = post(body()).json()

    advice = data["departure_options"]
    assert [o["offset_h"] for o in advice["options"]] == list(range(25))
    assert advice["options"][0]["route_id"] == data["ranking"]["recommended_id"]
    assert advice["options"][0]["worst_level"] == "Low"
    assert advice["suggestion"] is None  # calm weather: leaving now is already safest


def test_advisor_suggests_waiting_out_a_storm_on_every_route(fakes):
    holder = {}

    def storm_for_six_hours(lat, lon, ts):
        stormy = ts < holder["departure"] + 6 * HOUR_S
        return (50.0, 0.0, 0.0) if stormy else (5.0, 0.0, 0.0)

    fakes(weather=TimedWeather(storm_for_six_hours))
    request = body()
    holder["departure"] = datetime.fromisoformat(request["departure"]).timestamp()

    data = post(request).json()

    advice = data["departure_options"]
    assert advice["options"][0]["worst_level"] == "Severe"
    suggestion = advice["suggestion"]
    assert suggestion["worst_level"] == "Low"
    assert suggestion["severe_miles"] == 0
    assert 6 <= suggestion["offset_h"] <= 7  # the first departure that misses the storm entirely
    assert _departure_ts({"departure": suggestion["departure"]}) == pytest.approx(
        _departure_ts(data) + suggestion["offset_h"] * HOUR_S
    )


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_only_the_requested_interval_is_computed(fakes, interval):
    fakes()

    data = post(body(interval_mi=interval)).json()

    assert data["interval_mi"] == interval
    route_a = data["routes"][0]
    miles = [c["mile"] for c in route_a["checkpoints"]]
    expected = [float(m) for m in range(0, int(route_a["distance_mi"]) + 1, interval)]
    if expected[-1] != route_a["distance_mi"]:
        expected.append(route_a["distance_mi"])  # the destination closes the list
    assert miles == pytest.approx(expected, abs=0.1)


def test_unknown_interval_is_rejected(fakes):
    fakes()

    response = post(body(interval_mi=15))

    assert response.status_code == 400
    assert "interval_mi" in response.json()["fields"]


def test_weather_rate_limit_is_a_clear_503(fakes):
    fakes(weather=FakeWeather(error=WeatherRateLimited("Hourly API request limit exceeded")))

    response = post(body())

    assert response.status_code == 503
    assert response.json()["code"] == "weather_busy"


def _ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def test_rest_breaks_are_off_by_default(fakes):
    fakes(tomtom=FakeTomTom(routes=[route(40, 20)]))

    data = post(body()).json()

    assert data["hos"] is False
    assert data["routes"][0]["rest_s"] == 0
    assert data["routes"][0]["duration_s"] == 20 * HOUR_S


def test_rest_breaks_push_arrival_and_checkpoint_times(fakes):
    fakes(tomtom=FakeTomTom(routes=[route(40, 20)]))

    data = post(body(hos=True, interval_mi=10)).json()

    r = data["routes"][0]
    assert data["hos"] is True
    assert r["driving_s"] == 20 * HOUR_S
    assert r["rest_s"] == 11 * HOUR_S  # two 30 min breaks and one 10 h rest
    assert _ts(r["arrival"]) - _ts(data["departure"]) == pytest.approx(31 * HOUR_S, abs=1)
    elapsed = [_ts(c["eta"]) - _ts(data["departure"]) for c in r["checkpoints"]]
    gaps = [b - a for a, b in zip(elapsed, elapsed[1:], strict=False)]
    assert max(gaps) > 10 * HOUR_S  # the 10 hour rest sits between two checkpoints


def test_rest_breaks_change_how_much_faster_a_route_is(fakes):
    # Elapsed time grows with driving time, so the faster route stays faster. What changes is the
    # gap: A (11.2 h) crosses the 11 h limit and needs a 10 h rest, B (10.9 h) only a 30 min break.
    fakes(tomtom=FakeTomTom(routes=[route(40, 11.2), route(41, 10.9)]))

    plain = post(body()).json()["ranking"]
    rested = post(body(hos=True)).json()["ranking"]

    assert plain["comparisons"][0]["reason"] == "Shortest travel time: 10 h 54 min vs 11 h 12 min on Route A"
    assert rested["comparisons"][0]["reason"] == "Shortest travel time: 11 h 24 min vs 21 h 42 min on Route A"


def test_weather_is_never_simulated_without_the_demo_flag(fakes):
    fakes()

    data = post(body()).json()

    assert data["simulation"] is None
    assert {c["level"] for r in data["routes"] for c in r["checkpoints"]} == {"Low"}


@pytest.mark.parametrize("minutes_past_hour", [0, 15, 30, 45])
def test_demo_storm_hits_the_fastest_route_and_is_reported(fakes, minutes_past_hour):
    fakes()
    # The storm is sampled hourly and wind is interpolated to the arrival time, so its peak
    # reaches the truck as 53 to 62 mph depending on the minute. Over 30,000 lb all of that is
    # No Travel, which keeps the test independent of the clock; every quarter hour is covered.
    next_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    departure = next_hour + timedelta(hours=2, minutes=minutes_past_hour)

    data = post(body(demo="storm", interval_mi=10, load_lb=35_000, departure=departure.isoformat())).json()

    sim = data["simulation"]
    assert sim["center"][0] == pytest.approx(-98.0, abs=0.05)  # 40% along route A (-100 to -95)
    route_a = data["routes"][0]
    assert route_a["summary"]["miles_by_level"]["No Travel"] > 0
    assert data["ranking"]["recommended_id"] != "A"
    assert data["departure_options"]["suggestion"] is not None  # waiting lets the storm pass


def test_replanning_a_later_departure_meets_the_same_storm(fakes):
    fakes()
    next_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    first = post(
        body(demo="storm", load_lb=35_000, departure=(next_hour + timedelta(hours=2)).isoformat())
    ).json()
    later = first["departure_options"]["suggestion"]["departure"]

    # Without the earlier storm, a new one would be placed on the new departure and hit again.
    moved = post(body(demo="storm", load_lb=35_000, departure=later)).json()
    pinned = post(body(demo="storm", load_lb=35_000, departure=later, simulation=first["simulation"])).json()

    assert moved["simulation"]["start"] != first["simulation"]["start"]
    assert pinned["simulation"] == first["simulation"]
    assert moved["routes"][0]["summary"]["miles_by_level"]["No Travel"] > 0
    assert pinned["routes"][0]["summary"]["miles_by_level"]["No Travel"] == 0  # the storm has passed


def test_unknown_demo_is_rejected(fakes):
    fakes()

    assert post(body(demo="hurricane")).status_code == 400
