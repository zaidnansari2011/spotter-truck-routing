"""One error shape for every API failure: {"code": ..., "message": ..., "fields"?: ...}."""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException, Throttled, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import exception_handler

from planner.services.openmeteo import WeatherError, WeatherRateLimited
from planner.services.tomtom import NoRouteError, TomTomError

logger = logging.getLogger(__name__)


class IPRateThrottle(SimpleRateThrottle):
    """Per-client-IP limits; the app has no accounts. Each view sets its own `scope`."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PlanThrottle(IPRateThrottle):
    scope = "plan"


class SuggestThrottle(IPRateThrottle):
    scope = "suggest"


class CorridorThrottle(IPRateThrottle):
    scope = "corridor"


def api_exception_handler(exc, context):
    if isinstance(exc, NoRouteError):
        return _error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "no_route",
            "No truck route exists between these places. Check that both are reachable by road.",
        )
    if isinstance(exc, TomTomError):
        return _error(
            status.HTTP_502_BAD_GATEWAY,
            "routing_unavailable",
            "The routing service is unavailable. Try again shortly.",
        )
    if isinstance(exc, WeatherRateLimited):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "weather_busy",
            "The free weather service's request limit is used up for now. Try again in a few minutes.",
        )
    if isinstance(exc, WeatherError):
        return _error(
            status.HTTP_502_BAD_GATEWAY,
            "weather_unavailable",
            "The weather service is unavailable. Try again shortly.",
        )

    response = exception_handler(exc, context)
    if response is None:
        # A bug, not a user error: log the traceback, keep internals out of the response.
        logger.exception("Unhandled API error", exc_info=exc)
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Something went wrong. Try again."
        )
    if isinstance(exc, ValidationError):
        response.data = {"code": "invalid_input", "message": _first_message(exc.detail), "fields": exc.detail}
    elif isinstance(exc, Throttled):
        wait = f" Try again in {exc.wait:.0f} seconds." if exc.wait else ""
        response.data = {"code": "rate_limited", "message": f"Too many requests.{wait}"}
    else:
        # Covers DRF exceptions and the Django ones DRF converts (Http404, PermissionDenied).
        code = (
            exc.default_code
            if isinstance(exc, APIException)
            else _STATUS_CODES.get(response.status_code, "error")
        )
        response.data = {"code": code, "message": str(response.data.get("detail", ""))}
    return response


_STATUS_CODES = {404: "not_found", 403: "permission_denied"}


def _error(status_code: int, code: str, message: str) -> Response:
    return Response({"code": code, "message": message}, status=status_code)


def _first_message(detail) -> str:
    while isinstance(detail, dict | list) and detail:
        detail = next(iter(detail.values())) if isinstance(detail, dict) else detail[0]
    return str(detail) if detail else "Invalid input."
