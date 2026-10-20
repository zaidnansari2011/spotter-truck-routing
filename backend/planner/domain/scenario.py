"""Simulated storm for demonstrations (docs/decisions.md DR-026).

Real weather is often calm, which hides most of the app's behaviour. In demo mode a synthetic
storm is laid over the real forecast (the worse value wins at each point): No Travel winds and
heavy snow at the centre, fading with distance and dissipating over STORM_LIFETIME_H hours.
The UI labels every page that uses it as simulated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .forecast import HOUR_S
from .geo import LatLon, haversine_m

STORM_RADIUS_M = 180_000
STORM_LIFETIME_H = 14
PEAK_WIND_MPH = 62.0
PEAK_SNOW_IN_HR = 2.6
PEAK_RAIN_IN_HR = 0.0  # a winter storm: snow, not rain, so the two never double count


@dataclass(frozen=True)
class SimulatedStorm:
    center: LatLon
    start_ts: float  # when the storm is at full strength

    def conditions(self, point: LatLon, ts: float) -> tuple[float, float, float]:
        """(wind mph, rain in/hr, snow in/hr) the storm adds at a point and time."""
        strength = self._strength(point, ts)
        return PEAK_WIND_MPH * strength, PEAK_RAIN_IN_HR * strength, PEAK_SNOW_IN_HR * strength

    def _strength(self, point: LatLon, ts: float) -> float:
        hours = (ts - self.start_ts) / HOUR_S
        if hours < -2 or hours > STORM_LIFETIME_H:
            return 0.0
        # Builds over the 2 hours before the start, then fades linearly to nothing.
        in_time = (hours + 2) / 2 if hours < 0 else 1 - hours / STORM_LIFETIME_H
        distance = haversine_m(point, self.center)
        if distance >= STORM_RADIUS_M:
            return 0.0
        in_space = math.cos(distance / STORM_RADIUS_M * math.pi / 2) ** 2
        return in_time * in_space


def overlay(
    real: tuple[float | None, float | None, float | None], added: tuple[float, float, float]
) -> tuple[float | None, float | None, float | None]:
    """The worse of real and simulated values; a missing real value stays missing."""
    return tuple(None if r is None else max(r, a) for r, a in zip(real, added, strict=True))
