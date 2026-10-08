"""
Binance HTTP client.

Responsible ONLY for talking to Binance's public REST API. Binance
provides exchange-specific trading data (its own listed pairs), not a
broad cryptocurrency universe — see docs/market-data.md for why this
is architecturally distinct from the CoinGecko client.
"""

from typing import Any

import httpx

from app.config import get_settings
from app.providers.http import request_json

PROVIDER_NAME = "binance"


class BinanceClient:
    """Thin async wrapper around Binance's public REST API."""

    provider_name = PROVIDER_NAME

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.BINANCE_API_BASE_URL.rstrip("/")

    async def get_exchange_info(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """
        GET /api/v3/exchangeInfo — every trading pair Binance lists,
        with each pair's base/quote asset and trading status. No API
        key required.
        """
        return await request_json(
            client, "GET", f"{self._base_url}/api/v3/exchangeInfo",
            provider_name=self.provider_name,
        )

    async def get_ticker_24hr(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """
        GET /api/v3/ticker/24hr — 24h rolling price/volume stats for
        every symbol. No API key required.
        """
        return await request_json(
            client, "GET", f"{self._base_url}/api/v3/ticker/24hr",
            provider_name=self.provider_name,
        )

    async def get_klines(self, client: httpx.AsyncClient, symbol: str, interval: str, limit: int = 500) -> list[list[Any]]:
        """GET /api/v3/klines; Binance kline element [5] is real base-asset volume."""
        return await request_json(client, "GET", f"{self._base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit}, provider_name=self.provider_name)
