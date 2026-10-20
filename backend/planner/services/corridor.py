"""Hourly heatmap frames for the corridor grid: 49 frames covering hours 0 to 48 (DR-019).

Values are small integers to keep the payload compact (the browser divides them back):
risk indices x100 (0-400), wind in whole mph, rain and snow in hundredths of an inch per hour.
Hours without a forecast are null, never zero.
"""

from __future__ import annotations

import math

from planner.domain.forecast import HOUR_S, HourlySeries
from planner.domain.geo import LatLon
from planner.domain.risk import risk_index
from planner.services import trip
from planner.services.openmeteo import snap

FRAME_COUNT = 49  # hour 0 through hour 48


def corridor_frames(points: list[LatLon], start_ts: float, load_lb: float) -> dict:
    start = math.floor(start_ts / HOUR_S) * HOUR_S
    hours = [start + k * HOUR_S for k in range(FRAME_COUNT)]
    cells = [snap(lat, lon) for lat, lon in points]
    series = trip.openmeteo_client().hourly(cells, hours[0], hours[-1])

    frames: dict[str, list[list[int | None]]] = {
        key: [] for key in ("risk", "risk_load", "wind", "rain", "snow")
    }
    for cell in cells:
        rows = [_frame_values(series[cell], ts, load_lb) for ts in hours]
        for key, column in zip(frames, zip(*rows, strict=True), strict=True):
            frames[key].append(list(column))
    return {"hours": hours, **frames}


def _frame_values(s: HourlySeries, ts: int, load_lb: float) -> tuple[int | None, ...]:
    wind = s.value(s.wind_mph, ts)
    rain = s.value(s.rain_in, ts)
    showers = s.value(s.showers_in, ts)
    snow = s.value(s.snowfall_in, ts)
    if None in (wind, rain, showers, snow):
        return (None,) * 5
    liquid = round(rain + showers, 3)
    return (
        # floor keeps floor(value / 100) equal to the discrete level (DR-013)
        math.floor(risk_index(wind, liquid, snow) * 100),
        math.floor(risk_index(wind, liquid, snow, load_lb) * 100),
        round(wind),
        round(liquid * 100),
        round(snow * 100),
    )
