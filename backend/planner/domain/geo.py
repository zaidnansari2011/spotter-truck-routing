"""Small geometry helpers. Coordinates are (lat, lon) in degrees, distances in meters."""

from __future__ import annotations

import math
from itertools import pairwise

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG)
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def cumulative_m(points: list[LatLon]) -> list[float]:
    """Distance from the first point to each point along the polyline."""
    totals = [0.0]
    for prev, cur in pairwise(points):
        totals.append(totals[-1] + haversine_m(prev, cur))
    return totals


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
