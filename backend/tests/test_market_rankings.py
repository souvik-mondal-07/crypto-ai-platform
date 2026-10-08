"""
Tests for the Phase 7 additions: market-cap/volume rankings, the
24h high/low fields, and Binance exchange tickers.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.providers.coingecko.mapper import map_coin_market
from app.schemas.market import ExchangeTicker, ExchangeTickerResponse, MoverItem
from app.services.market_service import MarketService


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# 24h high/low now flow from the provider through to the API schema
# ---------------------------------------------------------------------------

def test_coin_market_mapper_extracts_24h_high_and_low():
    raw = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "high_24h": 66000.0, "low_24h": 64000.0,
    }
    _, market = map_coin_market(raw)
    assert market.high_24h_usd == 66000.0
    assert market.low_24h_usd == 64000.0


def test_coin_market_mapper_24h_high_low_absent_stays_none():
    _, market = map_coin_market({"id": "x", "symbol": "x", "name": "X"})
    assert market.high_24h_usd is None
    assert market.low_24h_usd is None


# ---------------------------------------------------------------------------
# Ranking endpoints
# ---------------------------------------------------------------------------

def _mover() -> MoverItem:
    return MoverItem(
        coin_id=str(ObjectId()), name="Real Coin", symbol="RC",
        logo_url=None, market_cap_rank=1, price_usd=10.0, percent_change_24h=1.0,
    )


def test_top_market_cap_returns_real_data(client):
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.get_top_ranked = AsyncMock(return_value=[_mover()])
        response = client.get("/api/v1/market/top/market-cap?limit=5")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Real Coin"


def test_top_volume_returns_real_data(client):
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.get_top_ranked = AsyncMock(return_value=[])
        response = client.get("/api/v1/market/top/volume")

    assert response.status_code == 200
    assert response.json() == []


def test_ranking_limit_is_bounded(client):
    response = client.get("/api/v1/market/top/market-cap?limit=99999")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_top_ranked_rejects_unknown_ranking_field():
    """A client-supplied string must never reach a MongoDB sort spec."""
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=AsyncMock(),
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )
    with pytest.raises(AppError) as exc_info:
        await service.get_top_ranked("$where", 10)
    assert exc_info.value.code == "INVALID_RANKING"


@pytest.mark.asyncio
async def test_get_top_ranked_maps_whitelisted_key_to_real_field():
    market_repo = AsyncMock()
    market_repo.get_top_by_field = AsyncMock(return_value=[])
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=market_repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )
    await service.get_top_ranked("volume", 10)
    market_repo.get_top_by_field.assert_awaited_once()
    assert market_repo.get_top_by_field.await_args.args[0] == "volume_24h_usd"


# ---------------------------------------------------------------------------
# Binance exchange tickers
# ---------------------------------------------------------------------------

def test_binance_tickers_endpoint_labels_the_exchange(client):
    payload = ExchangeTickerResponse(
        exchange="binance",
        tickers=[ExchangeTicker(symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT", last_price=65000.0)],
        count=1,
    )
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.get_exchange_tickers = AsyncMock(return_value=payload)
        response = client.get("/api/v1/market/exchange/binance/tickers?limit=1")

    assert response.status_code == 200
    body = response.json()
    # The response must make clear this is one venue, not a global aggregate.
    assert body["exchange"] == "binance"
    assert body["tickers"][0]["symbol"] == "BTCUSDT"


def test_refresh_status_endpoint_reports_scheduler_state(client):
    """Part 18 — a lightweight status endpoint for debugging staleness. No secrets, just counts/timestamps."""
    response = client.get("/api/v1/market/refresh-status")
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "is_running" in body
    assert "total_cycles" in body
    # Never leak provider keys/secrets through this endpoint.
    assert "api_key" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_existing_step3_market_endpoints_still_work(client):
    """Phase 7 additions must not break the earlier market routes."""
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.get_top_movers = AsyncMock(return_value=[])
        assert client.get("/api/v1/market/gainers").status_code == 200
        assert client.get("/api/v1/market/losers").status_code == 200
