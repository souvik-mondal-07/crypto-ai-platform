"""
API-level tests for /api/v1/coins and /api/v1/market, using
unittest.mock to replace the service layer so these run without
MongoDB or live provider calls. Verifies routing, request validation,
and the consistent error-response shape.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app


@pytest.fixture
def client():
    # raise_server_exceptions=False: Starlette's ServerErrorMiddleware
    # re-raises any exception that reaches it even after invoking a
    # registered handler (so the generic `Exception` handler in
    # app/core/exceptions.py still produces the 500 JSON response, but
    # the original exception then propagates to the test transport by
    # default). Without this flag, an unhandled-exception test like
    # test_unexpected_exception_returns_generic_500_without_leaking_detail
    # would see the RuntimeError raised into the test itself instead of
    # getting to inspect the resulting HTTP response.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_coins_search_requires_query_param(client):
    response = client.get("/api/v1/coins/search")
    assert response.status_code == 422  # FastAPI validation, missing required `q`


def test_coins_list_rejects_limit_above_max(client):
    response = client.get("/api/v1/coins?limit=99999")
    assert response.status_code == 422


def test_coins_list_rejects_invalid_sort_direction(client):
    response = client.get("/api/v1/coins?sort_direction=sideways")
    assert response.status_code == 422


def test_get_coin_not_found_returns_consistent_error_shape(client):
    with patch("app.api.v1.coins.CoinService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.get_coin = AsyncMock(side_effect=AppError(404, "COIN_NOT_FOUND", "No coin found."))
        response = client.get("/api/v1/coins/000000000000000000000000")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "COIN_NOT_FOUND"
    assert "message" in body["error"]
    # Never a raw traceback / exception repr in the response.
    assert "Traceback" not in response.text


def test_unexpected_exception_returns_generic_500_without_leaking_detail(client):
    with patch("app.api.v1.coins.CoinService") as mock_service_cls:
        instance = mock_service_cls.return_value
        instance.get_coin = AsyncMock(side_effect=RuntimeError("some secret internal detail"))
        response = client.get("/api/v1/coins/000000000000000000000000")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "some secret internal detail" not in response.text


def test_dev_sync_endpoint_not_registered_by_default(client):
    """ENABLE_DEV_SYNC_ENDPOINT defaults to false — the route must not exist at all."""
    response = client.post("/api/v1/dev/sync/market")
    assert response.status_code == 404
