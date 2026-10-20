"""Weather risk classification: the brief's risk table plus its load rules.

Band edges (docs/decisions.md, DR-006): each band includes its lower bound and excludes its upper
bound. No Travel follows the table's own symbols: wind ">= 55" is inclusive, rain "> 1.00" and
snow "> 3.0" are exclusive, so exactly 1.00 in/hr rain and 3.0 in/hr snow are Severe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    """Ordered risk levels. The integer value is the score used for average risk."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}


@dataclass(frozen=True)
class Thresholds:
    """Lower bounds of Moderate, High and Severe, plus the No Travel cut-off."""

    moderate: float
    high: float
    severe: float
    no_travel: float
    no_travel_inclusive: bool

    def classify(self, value: float) -> RiskLevel:
        if value > self.no_travel or (self.no_travel_inclusive and value == self.no_travel):
            return RiskLevel.NO_TRAVEL
        if value >= self.severe:
            return RiskLevel.SEVERE
        if value >= self.high:
            return RiskLevel.HIGH
        if value >= self.moderate:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def index(self, value: float) -> float:
        """Continuous 0..4 score for smooth heatmaps, with floor(index) == classify(value)."""
        level = self.classify(value)
        if level == RiskLevel.NO_TRAVEL:
            return 4.0
        edges = (0.0, self.moderate, self.high, self.severe, self.no_travel)
        lower, upper = edges[level], edges[level + 1]
        fraction = (value - lower) / (upper - lower)
        # The Severe band can include its upper edge (rain 1.00, snow 3.0); keep it below 4.
        return level + min(max(fraction, 0.0), 0.999)


WIND_MPH = Thresholds(moderate=25, high=35, severe=45, no_travel=55, no_travel_inclusive=True)
RAIN_IN_HR = Thresholds(moderate=0.10, high=0.25, severe=0.50, no_travel=1.00, no_travel_inclusive=False)
SNOW_IN_HR = Thresholds(moderate=0.5, high=1.0, severe=2.0, no_travel=3.0, no_travel_inclusive=False)

# Load rules. ">= 55 mph is No Travel for any load" is already the wind table's top band.
NO_TRAVEL_LOAD_LB = 30_000  # 45-54 mph wind with a load over this is No Travel
SEVERE_LOAD_LB = 40_000  # 35-44 mph wind with a load over this is Severe


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    weather_level: RiskLevel  # before load rules
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    factors: tuple[str, ...]  # conditions at the final level, e.g. ("wind", "rain"); empty when Low
    load_rule: str | None  # human-readable rule that raised the level, if any


def load_rule_level(wind: RiskLevel, load_lb: float) -> tuple[RiskLevel, str] | None:
    """The level a load rule forces for this wind band, or None if no rule applies."""
    if wind == RiskLevel.SEVERE and load_lb > NO_TRAVEL_LOAD_LB:
        return RiskLevel.NO_TRAVEL, "45-54 mph wind with a load over 30,000 lb"
    if wind == RiskLevel.HIGH and load_lb > SEVERE_LOAD_LB:
        return RiskLevel.SEVERE, "35-44 mph wind with a load over 40,000 lb"
    return None


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> RiskAssessment:
    """Worst of wind, rain and snow, then load rules, which can only raise the level."""
    if load_lb < 0:
        raise ValueError("load_lb must be >= 0")

    levels = {
        "wind": WIND_MPH.classify(wind_mph),
        "rain": RAIN_IN_HR.classify(rain_in_hr),
        "snow": SNOW_IN_HR.classify(snow_in_hr),
    }
    weather_level = max(levels.values())
    level, load_rule = weather_level, None

    forced = load_rule_level(levels["wind"], load_lb)
    if forced and forced[0] > weather_level:
        level, load_rule = forced

    if load_rule:
        factors: tuple[str, ...] = ("wind",)
    elif level > RiskLevel.LOW:
        factors = tuple(name for name, lvl in levels.items() if lvl == level)
    else:
        factors = ()

    return RiskAssessment(
        level=level,
        weather_level=weather_level,
        wind=levels["wind"],
        rain=levels["rain"],
        snow=levels["snow"],
        factors=factors,
        load_rule=load_rule,
    )


def risk_index(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float | None = None) -> float:
    """Continuous 0..4 risk for heatmaps. floor() of it always equals the discrete level.

    Without load_lb this is the weather-only index (the risk table alone).
    """
    index = max(WIND_MPH.index(wind_mph), RAIN_IN_HR.index(rain_in_hr), SNOW_IN_HR.index(snow_in_hr))
    if load_lb is not None:
        forced = load_rule_level(WIND_MPH.classify(wind_mph), load_lb)
        if forced:
            index = max(index, float(forced[0]))
    return index
