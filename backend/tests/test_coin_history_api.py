"""
API-level tests for GET /api/v1/coins/{coin_id}/history, with the
service layer mocked — no MongoDB, no live provider calls.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.providers.errors import ProviderUnavailableError
from app.schemas.market import HistoricalCandle, HistoricalPriceResponse


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


VALID_COIN_ID = "507f1f77bcf86cd799439011"


def _history_response() -> HistoricalPriceResponse:
    return HistoricalPriceResponse(
        coin_id=VALID_COIN_ID,
        timeframe="7D",
        granularity="4h",
        candles=[
            HistoricalCandle(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                open=100.0, high=110.0, low=95.0, close=105.0, volume=None,
            )
        ],
        data_source="coingecko",
    )


def test_history_returns_candles(client):
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(return_value=_history_response())
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history?timeframe=7D")

    assert response.status_code == 200
    body = response.json()
    assert body["timeframe"] == "7D"
    assert body["granularity"] == "4h"
    assert len(body["candles"]) == 1
    assert body["candles"][0]["open"] == 100.0
    # Volume is genuinely absent from this provider endpoint.
    assert body["candles"][0]["volume"] is None


def test_history_defaults_to_a_supported_timeframe(client):
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(return_value=_history_response())
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history")
    assert response.status_code == 200


def test_history_rejects_unsupported_timeframe_with_422(client):
    """1H is deliberately not offered — it must be rejected, not silently coerced."""
    response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history?timeframe=1H")
    assert response.status_code == 422


def test_history_coin_not_found_returns_consistent_error_shape(client):
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(
            side_effect=AppError(404, "COIN_NOT_FOUND", "No coin found.")
        )
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history?timeframe=7D")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COIN_NOT_FOUND"


def test_history_invalid_coin_id_returns_400(client):
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(
            side_effect=AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        )
        response = client.get("/api/v1/coins/not-an-objectid/history?timeframe=7D")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COIN_ID"


def test_history_provider_failure_returns_503_without_traceback(client):
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(
            side_effect=ProviderUnavailableError("coingecko down")
        )
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history?timeframe=7D")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert "Traceback" not in response.text
    assert "coingecko down" not in response.text


def test_history_empty_candles_is_a_valid_response(client):
    empty = _history_response()
    empty.candles = []
    with patch("app.api.v1.coins.MarketService") as mock_service_cls:
        mock_service_cls.return_value.get_coin_history = AsyncMock(return_value=empty)
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/history?timeframe=7D")

    assert response.status_code == 200
    assert response.json()["candles"] == []
