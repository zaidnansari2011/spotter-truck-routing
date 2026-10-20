from datetime import datetime, timedelta, timezone

from rest_framework import serializers

from planner.domain.geo import haversine_m

MAX_LOAD_LB = 80_000  # US federal gross limit; no legal cargo load exceeds it
PAST_GRACE = timedelta(minutes=15)  # form filled in a few minutes ago still counts as "now"
MAX_DEPARTURE_AHEAD = timedelta(days=7)  # forecasts beyond a week are too unreliable to rank routes on
MIN_TRIP_M = 1_000


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.DateTimeField(
        help_text="ISO 8601 with a UTC offset, e.g. 2026-10-22T08:00:00-05:00"
    )
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB, help_text="Cargo weight in pounds")

    def validate_departure(self, value: datetime) -> datetime:
        # DRF makes naive input aware using TIME_ZONE, so check the raw text for an explicit offset.
        raw = str(self.initial_data.get("departure", ""))
        if not (raw.endswith("Z") or "+" in raw[10:] or "-" in raw[10:]):
            raise serializers.ValidationError("Include a UTC offset, e.g. 2026-10-22T08:00:00-05:00.")
        now = datetime.now(timezone.utc)
        if value < now - PAST_GRACE:
            raise serializers.ValidationError("Departure cannot be in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Departure must be within the next 7 days.")
        return value

    def validate(self, attrs):
        origin, destination = attrs["origin"], attrs["destination"]
        if haversine_m((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"])) < MIN_TRIP_M:
            raise serializers.ValidationError({"destination": "Origin and destination are the same place."})
        return attrs


class SuggestQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=120, allow_blank=True)


MAX_CORRIDOR_POINTS = 1_000


class CorridorRequestSerializer(serializers.Serializer):
    points = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        min_length=1,
        max_length=MAX_CORRIDOR_POINTS,
        help_text="Grid points as [lon, lat], as returned in the plan's corridor.points",
    )
    start = serializers.DateTimeField(help_text="Hour 0 of the slider, ISO 8601 with a UTC offset")
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_points(self, value):
        for lon, lat in value:
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise serializers.ValidationError("Each point must be [lon, lat] within valid ranges.")
        return value

    def validate_start(self, value: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if not now - timedelta(hours=1) <= value <= now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError("Start must be between now and 7 days ahead.")
        return value
