"""Hours-of-service rest breaks for property-carrying drivers (FMCSA, docs/decisions.md DR-025).

A driver may drive 8 hours before a 30-minute break, 11 hours in total, and then needs 10
consecutive hours off duty. With no other on-duty work, a day is 8 h driving, a 30 min break and
3 h driving: 11.5 h on duty, inside the 14-hour window. The 60/70-hour weekly limits are not
modelled; a single trip in this app does not approach them.
"""

from __future__ import annotations

import math

HOUR_S = 3600
DRIVING_BEFORE_BREAK_S = 8 * HOUR_S
BREAK_S = 30 * 60
DRIVING_PER_DAY_S = 11 * HOUR_S
OFF_DUTY_S = 10 * HOUR_S
DAY_CYCLE_S = DRIVING_PER_DAY_S + BREAK_S + OFF_DUTY_S


def wall_clock(driving_s: float) -> float:
    """Elapsed time since departure once `driving_s` of driving is done, rests included.

    A rest is only taken before more driving: finishing exactly at 8 h or 11 h needs no break.
    """
    if driving_s <= 0:
        return 0.0
    full_days = math.ceil(driving_s / DRIVING_PER_DAY_S) - 1
    today = driving_s - full_days * DRIVING_PER_DAY_S
    break_today = BREAK_S if today > DRIVING_BEFORE_BREAK_S else 0
    return full_days * DAY_CYCLE_S + today + break_today


def rest_s(driving_s: float) -> float:
    """Total break and off-duty time added to a trip of `driving_s` driving."""
    return wall_clock(driving_s) - driving_s
