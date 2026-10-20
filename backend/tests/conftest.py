import pytest
from django.core.cache import cache

from planner.services import trip
from tests.support import FakeTomTom, FakeWeather


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def fakes(monkeypatch):
    def install(tomtom=None, weather=None):
        tomtom, weather = tomtom or FakeTomTom(), weather or FakeWeather()
        monkeypatch.setattr(trip, "tomtom_client", lambda: tomtom)
        monkeypatch.setattr(trip, "openmeteo_client", lambda: weather)
        return tomtom, weather

    return install


@pytest.fixture(autouse=True)
def no_live_api_clients(request, monkeypatch):
    """API tests must install fakes; reaching TomTom or Open-Meteo from a test is a bug."""
    if request.node.get_closest_marker("real_client_factories"):
        return

    def refuse():
        raise AssertionError("test tried to use a live API client; install fakes first")

    monkeypatch.setattr(trip, "tomtom_client", refuse)
    monkeypatch.setattr(trip, "openmeteo_client", refuse)
