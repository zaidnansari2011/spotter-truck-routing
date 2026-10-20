"""Forecast grid along the trip corridor, for the weather heatmap (docs/decisions.md DR-019).

The grid covers everything within CORRIDOR_BUFFER_M of any route. Spacing is the finest multiple
of 0.05 degrees that keeps the grid under MAX_GRID_POINTS, so points line up with the forecast
cache cells (DR-017) and the request stays within one or two Open-Meteo batches.
"""

from __future__ import annotations

import math
from itertools import pairwise

from .geo import EARTH_RADIUS_M, LatLon, haversine_m, lerp

CORRIDOR_BUFFER_M = 48_000  # 30 miles either side of each route
MAX_GRID_POINTS = 600
MIN_SPACING_DEG = 0.05
DENSIFY_STEP_M = 5_000  # route sample spacing for distance checks (max error 2.5 km)

_M_PER_DEG = math.radians(1) * EARTH_RADIUS_M


def densify(points: list[LatLon], step_m: float = DENSIFY_STEP_M) -> list[LatLon]:
    """Add points so consecutive samples are at most `step_m` apart."""
    if not points:
        return []
    result = [points[0]]
    for a, b in pairwise(points):
        pieces = max(1, math.ceil(haversine_m(a, b) / step_m))
        result += [(lerp(a[0], b[0], k / pieces), lerp(a[1], b[1], k / pieces)) for k in range(1, pieces + 1)]
    return result


class _NearRoute:
    """Answers "is this point within buffer_m of any route?" using a coarse spatial hash."""

    def __init__(self, routes: list[list[LatLon]], buffer_m: float):
        samples = [p for route in routes for p in densify(route)]
        max_lat = max(abs(lat) for lat, _ in samples)
        # Cells at least buffer_m wide in both directions, so only neighbouring cells can hold a match.
        self._cell = buffer_m / (_M_PER_DEG * max(math.cos(math.radians(min(max_lat + 1, 89))), 0.01))
        self._buffer = buffer_m
        self._buckets: dict[tuple[int, int], list[LatLon]] = {}
        for p in samples:
            self._buckets.setdefault(self._key(p), []).append(p)

    def _key(self, p: LatLon) -> tuple[int, int]:
        return math.floor(p[0] / self._cell), math.floor(p[1] / self._cell)

    def __call__(self, p: LatLon) -> bool:
        r, c = self._key(p)
        return any(
            haversine_m(p, q) <= self._buffer
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            for q in self._buckets.get((r + dr, c + dc), ())
        )


def corridor_grid(
    routes: list[list[LatLon]], buffer_m: float = CORRIDOR_BUFFER_M, max_points: int = MAX_GRID_POINTS
) -> tuple[list[LatLon], float]:
    """Grid points within `buffer_m` of any route, and the spacing used (degrees)."""
    routes = [r for r in routes if r]
    if not routes:
        raise ValueError("need at least one route")
    near = _NearRoute(routes, buffer_m)
    lats = [lat for route in routes for lat, _ in route]
    lons = [lon for route in routes for _, lon in route]
    pad_lat = buffer_m / _M_PER_DEG
    pad_lon = pad_lat / max(math.cos(math.radians(max(abs(min(lats)), abs(max(lats))))), 0.01)
    bounds = (min(lats) - pad_lat, max(lats) + pad_lat, min(lons) - pad_lon, max(lons) + pad_lon)

    # Estimate the corridor area at a coarse spacing, then pick the spacing that fits max_points.
    probe = 0.25
    probe_count = len(_grid(bounds, probe, near))
    spacing = _round_up(max(MIN_SPACING_DEG, probe * math.sqrt(probe_count / max_points)))
    points = _grid(bounds, spacing, near)
    while len(points) > max_points:
        spacing = _round_up(spacing + MIN_SPACING_DEG)
        points = _grid(bounds, spacing, near)
    return points, spacing


def _grid(bounds: tuple[float, float, float, float], spacing: float, near: _NearRoute) -> list[LatLon]:
    lat_min, lat_max, lon_min, lon_max = bounds
    first_lat, first_lon = math.ceil(lat_min / spacing), math.ceil(lon_min / spacing)
    points = []
    i = first_lat
    while i * spacing <= lat_max:
        j = first_lon
        while j * spacing <= lon_max:
            # Rounded to 2 decimals: grid points are multiples of 0.05, matching forecast cache cells.
            p = (round(i * spacing, 2), round(j * spacing, 2))
            if near(p):
                points.append(p)
            j += 1
        i += 1
    return points


def _round_up(spacing: float) -> float:
    return round(math.ceil(round(spacing / MIN_SPACING_DEG, 6)) * MIN_SPACING_DEG, 2)
