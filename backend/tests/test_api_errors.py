import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import override_settings

from planner.api_errors import api_exception_handler
from planner.services import trip
from planner.services.openmeteo import OpenMeteoClient, WeatherError
from planner.services.tomtom import TomTomClient, TomTomError


def test_upstream_failures_are_logged_with_their_reason(caplog):
    response = api_exception_handler(WeatherError("Open-Meteo returned HTTP 504: unknown"), {})

    assert response.status_code == 502
    assert "HTTP 504" not in str(response.data)  # the reason stays out of the response
    assert "Upstream failure: Open-Meteo returned HTTP 504" in caplog.text


def test_unexpected_errors_are_logged_and_hidden(caplog):
    response = api_exception_handler(KeyError("secret internals"), {})

    assert response.status_code == 500
    assert response.data == {"code": "internal_error", "message": "Something went wrong. Try again."}
    assert "Unhandled API error" in caplog.text


@pytest.mark.parametrize(
    ("exc", "status", "code"), [(Http404(), 404, "not_found"), (PermissionDenied(), 403, "permission_denied")]
)
def test_django_exceptions_use_the_same_shape(exc, status, code):
    response = api_exception_handler(exc, {})

    assert response.status_code == status
    assert response.data["code"] == code
    assert set(response.data) == {"code", "message"}


@pytest.mark.real_client_factories
def test_client_factories_build_configured_clients():
    trip.tomtom_client.cache_clear()
    trip.openmeteo_client.cache_clear()
    try:
        with override_settings(TOMTOM_API_KEY="configured-key"):
            assert isinstance(trip.tomtom_client(), TomTomClient)
            assert trip.tomtom_client() is trip.tomtom_client()  # one shared HTTP connection pool
        assert isinstance(trip.openmeteo_client(), OpenMeteoClient)
    finally:
        trip.tomtom_client.cache_clear()
        trip.openmeteo_client.cache_clear()


@pytest.mark.real_client_factories
def test_missing_key_fails_loudly_when_first_used():
    trip.tomtom_client.cache_clear()
    try:
        with override_settings(TOMTOM_API_KEY=""), pytest.raises(TomTomError):
            trip.tomtom_client()
    finally:
        trip.tomtom_client.cache_clear()
