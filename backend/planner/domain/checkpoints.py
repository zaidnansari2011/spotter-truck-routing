"""Route timing profile and weather checkpoints.

The routing API reports cumulative distance and travel time at a sparse set of "anchor" points
(TomTom's `progress` array). Between anchors, distance and time are interpolated in proportion to
the geometric length of the polyline, so ETAs follow the traffic-aware speed profile instead of
assuming one constant speed for the whole trip (docs/decisions.md, DR-003).
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from itertools import pairwise

from .geo import METERS_PER_MILE, LatLon, cumulative_m, lerp

SAMPLING_INTERVALS_MI = (10, 25, 50)
_EPSILON_MI = 1e-6


@dataclass(frozen=True)
class Anchor:
    point_index: int
    meters: float
    seconds: float


@dataclass(frozen=True)
class RouteProfile:
    points: list[LatLon]
    meters: list[float]  # route distance from the origin at each point
    seconds: list[float]  # driving time from the origin at each point

    @property
    def total_miles(self) -> float:
        return self.meters[-1] / METERS_PER_MILE

    @property
    def total_seconds(self) -> float:
        return self.seconds[-1]


@dataclass(frozen=True)
class Checkpoint:
    index: int
    mile: float
    lat: float
    lon: float
    elapsed_s: float  # driving time from departure
    eta_ts: float  # unix seconds
    covered_miles: float  # route length this checkpoint stands for (DR-007 / plan D7)


def build_profile(
    points: list[LatLon], anchors: list[Anchor], total_meters: float, total_seconds: float
) -> RouteProfile:
    """Distance and time at every point, interpolated between anchors.

    The origin and destination are added as anchors when the API leaves them out, using the
    route summary totals.
    """
    if len(points) < 2:
        raise ValueError("a route needs at least two points")
    last = len(points) - 1

    by_index = {a.point_index: a for a in anchors if 0 <= a.point_index <= last}
    by_index.setdefault(0, Anchor(0, 0.0, 0.0))
    by_index.setdefault(last, Anchor(last, total_meters, total_seconds))
    ordered = [by_index[i] for i in sorted(by_index)]
    for prev, cur in pairwise(ordered):
        if cur.meters < prev.meters or cur.seconds < prev.seconds:
            raise ValueError("anchor distance and time must not decrease along the route")

    geometric = cumulative_m(points)
    meters = [0.0] * len(points)
    seconds = [0.0] * len(points)
    for start, end in pairwise(ordered):
        span = geometric[end.point_index] - geometric[start.point_index]
        steps = end.point_index - start.point_index
        for i in range(start.point_index, end.point_index + 1):
            # Fall back to point count when the polyline span has zero length.
            if span > 0:
                t = (geometric[i] - geometric[start.point_index]) / span
            else:
                t = (i - start.point_index) / steps
            meters[i] = lerp(start.meters, end.meters, t)
            seconds[i] = lerp(start.seconds, end.seconds, t)

    return RouteProfile(points=points, meters=meters, seconds=seconds)


def checkpoint_miles(total_miles: float, interval_miles: float) -> list[float]:
    """Mile 0, every `interval_miles`, and the destination (never duplicated)."""
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")
    miles = []
    step = 0
    while step * interval_miles < total_miles - _EPSILON_MI:
        miles.append(step * interval_miles)
        step += 1
    miles.append(total_miles)
    return miles


def covered_miles(miles: list[float]) -> list[float]:
    """Each checkpoint covers half the gap to each neighbour; the ends are clipped to the route.

    The result always sums to the route length.
    """
    bounds = [miles[0]] + [(a + b) / 2 for a, b in pairwise(miles)] + [miles[-1]]
    return [hi - lo for lo, hi in pairwise(bounds)]


def place_checkpoints(profile: RouteProfile, interval_miles: float, departure_ts: float) -> list[Checkpoint]:
    miles = checkpoint_miles(profile.total_miles, interval_miles)
    coverage = covered_miles(miles)
    checkpoints = []
    for index, (mile, covered) in enumerate(zip(miles, coverage, strict=True)):
        lat, lon, elapsed = _locate(profile, mile * METERS_PER_MILE)
        checkpoints.append(
            Checkpoint(
                index=index,
                mile=mile,
                lat=lat,
                lon=lon,
                elapsed_s=elapsed,
                eta_ts=departure_ts + elapsed,
                covered_miles=covered,
            )
        )
    return checkpoints


def _locate(profile: RouteProfile, target_m: float) -> tuple[float, float, float]:
    """Position and elapsed time at a route distance, interpolated within the segment."""
    meters = profile.meters
    i = bisect_left(meters, target_m)
    if i == 0:
        lat, lon = profile.points[0]
        return lat, lon, profile.seconds[0]
    if i >= len(meters):
        lat, lon = profile.points[-1]
        return lat, lon, profile.seconds[-1]
    span = meters[i] - meters[i - 1]
    t = (target_m - meters[i - 1]) / span if span > 0 else 1.0
    (lat0, lon0), (lat1, lon1) = profile.points[i - 1], profile.points[i]
    return lerp(lat0, lat1, t), lerp(lon0, lon1, t), lerp(profile.seconds[i - 1], profile.seconds[i], t)
