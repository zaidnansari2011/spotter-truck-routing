import pytest

from planner.domain.hos import rest_s, wall_clock

H = 3600


@pytest.mark.parametrize(
    ("driving_h", "elapsed_h"),
    [
        (0, 0),
        (5, 5),
        (8, 8),  # finishing at 8 h needs no break
        (8.5, 9),  # 30 min break after 8 h
        (11, 11.5),  # a full driving day: 8 h + break + 3 h
        (12, 22.5),  # 11.5 h day + 10 h off + 1 h
        (19, 29.5),  # second day: 8 h, no break yet (21.5 + 8)
        (20, 31),  # second day past 8 h: break again
        (22, 33),  # exactly two full days, no rest needed after the last one
        (33, 54.5),  # three full days
    ],
)
def test_wall_clock_adds_breaks_and_off_duty(driving_h, elapsed_h):
    assert wall_clock(driving_h * H) == pytest.approx(elapsed_h * H)


def test_wall_clock_never_goes_backwards():
    values = [wall_clock(m * 60) for m in range(0, 60 * 40)]

    assert values == sorted(values)


def test_rest_time_is_the_difference():
    assert rest_s(12 * H) == pytest.approx(10.5 * H)
    assert rest_s(4 * H) == 0


def test_negative_driving_is_zero():
    assert wall_clock(-5) == 0
