"""Read an hourly forecast at the moment the truck reaches a checkpoint (docs/decisions.md, DR-005).

Open-Meteo stamps each hourly value at the end of its hour for accumulated fields: rain, showers
and snowfall at 15:00 are totals for 14:00-15:00, and gusts are that hour's maximum. Wind speed is
an instant value. So at 14:20 we use the 15:00 accumulations and interpolate wind between 14:00
and 15:00.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geo import lerp

HOUR_S = 3600
# Open-Meteo reports precipitation in inches to 3 decimals; summing floats (0.01 + 0.09) can land
# just under a threshold, so sums are rounded back to the source precision.
PRECIP_DECIMALS = 3
# Interpolated wind is classified at the precision it is shown (1 decimal), so a checkpoint never
# reads "35.0 mph" next to Moderate.
WIND_DECIMALS = 1


@dataclass(frozen=True)
class HourlySeries:
    """Contiguous hourly values for one location. Index i is the stamp start_ts + i hours."""

    start_ts: int
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in: list[float | None]
    showers_in: list[float | None]
    snowfall_in: list[float | None]

    def value(self, values: list[float | None], stamp_ts: int) -> float | None:
        offset, remainder = divmod(stamp_ts - self.start_ts, HOUR_S)
        if remainder or not 0 <= offset < len(values):
            return None
        return values[offset]


@dataclass(frozen=True)
class WeatherAtEta:
    wind_mph: float
    gust_mph: float | None  # shown for context only; the risk table uses sustained wind
    rain_in_hr: float  # rain + showers, liquid only (snow is counted separately)
    snow_in_hr: float
    hour_ending_ts: int  # stamp of the hourly bucket used for rain, snow and gusts


def weather_at(series: HourlySeries, eta_ts: float) -> WeatherAtEta | None:
    """Conditions at `eta_ts`, or None when the forecast does not cover it (never assume calm)."""
    hour_start = math.floor(eta_ts / HOUR_S) * HOUR_S
    hour_end = math.ceil(eta_ts / HOUR_S) * HOUR_S

    wind_start = series.value(series.wind_mph, hour_start)
    wind_end = series.value(series.wind_mph, hour_end)
    rain = series.value(series.rain_in, hour_end)
    showers = series.value(series.showers_in, hour_end)
    snow = series.value(series.snowfall_in, hour_end)
    if None in (wind_start, wind_end, rain, showers, snow):
        return None

    fraction = (eta_ts - hour_start) / HOUR_S
    wind = round(lerp(wind_start, wind_end, fraction), WIND_DECIMALS)
    gust = series.value(series.gust_mph, hour_end)
    return WeatherAtEta(
        wind_mph=wind,
        # The hour's peak gust can sit below a wind interpolated from the next hour's value.
        gust_mph=None if gust is None else max(gust, wind),
        rain_in_hr=round(rain + showers, PRECIP_DECIMALS),
        snow_in_hr=round(snow, PRECIP_DECIMALS),
        hour_ending_ts=hour_end,
    )
