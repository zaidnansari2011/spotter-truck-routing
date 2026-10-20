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


def point_at_fraction(points: list[LatLon], fraction: float) -> LatLon:
    """The point a given fraction of the way along a polyline (by distance)."""
    totals = cumulative_m(points)
    target = totals[-1] * fraction
    for i in range(1, len(points)):
        if totals[i] >= target:
            span = totals[i] - totals[i - 1]
            t = (target - totals[i - 1]) / span if span > 0 else 0.0
            return lerp(points[i - 1][0], points[i][0], t), lerp(points[i - 1][1], points[i][1], t)
    return points[-1]


def _to_local_m(origin: LatLon, point: LatLon) -> tuple[float, float]:
    """Equirectangular (east, north) meters from origin; accurate over a few hundred km."""
    m_per_deg = math.radians(1) * EARTH_RADIUS_M
    east = (point[1] - origin[1]) * m_per_deg * math.cos(math.radians(origin[0]))
    north = (point[0] - origin[0]) * m_per_deg
    return east, north


def offset_point(start: LatLon, end: LatLon, around: LatLon, offset_m: float, side: int) -> LatLon:
    """`around` moved `offset_m` perpendicular to the start->end direction (side +1 left, -1 right)."""
    east, north = _to_local_m(start, end)
    length = math.hypot(east, north)
    if length == 0:
        raise ValueError("start and end must differ")
    left_east, left_north = -north / length, east / length
    m_per_deg = math.radians(1) * EARTH_RADIUS_M
    dlat = side * offset_m * left_north / m_per_deg
    dlon = side * offset_m * left_east / (m_per_deg * math.cos(math.radians(around[0])))
    return around[0] + dlat, around[1] + dlon


def overlap_fraction(route: list[LatLon], other: list[LatLon], cell_deg: float = 0.003) -> float:
    """Share of `route`'s points that lie on or next to `other` (within roughly 300-600 m).

    Both routes come from the same routing engine at ~100 m point spacing, so a grid-cell lookup
    is enough to tell shared road from different road.
    """

    def cell(p: LatLon) -> tuple[int, int]:
        return math.floor(p[0] / cell_deg), math.floor(p[1] / cell_deg)

    occupied = {cell(p) for p in other}
    near = 0
    for p in route:
        r, c = cell(p)
        if any((r + dr, c + dc) in occupied for dr in (-1, 0, 1) for dc in (-1, 0, 1)):
            near += 1
    return near / len(route)


def simplify(points: list[LatLon], tolerance_m: float) -> list[LatLon]:
    """Douglas-Peucker: drop points that deviate less than `tolerance_m` from the simplified line."""
    if len(points) < 3:
        return list(points)
    origin = points[0]
    local = [_to_local_m(origin, p) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = local[first], local[last]
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        worst, worst_i = 0.0, -1
        for i in range(first + 1, last):
            px, py = local[i]
            if seg_len_sq == 0:
                dist = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
                dist = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if dist > worst:
                worst, worst_i = dist, i
        if worst > tolerance_m:
            keep[worst_i] = True
            stack += [(first, worst_i), (worst_i, last)]
    return [p for p, k in zip(points, keep, strict=True) if k]
