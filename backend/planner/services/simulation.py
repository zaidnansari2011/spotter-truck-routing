"""Forecast client wrapper that adds the demo storm on top of real forecasts (DR-026)."""

from __future__ import annotations

from collections.abc import Iterable

from planner.domain.forecast import HOUR_S, HourlySeries
from planner.domain.scenario import SimulatedStorm, overlay
from planner.services.openmeteo import Cell


class SimulatedWeather:
    """Same interface as OpenMeteoClient.hourly; real data is fetched and cached as usual."""

    def __init__(self, real, storm: SimulatedStorm):
        self._real = real
        self._storm = storm

    def hourly(self, cells: Iterable[Cell], start_ts: float, end_ts: float) -> dict[Cell, HourlySeries]:
        return {
            cell: self._with_storm(cell, s) for cell, s in self._real.hourly(cells, start_ts, end_ts).items()
        }

    def _with_storm(self, cell: Cell, s: HourlySeries) -> HourlySeries:
        wind, gust, rain, snow = [], [], [], []
        for k in range(len(s.wind_mph)):
            added = self._storm.conditions(cell, s.start_ts + k * HOUR_S)
            w, r, sn = overlay((s.wind_mph[k], s.rain_in[k], s.snowfall_in[k]), added)
            wind.append(w)
            rain.append(r)
            snow.append(sn)
            g = s.gust_mph[k]
            gust.append(None if g is None else max(g, added[0]))
        return HourlySeries(s.start_ts, wind, gust, rain, s.showers_in, snow)
