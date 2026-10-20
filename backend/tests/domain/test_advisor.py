from planner.domain.advisor import RouteCheckpoints, departure_options, safer_departure
from planner.domain.checkpoints import Checkpoint
from planner.domain.forecast import HOUR_S
from planner.domain.risk import RiskLevel

DEPARTURE = 1_800_000_000.0


def checkpoints(count: int, hours_apart: float) -> list[Checkpoint]:
    return [
        Checkpoint(
            index=i,
            mile=25.0 * i,
            lat=40.0,
            lon=-100.0 + i,
            elapsed_s=i * hours_apart * HOUR_S,
            eta_ts=DEPARTURE + i * hours_apart * HOUR_S,
            covered_miles=25.0,
        )
        for i in range(count)
    ]


def storm_until(hour: int, on_lon_below: float = 1e9):
    """Severe weather everywhere west of a longitude until `hour` hours after DEPARTURE."""

    def level_at(checkpoint: Checkpoint, eta_ts: float) -> RiskLevel:
        stormy = eta_ts < DEPARTURE + hour * HOUR_S and checkpoint.lon < on_lon_below
        return RiskLevel.SEVERE if stormy else RiskLevel.LOW

    return level_at


def test_one_option_per_offset_with_shifted_departure():
    routes = [RouteCheckpoints("A", 3 * HOUR_S, checkpoints(4, 1))]

    options = departure_options(routes, DEPARTURE, storm_until(0), offsets_h=range(3))

    assert [o.offset_h for o in options] == [0, 1, 2]
    assert [o.departure_ts - DEPARTURE for o in options] == [0, HOUR_S, 2 * HOUR_S]


def test_weather_is_read_at_the_shifted_arrival_times():
    seen = []

    def level_at(checkpoint, eta_ts):
        seen.append((checkpoint.index, eta_ts - DEPARTURE))
        return RiskLevel.LOW

    routes = [RouteCheckpoints("A", 2 * HOUR_S, checkpoints(3, 1))]
    departure_options(routes, DEPARTURE, level_at, offsets_h=[5])

    assert seen == [(0, 5 * HOUR_S), (1, 6 * HOUR_S), (2, 7 * HOUR_S)]


def test_suggests_the_earliest_departure_that_clears_the_storm():
    routes = [RouteCheckpoints("A", 3 * HOUR_S, checkpoints(4, 1))]

    options = departure_options(routes, DEPARTURE, storm_until(4), offsets_h=range(8))
    suggestion = safer_departure(options)

    # Each hour of waiting trims the storm; from +4 h the whole trip is clear.
    assert [o.recommended.severe_miles for o in options[:5]] == [100, 75, 50, 25, 0]
    assert suggestion.offset_h == 4  # not +1 h, which only trims 25 of 100 Severe miles
    assert suggestion.recommended.severe_miles == 0


def test_best_route_can_change_with_departure_time():
    # Route A (fast) crosses the storm at lon < -98.5; route B (slow) avoids it entirely.
    routes = [
        RouteCheckpoints("A", 3 * HOUR_S, checkpoints(4, 1)),
        RouteCheckpoints("B", 5 * HOUR_S, [c for c in checkpoints(4, 1) if c.lon >= -98.5]),
    ]

    options = departure_options(routes, DEPARTURE, storm_until(2, on_lon_below=-98.5), offsets_h=range(4))

    assert options[0].recommended.route_id == "B"
    assert options[3].recommended.route_id == "A"  # storm gone, the fastest route wins again


def test_no_suggestion_when_leaving_now_is_already_safest():
    routes = [RouteCheckpoints("A", HOUR_S, checkpoints(2, 1))]

    options = departure_options(routes, DEPARTURE, storm_until(0), offsets_h=range(5))

    assert safer_departure(options) is None


def test_no_suggestion_when_later_is_only_faster_not_safer():
    # Same risk at every offset: travel time must not count as "safer".
    routes = [RouteCheckpoints("A", HOUR_S, checkpoints(2, 1))]

    options = departure_options(routes, DEPARTURE, lambda c, t: RiskLevel.MODERATE, offsets_h=range(3))

    assert safer_departure(options) is None


def test_empty_options():
    assert safer_departure([]) is None


def test_later_departures_keep_the_rest_breaks_in_arrival_times():
    # A checkpoint reached after a rest has eta well beyond its driving time; shifts must use eta.
    cps = checkpoints(2, 1)
    rested = [cps[0], Checkpoint(**{**cps[1].__dict__, "eta_ts": DEPARTURE + 11 * HOUR_S})]
    seen = []

    def level_at(checkpoint, eta_ts):
        seen.append(eta_ts - DEPARTURE)
        return RiskLevel.LOW

    departure_options([RouteCheckpoints("A", 11 * HOUR_S, rested)], DEPARTURE, level_at, offsets_h=[2])

    assert seen == [2 * HOUR_S, 13 * HOUR_S]
