"""Departure-time advisor (docs/decisions.md DR-022).

Re-scores the same routes as if the truck left later. Route geometry and driving times are reused,
only the time each checkpoint is reached moves, so its forecast changes. The suggestion is the
safest departure in the window (the earliest one if several tie), and only when it is strictly
safer than leaving as planned.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .checkpoints import Checkpoint
from .forecast import HOUR_S
from .ranking import RouteScore, rank, score_route
from .risk import RiskLevel

ADVISOR_HOURS = range(25)  # leave now or up to 24 hours later

LevelAt = Callable[[Checkpoint, float], RiskLevel | None]


@dataclass(frozen=True)
class RouteCheckpoints:
    route_id: str
    duration_s: float
    checkpoints: list[Checkpoint]


@dataclass(frozen=True)
class DepartureOption:
    offset_h: int
    departure_ts: float
    recommended: RouteScore


def departure_options(
    routes: list[RouteCheckpoints],
    departure_ts: float,
    level_at: LevelAt,
    offsets_h: Iterable[int] = ADVISOR_HOURS,
) -> list[DepartureOption]:
    """For each departure offset, the route the ranking would recommend and its score."""
    options = []
    for offset in offsets_h:
        start = departure_ts + offset * HOUR_S
        scores = [
            score_route(
                r.route_id,
                r.duration_s,
                [(c.covered_miles, level_at(c, start + c.elapsed_s)) for c in r.checkpoints],
            )
            for r in routes
        ]
        best_id = rank(scores).recommended_id
        best = next(s for s in scores if s.route_id == best_id)
        options.append(DepartureOption(offset_h=offset, departure_ts=start, recommended=best))
    return options


def safer_departure(options: list[DepartureOption]) -> DepartureOption | None:
    """The safest departure in the window, earliest on ties, if it beats leaving as planned.

    Safety compares everything the ranking compares except travel time (forecast availability,
    No Travel, Severe and High miles, average risk at display precision). Waiting one hour to
    trim a storm is not suggested when waiting four avoids it entirely.
    """
    if not options:
        return None
    safest = min(options, key=lambda o: (_risk_key(o.recommended), o.offset_h))
    if _risk_key(safest.recommended) < _risk_key(options[0].recommended):
        return safest
    return None


def _risk_key(score: RouteScore) -> tuple[float, ...]:
    return score.sort_key()[:-1]  # drop travel time
