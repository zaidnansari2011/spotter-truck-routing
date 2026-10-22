"""Route scoring and recommendation (docs/decisions.md, DR-007 and DR-008).

Routes are ordered by the brief's preferences, with No Travel miles compared first:

    no travel miles, severe miles, high miles, average risk, travel time

A route with no forecast at all ranks after every route that has one: missing data must never
look safer than known risk.

Miles are compared at 1 decimal, average risk at 2 decimals and travel time in whole minutes,
the precision the UI shows, so every recommendation can be explained from the numbers on screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .risk import RiskLevel

MILES_DECIMALS = 1
AVG_RISK_DECIMALS = 2
MINUTE_S = 60
TRADEOFF_MIN_SAVING_S = 30 * MINUTE_S

CRITERIA = ("forecast", "no_travel_miles", "severe_miles", "high_miles", "avg_risk", "duration")
CRITERION_LABELS = {
    "forecast": "Forecast available",
    "no_travel_miles": "Fewest No Travel miles",
    "severe_miles": "Fewest Severe miles",
    "high_miles": "Fewest High miles",
    "avg_risk": "Lowest average risk",
    "duration": "Shortest travel time",
    "tie": "Identical on every criterion",
}


@dataclass(frozen=True)
class RouteScore:
    route_id: str
    duration_s: float
    distance_mi: float
    miles_by_level: dict[RiskLevel, float]
    unknown_miles: float  # checkpoints with no forecast at their ETA
    avg_risk: float | None  # distance-weighted over miles with a forecast; None if there are none

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]

    def sort_key(self) -> tuple[float, ...]:
        avg = math.inf if self.avg_risk is None else round(self.avg_risk, AVG_RISK_DECIMALS)
        return (
            0 if self.avg_risk is not None else 1,
            round(self.no_travel_miles, MILES_DECIMALS),
            round(self.severe_miles, MILES_DECIMALS),
            round(self.high_miles, MILES_DECIMALS),
            avg,
            round(self.duration_s / MINUTE_S),
        )


@dataclass(frozen=True)
class Comparison:
    """Why the recommended route beat one other route."""

    other_id: str
    decided_by: str  # one of CRITERIA, or "tie"
    reason: str


@dataclass(frozen=True)
class Tradeoff:
    """A faster route that lost on risk; shown to the driver, never overrides the pick."""

    faster_id: str
    saving_s: float
    note: str


@dataclass(frozen=True)
class Ranking:
    order: list[str]  # route ids, best first
    recommended_id: str
    comparisons: list[Comparison]
    tradeoff: Tradeoff | None
    all_no_travel: bool  # every route crosses No Travel conditions


def score_route(
    route_id: str, duration_s: float, segments: list[tuple[float, RiskLevel | None]]
) -> RouteScore:
    """Aggregate (covered_miles, level) per checkpoint. A None level means no forecast."""
    miles_by_level = dict.fromkeys(RiskLevel, 0.0)
    unknown = 0.0
    for miles, level in segments:
        if level is None:
            unknown += miles
        else:
            miles_by_level[level] += miles

    known = sum(miles_by_level.values())
    avg = sum(level * miles for level, miles in miles_by_level.items()) / known if known > 0 else None
    return RouteScore(
        route_id=route_id,
        duration_s=duration_s,
        distance_mi=known + unknown,
        miles_by_level=miles_by_level,
        unknown_miles=unknown,
        avg_risk=avg,
    )


def rank(scores: list[RouteScore]) -> Ranking:
    if not scores:
        raise ValueError("need at least one route to rank")

    # sorted() is stable, so full ties keep the routing API's order (fastest first).
    ordered = sorted(scores, key=RouteScore.sort_key)
    best = ordered[0]
    return Ranking(
        order=[s.route_id for s in ordered],
        recommended_id=best.route_id,
        comparisons=[_compare(best, other) for other in ordered[1:]],
        tradeoff=_tradeoff(best, ordered[1:]),
        all_no_travel=all(s.no_travel_miles > 0 for s in scores),
    )


def _compare(best: RouteScore, other: RouteScore) -> Comparison:
    for criterion, mine, theirs in zip(CRITERIA, best.sort_key(), other.sort_key(), strict=True):
        if mine != theirs:
            reason = (
                f"{CRITERION_LABELS[criterion]}: {_fmt(criterion, mine)} vs "
                f"{_fmt(criterion, theirs)} on Route {other.route_id}"
            )
            return Comparison(other.route_id, criterion, reason)
    return Comparison(other.route_id, "tie", f"{CRITERION_LABELS['tie']} with Route {other.route_id}")


def _tradeoff(best: RouteScore, others: list[RouteScore]) -> Tradeoff | None:
    faster = [o for o in others if best.duration_s - o.duration_s >= TRADEOFF_MIN_SAVING_S]
    if not faster:
        return None
    quickest = min(faster, key=lambda s: s.duration_s)
    saving = best.duration_s - quickest.duration_s
    note = (
        f"Route {quickest.route_id} is {format_duration(saving)} faster but has "
        f"{_risk_summary(quickest)} (vs {_risk_summary(best)} on Route {best.route_id})."
    )
    return Tradeoff(quickest.route_id, saving, note)


def _risk_summary(score: RouteScore) -> str:
    parts = []
    for label, miles in (
        ("No Travel", score.no_travel_miles),
        ("Severe", score.severe_miles),
        ("High", score.high_miles),
    ):
        if round(miles, MILES_DECIMALS) > 0:
            parts.append(f"{_fmt_miles(miles)} {label} miles")
    avg = "n/a" if score.avg_risk is None else f"{score.avg_risk:.2f}"
    parts.append(f"average risk {avg}")
    return ", ".join(parts)


def _fmt(criterion: str, value: float) -> str:
    if criterion == "forecast":
        return "yes" if value == 0 else "no"
    if criterion == "duration":
        return format_duration(value * MINUTE_S)
    if criterion == "avg_risk":
        return "n/a" if math.isinf(value) else f"{value:.2f}"
    return f"{_fmt_miles(value)} mi"


def _fmt_miles(miles: float) -> str:
    return f"{miles:,.1f}".removesuffix(".0")


def format_duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    return f"{hours} h" if hours else f"{minutes} min"
