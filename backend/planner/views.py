import hashlib
from dataclasses import asdict

from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.request import Request
from rest_framework.response import Response

from planner.api_errors import CorridorThrottle, PlanThrottle, SuggestThrottle
from planner.serializers import (
    CorridorRequestSerializer,
    PlaceSerializer,
    PlanRequestSerializer,
    SuggestQuerySerializer,
)
from planner.services import corridor, trip

SUGGEST_CACHE_SECONDS = 24 * 3600


@extend_schema(responses=inline_serializer("Health", {"status": serializers.CharField()}))
@api_view(["GET"])
def health(request: Request) -> Response:
    return Response({"status": "ok"})


@extend_schema(
    parameters=[OpenApiParameter("q", str, description="Partial place name or address (US and Canada)")],
    responses=PlaceSerializer(many=True),
)
@api_view(["GET"])
@throttle_classes([SuggestThrottle])
def suggest(request: Request) -> Response:
    query = SuggestQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    text = " ".join(query.validated_data["q"].split()).lower()
    if len(text) < 2:
        return Response([])
    # Hashed so spaces and commas in queries are safe for every cache backend.
    key = "suggest:v2:" + hashlib.sha256(text.encode()).hexdigest()
    places = cache.get(key)
    if places is None:
        places = [asdict(p) for p in trip.tomtom_client().suggest(text)]
        cache.set(key, places, SUGGEST_CACHE_SECONDS)
    return Response(places)


@extend_schema(
    request=PlanRequestSerializer,
    responses=inline_serializer(
        "Plan", {"routes": serializers.ListField(), "rankings": serializers.DictField()}
    ),
    description=(
        "Three route options with checkpoints, forecast risk and a recommendation for each sampling interval."
    ),
)
@api_view(["POST"])
@throttle_classes([PlanThrottle])
def plan(request: Request) -> Response:
    body = PlanRequestSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    data = body.validated_data
    result = trip.plan_trip(
        trip.TripRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(data["destination"]["lat"], data["destination"]["lon"]),
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_mi=data["interval_mi"],
        )
    )
    return Response(result)


@extend_schema(
    request=CorridorRequestSerializer,
    responses=inline_serializer(
        "CorridorFrames",
        {
            "hours": serializers.ListField(child=serializers.IntegerField()),
            "risk": serializers.ListField(),
            "risk_load": serializers.ListField(),
            "wind": serializers.ListField(),
            "rain": serializers.ListField(),
            "snow": serializers.ListField(),
        },
    ),
    description=(
        "Hourly weather for the heatmap grid, hours 0 to 48 from `start`. One row per point, "
        "one value per hour: risk x100, wind mph, rain and snow in hundredths of an inch per hour."
    ),
)
@api_view(["POST"])
@throttle_classes([CorridorThrottle])
def corridor_weather(request: Request) -> Response:
    body = CorridorRequestSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    data = body.validated_data
    points = [(lat, lon) for lon, lat in data["points"]]
    return Response(corridor.corridor_frames(points, data["start"].timestamp(), data["load_lb"]))
