"""Fake routing and weather clients plus request helpers shared by the API tests."""

import math
from datetime import datetime, timedelta, timezone

from rest_framework.test import APIClient

from planner.domain.checkpoints import Anchor
from planner.domain.forecast import HOUR_S, HourlySeries
from planner.domain.geo import cumulative_m
from planner.services.tomtom import Place, RouteData


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
