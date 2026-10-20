from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from planner.services.tomtom import (
    NoRouteError,
    TomTomClient,
    TomTomError,
    gross_weight_kg,
)

ORIGIN, DESTINATION = (40.0, -100.0), (40.0, -95.0)
PAST = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROUTE_URL = respx.get(url__regex=r"https://api\.tomtom\.com/routing/1/calculateRoute/.*")
SEARCH_URL = respx.get(url__regex=r"https://api\.tomtom\.com/search/2/search/.*")


def bent_line(mid_lat: float, n: int = 300) -> list[tuple[float, float]]:
    """Origin -> (mid_lat, -97.5) -> destination, densely sampled like real routing output."""
    half = n // 2
    first = [(40 + (mid_lat - 40) * i / half, -100 + 2.5 * i / half) for i in range(half)]
    second = [(mid_lat + (40 - mid_lat) * i / half, -97.5 + 2.5 * i / half) for i in range(half + 1)]
    return first + second


def route_json(points, hours: float, legs: int = 1) -> dict:
    length = 500_000.0
    if legs == 2:
        cut = len(points) // 2
        leg_points = [points[: cut + 1], points[cut:]]  # the join point is repeated, as TomTom does
    else:
        leg_points = [points]
    total_points = sum(len(lp) for lp in leg_points)
    return {
        "summary": {
            "lengthInMeters": length,
            "travelTimeInSeconds": hours * 3600,
            "trafficDelayInSeconds": 60,
        },
        "legs": [{"points": [{"latitude": a, "longitude": b} for a, b in lp]} for lp in leg_points],
        "progress": [
            {"pointIndex": 0, "distanceInMeters": 0, "travelTimeInSeconds": 0},
            {"pointIndex": total_points - 1, "distanceInMeters": length, "travelTimeInSeconds": hours * 3600},
        ],
    }


def via_count(request: httpx.Request) -> int:
    return request.url.path.split("/calculateRoute/")[1].count(":")


@pytest.fixture
def client():
    with httpx.Client(base_url="https://api.tomtom.com") as http:
        yield TomTomClient("test-key", http=http)


def test_missing_api_key_is_a_clear_error():
    with pytest.raises(TomTomError, match="TOMTOM_API_KEY"):
        TomTomClient("")


@pytest.mark.parametrize(
    ("load_lb", "expected_kg"),
    [
        (38_000, round(73_000 * 0.45359237)),  # cargo + 35,000 lb tractor-trailer
        (60_000, round(80_000 * 0.45359237)),  # capped at the 80,000 lb federal limit
    ],
)
def test_gross_weight_sent_to_routing(load_lb, expected_kg):
    assert gross_weight_kg(load_lb) == expected_kg


@respx.mock
def test_suggest_builds_readable_labels(client):
    SEARCH_URL.mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "type": "Geography",
                        "address": {"freeformAddress": "Denver, CO"},
                        "position": {"lat": 39.7, "lon": -105.0},
                    },
                    {
                        "type": "POI",
                        "poi": {"name": "Pilot Travel Center"},
                        "address": {
                            "freeformAddress": "1 Main St",
                            "municipality": "Laramie",
                            "countrySubdivision": "WY",
                        },
                        "position": {"lat": 41.3, "lon": -105.6},
                    },
                    {
                        "type": "Point Address",
                        "address": {"freeformAddress": "100 Oak St, Austin, TX 78701"},
                        "position": {"lat": 30.2, "lon": -97.7},
                    },
                ]
            },
        )
    )

    places = client.suggest("den")

    assert [p.label for p in places] == [
        "Denver, CO",
        "Pilot Travel Center, Laramie, WY",
        "100 Oak St, Austin, TX 78701",
    ]
    assert places[0].lat == 39.7
    params = SEARCH_URL.calls.last.request.url.params
    assert params["typeahead"] == "true"
    assert params["countrySet"] == "US,CA"
    assert params["key"] == "test-key"


@respx.mock
def test_suggest_encodes_slashes_in_the_query(client):
    SEARCH_URL.mock(return_value=httpx.Response(200, json={"results": []}))

    client.suggest("I-80 / Exit 5")

    assert "/search/2/search/I-80%20%2F%20Exit%205.json" in str(SEARCH_URL.calls.last.request.url)


@respx.mock
def test_suggest_skips_queries_too_short_to_be_useful(client):
    assert client.suggest(" d ") == []
    assert not SEARCH_URL.called


@respx.mock
def test_route_request_uses_truck_mode_weight_and_two_alternatives(client):
    ROUTE_URL.mock(return_value=httpx.Response(200, json={"routes": [route_json(bent_line(40), 6)]}))

    client._calculate([ORIGIN, DESTINATION], PAST, 38_000, 2)

    params = ROUTE_URL.calls.last.request.url.params
    assert params["travelMode"] == "truck"
    assert params["vehicleCommercial"] == "true"
    assert params["vehicleWeight"] == str(gross_weight_kg(38_000))
    assert params["maxAlternatives"] == "2"
    assert params.get_list("extendedRouteRepresentation") == ["distance", "travelTime"]
    assert params["departAt"] == "now"  # departures in the past use live traffic


@respx.mock
def test_future_departure_is_sent_as_timestamp(client):
    ROUTE_URL.mock(return_value=httpx.Response(200, json={"routes": [route_json(bent_line(40), 6)]}))
    future = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)

    client._calculate([ORIGIN, DESTINATION], future, 20_000, 0)

    assert ROUTE_URL.calls.last.request.url.params["departAt"] == future.isoformat()


@respx.mock
def test_multi_leg_routes_are_joined_in_order(client):
    points = bent_line(41)
    ROUTE_URL.mock(return_value=httpx.Response(200, json={"routes": [route_json(points, 7, legs=2)]}))

    (route,) = client._calculate([ORIGIN, (41, -97.5), DESTINATION], PAST, 20_000, 0)

    assert len(route.points) == len(points) + 1  # join point appears in both legs
    assert route.points[0] == points[0] and route.points[-1] == points[-1]
    assert route.anchors[-1].point_index == len(route.points) - 1
    assert route.duration_s == 7 * 3600
    assert route.traffic_delay_s == 60


@respx.mock
def test_three_distinct_routes_need_no_fallback(client):
    routes = [route_json(bent_line(lat), h) for lat, h in ((40, 6), (41, 7), (39, 7.5))]
    ROUTE_URL.mock(return_value=httpx.Response(200, json={"routes": routes}))

    result = client.route_options(ORIGIN, DESTINATION, PAST, 30_000)

    assert [r.duration_s / 3600 for r in result] == [6, 7, 7.5]
    assert {r.source for r in result} == {"tomtom"}
    assert ROUTE_URL.call_count == 1


@respx.mock
def test_duplicate_alternative_is_replaced_by_a_waypoint_route(client):
    main = [route_json(bent_line(40), 6), route_json(bent_line(40.001), 6.1), route_json(bent_line(41), 7)]

    def respond(request):
        if via_count(request) == 1:
            return httpx.Response(200, json={"routes": main})
        return httpx.Response(200, json={"routes": [route_json(bent_line(38.5), 8, legs=2)]})

    ROUTE_URL.mock(side_effect=respond)

    result = client.route_options(ORIGIN, DESTINATION, PAST, 30_000)

    assert len(result) == 3
    assert [r.source for r in result] == ["tomtom", "tomtom", "via-waypoint"]
    assert result[2].duration_s == 8 * 3600


@respx.mock
def test_fallback_skips_unroutable_and_too_slow_waypoints(client):
    attempts = []

    def respond(request):
        if via_count(request) == 1:
            return httpx.Response(200, json={"routes": [route_json(bent_line(40), 6)]})
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(400, json={"detailedError": {"code": "MAP_MATCHING_FAILURE"}})
        if len(attempts) == 2:
            return httpx.Response(200, json={"routes": [route_json(bent_line(41), 10, legs=2)]})  # > 1.6x
        return httpx.Response(200, json={"routes": [route_json(bent_line(39 - len(attempts)), 7, legs=2)]})

    ROUTE_URL.mock(side_effect=respond)

    result = client.route_options(ORIGIN, DESTINATION, PAST, 30_000)

    assert len(result) == 3
    assert len(attempts) == 4
    assert all(r.duration_s <= 1.6 * 6 * 3600 for r in result)


@respx.mock
def test_returns_fewer_routes_when_no_distinct_alternative_exists(client):
    def respond(request):
        return httpx.Response(200, json={"routes": [route_json(bent_line(40), 6)]})

    ROUTE_URL.mock(side_effect=respond)

    result = client.route_options(ORIGIN, DESTINATION, PAST, 30_000)

    assert len(result) == 1  # every waypoint route came back identical to the fastest one
    assert ROUTE_URL.call_count == 5  # 1 main request + 4 waypoint attempts


@respx.mock
def test_no_route_found_is_its_own_error(client):
    ROUTE_URL.mock(
        return_value=httpx.Response(
            400, json={"detailedError": {"code": "NO_ROUTE_FOUND", "message": "No valid route"}}
        )
    )

    with pytest.raises(NoRouteError):
        client.route_options((21.3, -157.9), DESTINATION, PAST, 30_000)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403, json={"detailedError": {"code": "FORBIDDEN"}}),
        httpx.Response(429, text="Too many requests"),
        httpx.Response(500, text="oops"),
        httpx.Response(400, json={"detailedError": {"code": "BAD_INPUT"}}),
    ],
)
@respx.mock
def test_upstream_failures_raise_tomtom_error(client, response):
    ROUTE_URL.mock(return_value=response)

    with pytest.raises(TomTomError) as info:
        client.route_options(ORIGIN, DESTINATION, PAST, 30_000)

    assert not isinstance(info.value, NoRouteError)


@respx.mock
def test_network_timeout_raises_tomtom_error(client):
    ROUTE_URL.mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(TomTomError, match="ReadTimeout"):
        client.route_options(ORIGIN, DESTINATION, PAST, 30_000)
