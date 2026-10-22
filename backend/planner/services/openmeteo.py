"""Open-Meteo hourly forecasts for many locations, batched and cached (docs/decisions.md DR-004, DR-017).

Locations are snapped to a 0.05 degree grid (about 5.5 km), finer than the GFS model and close to
HRRR's 3 km, so nearby checkpoints on different routes or sampling intervals share one cached
forecast.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
from django.core.cache import cache as default_cache

from planner.domain.forecast import HOUR_S, HourlySeries

BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)
FIELDS = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
SNAP_DEG = 0.05
BATCH_SIZE = 300  # 300 locations x 49 hours measured at 2.1 s and a 4.1 KB URL (DR-004)
MAX_WORKERS = 4
MAX_FORECAST_DAYS = 16
CACHE_SECONDS = 30 * 60  # models update hourly
MINUTE_S = 60
CACHE_VERSION = 2

Cell = tuple[float, float]


class WeatherError(Exception):
    """Open-Meteo could not be reached or rejected the request."""


class WeatherRateLimited(WeatherError):
    """The free tier's request limit is used up (each location counts as one request, DR-023)."""


@dataclass(frozen=True)
class _Window:
    start_ts: int
    end_ts: int

    @property
    def hours(self) -> range:
        return range(self.start_ts, self.end_ts + 1, HOUR_S)


def snap(lat: float, lon: float) -> Cell:
    return round(round(lat / SNAP_DEG) * SNAP_DEG, 2), round(round(lon / SNAP_DEG) * SNAP_DEG, 2)


class OpenMeteoClient:
    def __init__(
        self, http: httpx.Client | None = None, cache=default_cache, now=time.time, sleep=time.sleep
    ):
        self._http = http or httpx.Client(timeout=TIMEOUT)
        self._cache = cache
        self._now = now
        self._sleep = sleep

    def hourly(self, cells: Iterable[Cell], start_ts: float, end_ts: float) -> dict[Cell, HourlySeries]:
        """Hourly series covering [start_ts, end_ts] for each (already snapped) cell.

        Hours outside the forecast horizon come back as None, which the domain treats as unknown.
        """
        cells = list(dict.fromkeys(cells))
        wanted = _Window(_floor_hour(start_ts), _ceil_hour(end_ts))
        horizon = _floor_hour(self._now()) + MAX_FORECAST_DAYS * 24 * HOUR_S - HOUR_S
        fetchable = _Window(wanted.start_ts, min(wanted.end_ts, horizon))

        keys = {cell: _cache_key(cell) for cell in cells}
        cached = self._cache.get_many(keys.values()) if cells else {}
        # Each hour keeps the time it was fetched, so hours merged into a newer entry still
        # expire 30 minutes after their own fetch.
        now = self._now()
        stored = {
            cell: {ts: row for ts, row in cached.get(key, {}).items() if now - row[0] < CACHE_SECONDS}
            for cell, key in keys.items()
        }

        if fetchable.start_ts <= fetchable.end_ts:
            missing = [c for c in cells if any(h not in stored[c] for h in fetchable.hours)]
            if missing:
                fetched = self._fetch(missing, fetchable)
                for cell, hours in fetched.items():
                    stored[cell] |= {ts: (now, values) for ts, values in hours.items()}
                self._cache.set_many({keys[c]: stored[c] for c in fetched}, CACHE_SECONDS)

        return {
            cell: _series({ts: values for ts, (_, values) in stored[cell].items()}, wanted) for cell in cells
        }

    def _fetch(self, cells: list[Cell], window: _Window) -> dict[Cell, dict[int, tuple]]:
        batches = [cells[i : i + BATCH_SIZE] for i in range(0, len(cells), BATCH_SIZE)]
        if len(batches) == 1:
            return self._fetch_batch(batches[0], window)
        result: dict[Cell, dict[int, tuple]] = {}
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
            for part in pool.map(lambda batch: self._fetch_batch(batch, window), batches):
                result.update(part)
        return result

    def _fetch_batch(self, cells: list[Cell], window: _Window) -> dict[Cell, dict[int, tuple]]:
        params = {
            "latitude": ",".join(f"{lat:.2f}" for lat, _ in cells),
            "longitude": ",".join(f"{lon:.2f}" for _, lon in cells),
            "hourly": ",".join(FIELDS),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timeformat": "unixtime",
            "timezone": "GMT",
            "start_hour": _iso_hour(window.start_ts),
            "end_hour": _iso_hour(window.end_ts),
        }
        response = self._get(params)
        if response.status_code == 429 and "Minutely" in _reason(response):
            # The per-minute window resets on the minute; waiting once is better than failing.
            self._sleep(MINUTE_S - self._now() % MINUTE_S + 1)
            response = self._get(params)
        if response.status_code == 429:
            raise WeatherRateLimited(f"Open-Meteo rate limit: {_reason(response)}")
        if response.status_code != 200:
            raise WeatherError(f"Open-Meteo returned HTTP {response.status_code}: {_reason(response)}")

        payload = response.json()
        locations = payload if isinstance(payload, list) else [payload]  # one location is not a list
        if len(locations) != len(cells):
            raise WeatherError(f"Open-Meteo returned {len(locations)} locations for {len(cells)} requested")
        return {cell: _hours(location["hourly"]) for cell, location in zip(cells, locations, strict=True)}

    def _get(self, params: dict) -> httpx.Response:
        try:
            return self._http.get(BASE_URL, params=params)
        except httpx.HTTPError as exc:
            raise WeatherError(f"Open-Meteo request failed: {exc.__class__.__name__}") from exc


def _hours(hourly: dict) -> dict[int, tuple]:
    columns = [hourly[field] for field in FIELDS]
    return {ts: tuple(column[i] for column in columns) for i, ts in enumerate(hourly["time"])}


def _series(hours: dict[int, tuple], window: _Window) -> HourlySeries:
    rows = [hours.get(ts, (None,) * len(FIELDS)) for ts in window.hours]
    wind, gust, rain, showers, snow = (list(column) for column in zip(*rows, strict=True))
    return HourlySeries(
        start_ts=window.start_ts,
        wind_mph=wind,
        gust_mph=gust,
        rain_in=rain,
        showers_in=showers,
        snowfall_in=snow,
    )


def _cache_key(cell: Cell) -> str:
    return f"openmeteo:v{CACHE_VERSION}:{cell[0]:.2f}:{cell[1]:.2f}"


def _floor_hour(ts: float) -> int:
    return int(ts // HOUR_S * HOUR_S)


def _ceil_hour(ts: float) -> int:
    return -int(-ts // HOUR_S * HOUR_S)


def _iso_hour(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M", time.gmtime(ts))


def _reason(response: httpx.Response) -> str:
    try:
        return response.json().get("reason", "unknown")
    except ValueError:
        return "unknown"
