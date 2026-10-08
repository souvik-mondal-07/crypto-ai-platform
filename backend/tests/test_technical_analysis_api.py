"""
API-level tests for GET /api/v1/coins/{coin_id}/technical-analysis,
with the service layer mocked — no MongoDB, no live provider calls.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.providers.errors import ProviderUnavailableError
from app.schemas.technical_analysis import (
    AtrData,
    BollingerBandsData,
    MacdData,
    MacdPointSchema,
    MovingAverages,
    RsiData,
    SupportResistanceData,
    TechnicalAnalysisResponse,
    TrendAnalysis,
    VolumeAnalysis,
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


VALID_COIN_ID = "507f1f77bcf86cd799439011"


def _ta_response() -> TechnicalAnalysisResponse:
    return TechnicalAnalysisResponse(
        coin_id=VALID_COIN_ID,
        symbol="BTC",
        timeframe="30D",
        calculated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        candle_count=180,
        rsi=RsiData(period=14, current=62.5, zone="neutral", history=[62.5]),
        macd=MacdData(
            fast_period=12, slow_period=26, signal_period=9,
            current=MacdPointSchema(timestamp="2026-01-01T00:00:00Z", macd=1.2, signal=1.0, histogram=0.2),
            crossover="bullish_crossover",
            history=[],
        ),
        moving_averages=MovingAverages(sma={"20": 100.0, "50": 95.0, "200": None}, ema={"20": 101.0, "50": None}),
        bollinger_bands=BollingerBandsData(period=20, num_std_dev=2.0, upper=110.0, middle=100.0, lower=90.0),
        atr=AtrData(period=14, current=3.2, history=[3.2]),
        volume=VolumeAnalysis(current_volume_24h_usd=1_000_000.0, average_volume=120.0, volume_change_percent=20.0, trend="increasing"),
        support_resistance=SupportResistanceData(support_levels=[90.0], resistance_levels=[110.0]),
        trend=TrendAnalysis(trend="bullish", signals_considered=3),
        data_source="coingecko",
    )


def test_technical_analysis_returns_full_shape(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(return_value=_ta_response())
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis?timeframe=30D")

    assert response.status_code == 200
    body = response.json()
    assert body["rsi"]["current"] == 62.5
    assert body["rsi"]["zone"] == "neutral"
    assert body["macd"]["crossover"] == "bullish_crossover"
    assert body["moving_averages"]["sma"]["20"] == 100.0
    assert body["moving_averages"]["sma"]["200"] is None
    assert body["bollinger_bands"]["upper"] > body["bollinger_bands"]["lower"]
    assert body["trend"]["trend"] == "bullish"
    assert body["volume"]["current_volume_24h_usd"] == 1_000_000.0
    assert body["volume"]["historical_volume"] == []
    assert body["volume"]["average_volume"] == 120.0
    assert body["volume"]["volume_change_percent"] == 20.0
    assert body["volume"]["trend"] == "increasing"
    # Never a BUY/HOLD/SELL field on this response.
    assert "decision" not in body
    assert "recommendation" not in body


def test_technical_analysis_defaults_to_a_supported_timeframe(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(return_value=_ta_response())
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis")
    assert response.status_code == 200


def test_technical_analysis_rejects_unsupported_timeframe_with_422(client):
    response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis?timeframe=1H")
    assert response.status_code == 422


def test_technical_analysis_invalid_coin_id_returns_400(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(
            side_effect=AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        )
        response = client.get("/api/v1/coins/not-an-objectid/technical-analysis")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COIN_ID"


def test_technical_analysis_coin_not_found_returns_404(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(
            side_effect=AppError(404, "COIN_NOT_FOUND", "No coin found.")
        )
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "COIN_NOT_FOUND"


def test_technical_analysis_insufficient_history_returns_422(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(
            side_effect=AppError(422, "INSUFFICIENT_HISTORICAL_DATA", "Not enough candles.")
        )
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_HISTORICAL_DATA"


def test_technical_analysis_provider_failure_returns_503_without_traceback(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock_service_cls.return_value.get_technical_analysis = AsyncMock(
            side_effect=ProviderUnavailableError("coingecko down")
        )
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert "Traceback" not in response.text
    assert "coingecko down" not in response.text


def test_technical_analysis_accepts_force_refresh_param(client):
    with patch("app.api.v1.coins.TechnicalAnalysisService") as mock_service_cls:
        mock = AsyncMock(return_value=_ta_response())
        mock_service_cls.return_value.get_technical_analysis = mock
        response = client.get(f"/api/v1/coins/{VALID_COIN_ID}/technical-analysis?force_refresh=true")

    assert response.status_code == 200
    _, kwargs = mock.call_args
    assert kwargs.get("force_refresh") is True
