"""
Root + health endpoint tests.

These run without requiring MongoDB to be available: the health
endpoint is expected to respond either way, reporting "connected" or
"disconnected" honestly rather than requiring a live database just to
exercise the endpoint. See test_database.py for tests that require a
running MongoDB instance.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_endpoint_reports_status_honestly():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("ok", "degraded")
    assert "service" in data

    # The database field must always be one of these two honest values
    # — never silently "connected" when it isn't.
    assert data["database"] in ("connected", "disconnected")

    # status and database must agree with each other
    if data["database"] == "connected":
        assert data["status"] == "ok"
    else:
        assert data["status"] == "degraded"
