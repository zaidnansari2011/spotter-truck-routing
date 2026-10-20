"""Plan a trip: routes -> checkpoints -> forecasts at each ETA -> risk -> ranking.

Everything for the three sampling intervals is computed in one pass so the UI can switch between
them without another request (docs/decisions.md DR-018).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache

from django.conf import settings
from django.core.cache import cache as django_cache

from planner.domain.advisor import ADVISOR_HOURS, RouteCheckpoints, departure_options, safer_departure
from planner.domain.checkpoints import (
    SAMPLING_INTERVALS_MI,
    Checkpoint,
    RouteProfile,
    build_profile,
    place_checkpoints,
)
from planner.domain.corridor import corridor_grid
from planner.domain.forecast import HOUR_S, weather_at
from planner.domain.geo import LatLon, simplify
from planner.domain.ranking import RouteScore, rank, score_route
from planner.domain.risk import NO_TRAVEL_LOAD_LB, SEVERE_LOAD_LB, RiskLevel, assess
from planner.services.openmeteo import OpenMeteoClient, snap
from planner.services.tomtom import (
    TRACTOR_TRAILER_TARE_LB,
    RouteData,
    TomTomClient,
    gross_weight_kg,
)

ROUTE_IDS = "ABC"
GEOMETRY_TOLERANCE_M = 25
ROUTES_CACHE_SECONDS = 10 * 60


@cache
def tomtom_client() -> TomTomClient:
    return TomTomClient(settings.TOMTOM_API_KEY)


@cache
def openmeteo_client() -> OpenMeteoClient:
    return OpenMeteoClient()


@dataclass(frozen=True)
class RouteSet:
    routes: list[RouteData]
    profiles: list[RouteProfile]  # distance and driving time at every route point
    geometries: list[list[list[float]]]  # simplified [lon, lat] lines for the map
    corridor_points: list[LatLon]  # heatmap grid around all routes
    corridor_spacing_deg: float


@dataclass(frozen=True)
class TripRequest:
    origin: LatLon
    destination: LatLon
    departure: datetime
    load_lb: float


def plan_trip(trip: TripRequest) -> dict:
    route_set = _routes(trip)
    routes = route_set.routes
    departure_ts = trip.departure.timestamp()
    profiles = route_set.profiles
    checkpoints = {
        (i, interval): place_checkpoints(profile, interval, departure_ts)
        for i, profile in enumerate(profiles)
        for interval in SAMPLING_INTERVALS_MI
    }

    every_checkpoint = [c for cps in checkpoints.values() for c in cps]
    # The window also covers later departures for the advisor (same grid cells, more hours).
    series = openmeteo_client().hourly(
        [snap(c.lat, c.lon) for c in every_checkpoint],
        departure_ts,
        max(c.eta_ts for c in every_checkpoint) + ADVISOR_HOURS[-1] * HOUR_S,
    )

    route_payloads = []
    scores: dict[int, list[RouteScore]] = {interval: [] for interval in SAMPLING_INTERVALS_MI}
    for i, (route, profile, geometry) in enumerate(zip(routes, profiles, route_set.geometries, strict=True)):
        route_id = ROUTE_IDS[i]
        intervals = {}
        for interval in SAMPLING_INTERVALS_MI:
            cps = checkpoints[(i, interval)]
            assessed = [_assess_checkpoint(c, series, trip.load_lb) for c in cps]
            segments = [(c.covered_miles, level) for c, (_, level) in zip(cps, assessed, strict=True)]
            score = score_route(route_id, profile.total_seconds, segments)
            scores[interval].append(score)
            intervals[str(interval)] = {
                "checkpoints": [row for row, _ in assessed],
                "summary": _summary(score),
            }
        route_payloads.append(
            {
                "id": route_id,
                "source": route.source,
                "distance_mi": round(profile.total_miles, 1),
                "duration_s": round(profile.total_seconds),
                "traffic_delay_s": round(route.traffic_delay_s),
                "arrival": _iso(departure_ts + profile.total_seconds),
                "geometry": geometry,
                "intervals": intervals,
            }
        )

    return {
        "departure": _iso(departure_ts),
        "load_lb": trip.load_lb,
        "generated_at": _iso(datetime.now(timezone.utc).timestamp()),
        "routes": route_payloads,
        "rankings": {str(interval): _ranking(scores[interval]) for interval in SAMPLING_INTERVALS_MI},
        "departure_options": {
            str(interval): _departure_advice(
                [
                    RouteCheckpoints(ROUTE_IDS[i], profile.total_seconds, checkpoints[(i, interval)])
                    for i, profile in enumerate(profiles)
                ],
                departure_ts,
                series,
                trip.load_lb,
            )
            for interval in SAMPLING_INTERVALS_MI
        },
        "notices": _notices(routes),
        "corridor": {
            "points": [[lon, lat] for lat, lon in route_set.corridor_points],
            "spacing_deg": route_set.corridor_spacing_deg,
        },
        "assumptions": {
            "intervals_mi": list(SAMPLING_INTERVALS_MI),
            "tractor_trailer_tare_lb": TRACTOR_TRAILER_TARE_LB,
            "gross_weight_kg_sent_to_routing": gross_weight_kg(trip.load_lb),
            "load_rules_lb": {
                "no_travel_45_54_mph_over": NO_TRAVEL_LOAD_LB,
                "severe_35_44_mph_over": SEVERE_LOAD_LB,
            },
        },
    }


def _routes(trip: TripRequest) -> RouteSet:
    """Routes, their simplified map geometry and the heatmap grid.

    Routing is the slow call (3 to 5 s); simplification and the grid add about 0.5 s. Identical
    requests within 10 minutes reuse all of it.
    """
    depart = "now" if trip.departure <= datetime.now(timezone.utc) else trip.departure.isoformat()
    raw_key = f"{trip.origin}|{trip.destination}|{depart}|{gross_weight_kg(trip.load_lb)}"
    key = "routes:v4:" + hashlib.sha256(raw_key.encode()).hexdigest()
    cached = django_cache.get(key)
    if cached is None:
        routes = tomtom_client().route_options(trip.origin, trip.destination, trip.departure, trip.load_lb)
        simplified = [simplify(r.points, GEOMETRY_TOLERANCE_M) for r in routes]
        points, spacing = corridor_grid(simplified)
        cached = RouteSet(
            routes=routes,
            profiles=[build_profile(r.points, r.anchors, r.length_m, r.duration_s) for r in routes],
            geometries=[[[round(lon, 5), round(lat, 5)] for lat, lon in line] for line in simplified],
            corridor_points=points,
            corridor_spacing_deg=spacing,
        )
        django_cache.set(key, cached, ROUTES_CACHE_SECONDS)
    return cached


def _assess_checkpoint(checkpoint: Checkpoint, series: dict, load_lb: float) -> tuple[dict, RiskLevel | None]:
    row = {
        "index": checkpoint.index,
        "mile": round(checkpoint.mile, 1),
        "lat": round(checkpoint.lat, 5),
        "lon": round(checkpoint.lon, 5),
        "eta": _iso(checkpoint.eta_ts),
        "covered_miles": round(checkpoint.covered_miles, 2),
    }
    weather = weather_at(series[snap(checkpoint.lat, checkpoint.lon)], checkpoint.eta_ts)
    if weather is None:
        return {**row, "forecast": False, "level": None}, None
    result = assess(weather.wind_mph, weather.rain_in_hr, weather.snow_in_hr, load_lb)
    row = {
        **row,
        "forecast": True,
        "level": result.level.label,
        "level_score": int(result.level),
        "weather_level": result.weather_level.label,
        "factors": list(result.factors),
        "load_rule": result.load_rule,
        "wind_mph": round(weather.wind_mph, 1),
        "gust_mph": None if weather.gust_mph is None else round(weather.gust_mph, 1),
        "rain_in_hr": weather.rain_in_hr,
        "snow_in_hr": weather.snow_in_hr,
    }
    return row, result.level


def _summary(score: RouteScore) -> dict:
    return {
        "miles_by_level": {level.label: round(miles, 1) for level, miles in score.miles_by_level.items()},
        "unknown_miles": round(score.unknown_miles, 1),
        "avg_risk": None if score.avg_risk is None else round(score.avg_risk, 2),
        "do_not_travel": score.miles_by_level[RiskLevel.NO_TRAVEL] > 0,
    }


def _ranking(scores: list[RouteScore]) -> dict:
    result = rank(scores)
    return {
        "order": result.order,
        "recommended_id": result.recommended_id,
        "comparisons": [
            {"other_id": c.other_id, "decided_by": c.decided_by, "reason": c.reason}
            for c in result.comparisons
        ],
        "tradeoff": None
        if result.tradeoff is None
        else {
            "faster_id": result.tradeoff.faster_id,
            "saving_s": result.tradeoff.saving_s,
            "note": result.tradeoff.note,
        },
        "all_no_travel": result.all_no_travel,
    }


def _departure_advice(
    routes: list[RouteCheckpoints], departure_ts: float, series: dict, load_lb: float
) -> dict:
    # The 10/25/50 mile sets share checkpoints and offsets shift by whole hours, so many
    # (cell, time) lookups repeat; remembering them roughly halves the advisor's cost.
    levels: dict[tuple[tuple[float, float], float], RiskLevel | None] = {}

    def level_at(checkpoint: Checkpoint, eta_ts: float) -> RiskLevel | None:
        key = (snap(checkpoint.lat, checkpoint.lon), eta_ts)
        if key not in levels:
            weather = weather_at(series[key[0]], eta_ts)
            levels[key] = (
                None
                if weather is None
                else assess(weather.wind_mph, weather.rain_in_hr, weather.snow_in_hr, load_lb).level
            )
        return levels[key]

    options = departure_options(routes, departure_ts, level_at)
    suggestion = safer_departure(options)

    def payload(option) -> dict:
        score = option.recommended
        return {
            "offset_h": option.offset_h,
            "departure": _iso(option.departure_ts),
            "route_id": score.route_id,
            "worst_level": _worst_level(score),
            "no_travel_miles": round(score.no_travel_miles, 1),
            "severe_miles": round(score.severe_miles, 1),
            "high_miles": round(score.high_miles, 1),
            "avg_risk": None if score.avg_risk is None else round(score.avg_risk, 2),
            "arrival": _iso(option.departure_ts + score.duration_s),
        }

    return {
        "options": [payload(o) for o in options],
        "suggestion": None if suggestion is None else payload(suggestion),
    }


def _worst_level(score: RouteScore) -> str | None:
    if score.avg_risk is None:
        return None
    worst = max((level for level, miles in score.miles_by_level.items() if miles > 0), default=RiskLevel.LOW)
    return worst.label


def _notices(routes: list[RouteData]) -> list[str]:
    notices = []
    if len(routes) == 1:
        notices.append(
            "There is only 1 distinct road route between these places, so it is the only option shown."
        )
    elif len(routes) < len(ROUTE_IDS):
        notices.append(
            f"There are only {len(routes)} distinct road routes between these places, "
            "so fewer than 3 options are shown."
        )
    if any(r.source == "via-waypoint" for r in routes):
        notices.append(
            "Some options were generated by routing through a waypoint, "
            "as the routing service returned fewer than 3 distinct routes."
        )
    return notices


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
