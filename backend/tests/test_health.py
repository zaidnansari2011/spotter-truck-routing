from rest_framework.test import APIClient


def test_health_returns_ok():
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_served():
    response = APIClient().get("/api/schema/")

    assert response.status_code == 200


def test_swagger_docs_page_renders():
    response = APIClient().get("/api/docs/")

    assert response.status_code == 200
