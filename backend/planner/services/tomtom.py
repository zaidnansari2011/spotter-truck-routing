"""TomTom Search (place suggestions) and Routing (truck routes) clients.

See docs/decisions.md DR-001 to DR-003 and DR-015 for the parameters and the alternative-route
fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from planner.domain.checkpoints import Anchor
from planner.domain.geo import LatLon, haversine_m, offset_point, overlap_fraction, point_at_fraction

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tomtom.com"
TIMEOUT = httpx.Timeout(30.0, connect=5.0)
SEARCH_COUNTRIES = "US,CA"

ROUTE_COUNT = 3
MAX_ALTERNATIVES = ROUTE_COUNT - 1  # DR-002: 4.7 s for 2 alternatives vs 11-19 s for 5
DUPLICATE_OVERLAP = 0.70  # routes sharing this much of their length count as the same route
VIA_OFFSETS = (0.15, 0.30)  # fallback waypoint offset, as a share of the straight-line distance
VIA_OFFSET_MIN_M, VIA_OFFSET_MAX_M = 24_000, 193_000  # 15 to 120 miles
VIA_MAX_SLOWDOWN = 1.6  # a fallback route may take at most 1.6x the fastest route's time

# The brief's load weight is cargo. Truck routing needs gross weight (D16 in the plan, DR-015).
TRACTOR_TRAILER_TARE_LB = 35_000
MAX_GROSS_LB = 80_000  # US federal gross vehicle weight limit
KG_PER_LB = 0.45359237


class TomTomError(Exception):
    """TomTom could not be reached or returned an unexpected error."""


class NoRouteError(TomTomError):
    """TomTom answered, but no road route exists between the places."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteData:
    points: list[LatLon]
    anchors: list[Anchor]
    length_m: float
    duration_s: float
    traffic_delay_s: float
    source: str  # "tomtom" or "via-waypoint"


def gross_weight_kg(load_lb: float) -> int:
    return round(min(load_lb + TRACTOR_TRAILER_TARE_LB, MAX_GROSS_LB) * KG_PER_LB)


class TomTomClient:
    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise TomTomError("TOMTOM_API_KEY is not configured")
        self._key = api_key
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def suggest(self, query: str, limit: int = 6) -> list[Place]:
        query = query.strip()
        if len(query) < 2:
            return []
        data = self._get(
            f"/search/2/search/{quote(query, safe='')}.json",
            {
                "typeahead": "true",
                "limit": limit,
                "countrySet": SEARCH_COUNTRIES,
                "idxSet": "Geo,Addr,PAD,POI",
            },
        )
        return [_place(r) for r in data.get("results", [])]

    def route_options(
        self, origin: LatLon, destination: LatLon, departure: datetime, load_lb: float
    ) -> list[RouteData]:
        """Up to three distinct truck routes, fastest first."""
        routes = self._calculate([origin, destination], departure, load_lb, MAX_ALTERNATIVES)
        distinct: list[RouteData] = []
        for route in routes:
            if _is_distinct(route, distinct):
                distinct.append(route)
        if len(distinct) < ROUTE_COUNT:
            distinct += self._via_routes(origin, destination, departure, load_lb, distinct)
        return distinct[:ROUTE_COUNT]

    def _via_routes(
        self,
        origin: LatLon,
        destination: LatLon,
        departure: datetime,
        load_lb: float,
        existing: list[RouteData],
    ) -> list[RouteData]:
        """Force extra routes through a waypoint offset sideways from the fastest route's midpoint."""
        fastest = existing[0]
        midpoint = point_at_fraction(fastest.points, 0.5)
        straight_m = haversine_m(origin, destination)
        found: list[RouteData] = []
        for share in VIA_OFFSETS:
            offset_m = min(max(share * straight_m, VIA_OFFSET_MIN_M), VIA_OFFSET_MAX_M)
            for side in (1, -1):
                if len(existing) + len(found) >= ROUTE_COUNT:
                    return found
                via = offset_point(origin, destination, midpoint, offset_m, side)
                try:
                    (candidate,) = self._calculate([origin, via, destination], departure, load_lb, 0)
                except NoRouteError:
                    continue
                candidate = replace(candidate, source="via-waypoint")
                if candidate.duration_s <= VIA_MAX_SLOWDOWN * fastest.duration_s and _is_distinct(
                    candidate, existing + found
                ):
                    found.append(candidate)
        if len(existing) + len(found) < ROUTE_COUNT:
            logger.warning("only %d distinct routes found", len(existing) + len(found))
        return found

    def _calculate(
        self, locations: list[LatLon], departure: datetime, load_lb: float, max_alternatives: int
    ) -> list[RouteData]:
        path = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in locations)
        data = self._get(
            f"/routing/1/calculateRoute/{path}/json",
            {
                "travelMode": "truck",
                "vehicleCommercial": "true",
                "vehicleWeight": gross_weight_kg(load_lb),
                "routeType": "fastest",
                "traffic": "true",
                "departAt": _depart_at(departure),
                "maxAlternatives": max_alternatives,
                "routeRepresentation": "polyline",
                "extendedRouteRepresentation": ["distance", "travelTime"],
            },
        )
        return [_route(r) for r in data.get("routes", [])]

    def _get(self, path: str, params: dict) -> dict:
        try:
            response = self._http.get(path, params={**params, "key": self._key})
        except httpx.HTTPError as exc:
            raise TomTomError(f"TomTom request failed: {exc.__class__.__name__}") from exc
        if response.status_code == 400:
            code = _error_code(response)
            if code in {"NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE", "CANNOT_RESTORE_BASEROUTE"}:
                raise NoRouteError(code)
        if response.status_code != 200:
            raise TomTomError(f"TomTom returned HTTP {response.status_code} ({_error_code(response)})")
        return response.json()


def _is_distinct(route: RouteData, others: list[RouteData]) -> bool:
    for other in others:
        # Every 5th point is plenty at ~100 m spacing and keeps the check fast.
        shared = max(
            overlap_fraction(route.points[::5], other.points),
            overlap_fraction(other.points[::5], route.points),
        )
        if shared >= DUPLICATE_OVERLAP:
            return False
    return True


def _depart_at(departure: datetime) -> str:
    if departure <= datetime.now(timezone.utc):
        return "now"  # live traffic instead of historical patterns
    return departure.isoformat(timespec="seconds")


def _route(raw: dict) -> RouteData:
    # Multi-leg routes repeat the joining point; `progress` indexes the concatenated legs.
    points = [(p["latitude"], p["longitude"]) for leg in raw["legs"] for p in leg["points"]]
    anchors = [
        Anchor(a["pointIndex"], a["distanceInMeters"], a["travelTimeInSeconds"])
        for a in raw.get("progress", [])
    ]
    summary = raw["summary"]
    return RouteData(
        points=points,
        anchors=anchors,
        length_m=summary["lengthInMeters"],
        duration_s=summary["travelTimeInSeconds"],
        traffic_delay_s=summary.get("trafficDelayInSeconds", 0),
        source="tomtom",
    )


def _place(raw: dict) -> Place:
    address = raw.get("address", {})
    label = address.get("freeformAddress", "")
    if raw.get("type") == "POI" and raw.get("poi", {}).get("name"):
        locality = ", ".join(
            part for part in (address.get("municipality"), address.get("countrySubdivision")) if part
        )
        label = f"{raw['poi']['name']}, {locality}" if locality else raw["poi"]["name"]
    position = raw["position"]
    return Place(label=label, lat=position["lat"], lon=position["lon"])


def _error_code(response: httpx.Response) -> str:
    try:
        return response.json().get("detailedError", {}).get("code", "unknown")
    except ValueError:
        return "unknown"
