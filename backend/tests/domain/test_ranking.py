import pytest

from planner.domain.ranking import format_duration, rank, score_route
from planner.domain.risk import RiskLevel

LOW, MOD, HIGH, SEVERE, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)
HOUR = 3600


def route(route_id, hours, **miles):
    """A route with the given miles per level; the rest of `total` (default 400) is Low."""
    total = miles.pop("total", 400)
    unknown = miles.pop("unknown", 0)
    levels = {"nt": NT, "severe": SEVERE, "high": HIGH, "mod": MOD}
    segments = [(m, levels[name]) for name, m in miles.items()]
    segments.append((total - sum(miles.values()) - unknown, LOW))
    if unknown:
        segments.append((unknown, None))
    return score_route(route_id, hours * HOUR, segments)


def test_score_aggregates_miles_and_weights_average_by_distance():
    score = score_route("A", HOUR, [(12.5, LOW), (25, HIGH), (12.5, MOD)])

    assert score.miles_by_level[HIGH] == 25
    assert score.distance_mi == 50
    assert score.avg_risk == pytest.approx((0 * 12.5 + 2 * 25 + 1 * 12.5) / 50)


def test_unknown_miles_are_excluded_from_the_average_but_counted_in_distance():
    score = score_route("A", HOUR, [(50, HIGH), (50, None)])

    assert score.avg_risk == 2
    assert score.unknown_miles == 50
    assert score.distance_mi == 100


def test_route_with_no_forecast_at_all_has_no_average():
    assert score_route("A", HOUR, [(100, None)]).avg_risk is None


@pytest.mark.parametrize(
    ("a", "b", "criterion"),
    [
        # each criterion decides only when every earlier one ties
        (route("A", 9, severe=10, high=50), route("B", 6, severe=20), "severe_miles"),
        (route("A", 9, high=10, mod=200), route("B", 6, high=20), "high_miles"),
        (route("A", 9, mod=25), route("B", 6, mod=100), "avg_risk"),
        (route("A", 6, mod=25), route("B", 9, mod=25), "duration"),
        (route("A", 9, nt=0, severe=50), route("B", 6, nt=10), "no_travel_miles"),
    ],
)
def test_each_criterion_decides_in_order(a, b, criterion):
    ranking = rank([b, a])

    assert ranking.recommended_id == "A"
    assert ranking.comparisons[0].decided_by == criterion


def test_no_travel_ranks_worse_than_any_severe_miles():
    # Read literally, the brief would pick A (0 Severe miles) despite 10 No Travel miles.
    a = route("A", 6, nt=10)
    b = route("B", 7, severe=50)

    ranking = rank([a, b])

    assert ranking.recommended_id == "B"
    assert ranking.comparisons[0].reason == "Fewest No Travel miles: 0 mi vs 10 mi on Route A"


def test_average_risk_differences_hidden_by_rounding_let_travel_time_decide():
    # docs/decisions.md DR-008: same 25 rainy miles, B is 10 miles longer and 1 h 15 min slower.
    a = route("A", 6 + 10 / 60, mod=25, total=400)
    b = route("B", 7 + 25 / 60, mod=25, total=410)
    assert a.avg_risk == pytest.approx(0.0625)
    assert b.avg_risk == pytest.approx(0.0610, abs=1e-4)

    ranking = rank([b, a])

    assert ranking.recommended_id == "A"
    assert ranking.comparisons[0].decided_by == "duration"
    assert ranking.comparisons[0].reason == "Shortest travel time: 6 h 10 min vs 7 h 25 min on Route B"


def test_visible_average_risk_difference_beats_travel_time():
    a = route("A", 9, mod=84)  # 0.21
    b = route("B", 6, mod=80)  # 0.20

    ranking = rank([a, b])

    assert ranking.recommended_id == "B"
    assert ranking.comparisons[0].decided_by == "avg_risk"


def test_mile_differences_below_display_precision_tie():
    a = route("A", 7, severe=25.04)
    b = route("B", 6, severe=25.0)

    assert rank([a, b]).recommended_id == "B"


def test_travel_times_in_the_same_minute_tie():
    # Seconds apart would otherwise give "Shortest travel time: 1 h vs 1 h".
    a = score_route("A", HOUR + 10, [(100, LOW)])
    b = score_route("B", HOUR, [(100, LOW)])

    ranking = rank([a, b])

    assert ranking.recommended_id == "A"  # input order kept
    assert ranking.comparisons[0].decided_by == "tie"


def test_full_tie_keeps_input_order():
    a = route("A", 6)
    b = route("B", 6)

    ranking = rank([a, b])

    assert ranking.order == ["A", "B"]
    assert ranking.comparisons[0].decided_by == "tie"


def test_order_lists_every_route_best_first():
    ranking = rank([route("A", 6, severe=5), route("B", 8), route("C", 7)])

    assert ranking.order == ["C", "B", "A"]


def test_tradeoff_note_when_a_losing_route_is_much_faster():
    safe = route("A", 9, high=20)
    fast = route("B", 7, severe=30)

    ranking = rank([fast, safe])

    assert ranking.recommended_id == "A"
    assert ranking.tradeoff.faster_id == "B"
    assert ranking.tradeoff.saving_s == 2 * HOUR
    assert ranking.tradeoff.note == (
        "Route B is 2 h faster but has 30 Severe miles, average risk 0.23 "
        "(vs 20 High miles, average risk 0.10 on Route A)."
    )


def test_tradeoff_picks_the_fastest_of_several_faster_routes():
    ranking = rank([route("A", 9), route("B", 8, severe=5), route("C", 7, severe=10)])

    assert ranking.tradeoff.faster_id == "C"


@pytest.mark.parametrize(("minutes_faster", "expected"), [(29, False), (30, True)])
def test_tradeoff_threshold_is_30_minutes(minutes_faster, expected):
    safe = route("A", 9)
    fast = route("B", 9 - minutes_faster / 60, severe=10)

    assert (rank([safe, fast]).tradeoff is not None) is expected


def test_no_tradeoff_when_recommended_route_is_fastest():
    assert rank([route("A", 6), route("B", 9, severe=10)]).tradeoff is None


def test_all_no_travel_flag():
    assert rank([route("A", 6, nt=5), route("B", 7, nt=1)]).all_no_travel is True
    assert rank([route("A", 6, nt=5), route("B", 7)]).all_no_travel is False


def test_route_without_any_forecast_ranks_after_scored_routes():
    # With no forecast, A has 0 known High miles; that must not beat B's 100 real High miles.
    blind = score_route("A", 5 * HOUR, [(400, None)])
    scored = route("B", 9, high=100)

    ranking = rank([blind, scored])

    assert ranking.recommended_id == "B"
    assert ranking.comparisons[0].decided_by == "forecast"
    assert ranking.comparisons[0].reason == "Forecast available: yes vs no on Route A"
    assert ranking.tradeoff.note.endswith(
        "but has average risk n/a (vs 100 High miles, average risk 0.50 on Route B)."
    )


def test_partial_forecast_gaps_still_rank_on_known_miles():
    # A trip running past the forecast horizon near the end is still compared normally.
    a = route("A", 9, high=20, unknown=30)
    b = route("B", 8, severe=10)

    ranking = rank([a, b])

    assert ranking.recommended_id == "A"
    assert ranking.comparisons[0].decided_by == "severe_miles"


def test_rank_needs_at_least_one_route():
    with pytest.raises(ValueError):
        rank([])


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0 min"), (45 * 60, "45 min"), (2 * HOUR, "2 h"), (HOUR + 15 * 60, "1 h 15 min"), (3599.7, "1 h")],
)
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text
