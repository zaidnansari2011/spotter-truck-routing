import calendar
import time
import uuid

import httpx
import pytest
import respx
from django.core.cache.backends.locmem import LocMemCache

from planner.services.openmeteo import OpenMeteoClient, WeatherError, WeatherRateLimited, snap

H = 3600
NOW = 1_800_000_000  # on the hour
FORECAST_URL = respx.get(url__startswith="https://api.open-meteo.com/v1/forecast")


def location(start, end, wind=10.0):
    hours = list(range(start, end + 1, H))
    return {
        "hourly": {
            "time": hours,
            "wind_speed_10m": [wind] * len(hours),
            "wind_gusts_10m": [wind + 5] * len(hours),
            "rain": [0.1] * len(hours),
            "showers": [0.0] * len(hours),
            "snowfall": [0.0] * len(hours),
        }
    }


def respond_with_window(request):
    """Answer like Open-Meteo: one entry per requested location covering start_hour..end_hour."""
    params = request.url.params
    count = len(params["latitude"].split(","))
    start = parse_iso(params["start_hour"])
    end = parse_iso(params["end_hour"])
    body = [location(start, end) for _ in range(count)]
    return httpx.Response(200, json=body if count > 1 else body[0])


def parse_iso(text):
    return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M"))


@pytest.fixture
def cache():
    # LocMemCache instances with the same name share storage, so each test gets a unique one.
    return LocMemCache(f"test-openmeteo-{uuid.uuid4()}", {})


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def client(cache, sleeps):
    with httpx.Client() as http:
        yield OpenMeteoClient(http=http, cache=cache, now=lambda: NOW + 125, sleep=sleeps.append)


def cells(n):
    return [snap(30 + i * 0.05, -100) for i in range(n)]


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        ((41.8832), (-87.6324), (41.9, -87.65)),
        ((39.7385), (-104.9849), (39.75, -105.0)),
        ((0.024), (0.026), (0.0, 0.05)),
    ],
)
def test_snap_to_005_degree_grid(lat, lon, expected):
    assert snap(lat, lon) == expected


@respx.mock
def test_request_parameters(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    client.hourly(cells(2), NOW + 600, NOW + 3 * H + 60)

    params = FORECAST_URL.calls.last.request.url.params
    assert params["latitude"] == "30.00,30.05"
    assert params["longitude"] == "-100.00,-100.00"
    assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timeformat"] == "unixtime"
    assert params["timezone"] == "GMT"
    # the window is widened to whole hours on both sides of the requested times
    assert parse_iso(params["start_hour"]) == NOW
    assert parse_iso(params["end_hour"]) == NOW + 4 * H


@respx.mock
def test_series_cover_the_window_for_every_cell(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    result = client.hourly(cells(3), NOW, NOW + 2 * H)

    assert set(result) == set(cells(3))
    series = result[cells(3)[1]]
    assert series.start_ts == NOW
    assert series.wind_mph == [10.0, 10.0, 10.0]
    assert series.gust_mph == [15.0, 15.0, 15.0]


@respx.mock
def test_single_location_response_is_an_object_not_a_list(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    result = client.hourly(cells(1), NOW, NOW + H)

    assert result[cells(1)[0]].rain_in == [0.1, 0.1]


@respx.mock
def test_large_requests_are_split_into_batches_of_300(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    result = client.hourly(cells(650), NOW, NOW + H)

    sizes = sorted(len(c.request.url.params["latitude"].split(",")) for c in FORECAST_URL.calls)
    assert sizes == [50, 300, 300]
    assert len(result) == 650


@respx.mock
def test_duplicate_cells_are_requested_once(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    result = client.hourly(cells(2) + cells(2), NOW, NOW + H)

    assert FORECAST_URL.calls.last.request.url.params["latitude"] == "30.00,30.05"
    assert len(result) == 2


@respx.mock
def test_cached_cells_are_not_fetched_again(client):
    FORECAST_URL.mock(side_effect=respond_with_window)
    client.hourly(cells(2), NOW, NOW + 2 * H)

    client.hourly(cells(2), NOW + H, NOW + 2 * H)  # inside the cached window
    assert FORECAST_URL.call_count == 1

    client.hourly(cells(3), NOW, NOW + 2 * H)  # one new cell
    assert FORECAST_URL.call_count == 2
    assert FORECAST_URL.calls.last.request.url.params["latitude"] == "30.10"


@respx.mock
def test_extending_the_window_refetches_and_merges(client):
    FORECAST_URL.mock(side_effect=respond_with_window)
    client.hourly(cells(1), NOW, NOW + H)

    result = client.hourly(cells(1), NOW, NOW + 3 * H)

    assert FORECAST_URL.call_count == 2
    assert result[cells(1)[0]].wind_mph == [10.0] * 4


@respx.mock
def test_merged_hours_expire_30_minutes_after_their_own_fetch(cache, sleeps):
    FORECAST_URL.mock(side_effect=respond_with_window)
    clock = [NOW]
    with httpx.Client() as http:
        client = OpenMeteoClient(http=http, cache=cache, now=lambda: clock[0], sleep=sleeps.append)
        client.hourly(cells(1), NOW, NOW + H)  # fetches 00:00 and 01:00
        clock[0] = NOW + 20 * 60
        client.hourly(cells(1), NOW + H, NOW + 2 * H)  # fetches 01:00 and 02:00, keeps 00:00
        clock[0] = NOW + 40 * 60  # 00:00 is now 40 minutes old

        client.hourly(cells(1), NOW, NOW + 2 * H)

    assert FORECAST_URL.call_count == 3
    assert parse_iso(FORECAST_URL.calls.last.request.url.params["start_hour"]) == NOW


@respx.mock
def test_hours_beyond_the_16_day_horizon_are_unknown(client):
    FORECAST_URL.mock(side_effect=respond_with_window)
    horizon_end = NOW + 16 * 24 * H - H

    result = client.hourly(cells(1), horizon_end - H, horizon_end + 2 * H)

    assert parse_iso(FORECAST_URL.calls.last.request.url.params["end_hour"]) == horizon_end
    assert result[cells(1)[0]].wind_mph == [10.0, 10.0, None, None]


@respx.mock
def test_window_entirely_past_the_horizon_makes_no_request(client):
    FORECAST_URL.mock(side_effect=respond_with_window)

    result = client.hourly(cells(1), NOW + 20 * 24 * H, NOW + 20 * 24 * H + H)

    assert not FORECAST_URL.called
    assert result[cells(1)[0]].wind_mph == [None, None]


@respx.mock
def test_no_cells_means_no_request(client):
    assert client.hourly([], NOW, NOW + H) == {}
    assert not FORECAST_URL.called


@respx.mock
def test_api_error_reason_is_reported(client):
    FORECAST_URL.mock(
        return_value=httpx.Response(400, json={"error": True, "reason": "Parameter end_hour out of range"})
    )

    with pytest.raises(WeatherError, match="end_hour out of range"):
        client.hourly(cells(1), NOW, NOW + H)


def too_many(reason):
    return httpx.Response(429, json={"error": True, "reason": reason})


@respx.mock
def test_minutely_limit_waits_for_the_next_minute_and_retries(client, sleeps):
    FORECAST_URL.mock(side_effect=[too_many("Minutely API request limit exceeded."), respond_with_window])

    result = client.hourly(cells(1), NOW, NOW + H)

    assert sleeps == [56]  # 5 s past the minute: wait 55 s plus 1 s of margin
    assert FORECAST_URL.call_count == 2
    assert result[cells(1)[0]].wind_mph == [10.0, 10.0]


@respx.mock
def test_minutely_limit_twice_gives_up_with_a_rate_limit_error(client, sleeps):
    limited = too_many("Minutely API request limit exceeded.")
    FORECAST_URL.mock(side_effect=[limited, limited])

    with pytest.raises(WeatherRateLimited, match="Minutely"):
        client.hourly(cells(1), NOW, NOW + H)
    assert len(sleeps) == 1


@respx.mock
def test_hourly_or_daily_limit_fails_fast_without_waiting(client, sleeps):
    FORECAST_URL.mock(return_value=too_many("Daily API request limit exceeded."))

    with pytest.raises(WeatherRateLimited, match="Daily"):
        client.hourly(cells(1), NOW, NOW + H)
    assert sleeps == []


@respx.mock
def test_rate_limit_without_json_body(client, sleeps):
    FORECAST_URL.mock(return_value=httpx.Response(429, text="slow down"))

    with pytest.raises(WeatherRateLimited, match="unknown"):
        client.hourly(cells(1), NOW, NOW + H)
    assert sleeps == []


@respx.mock
def test_network_failure_is_a_weather_error(client):
    FORECAST_URL.mock(side_effect=httpx.ConnectTimeout("down"))

    with pytest.raises(WeatherError, match="ConnectTimeout"):
        client.hourly(cells(1), NOW, NOW + H)


@respx.mock
def test_location_count_mismatch_is_rejected(client):
    FORECAST_URL.mock(return_value=httpx.Response(200, json=[location(NOW, NOW + H)]))

    with pytest.raises(WeatherError, match="1 locations for 2"):
        client.hourly(cells(2), NOW, NOW + H)
