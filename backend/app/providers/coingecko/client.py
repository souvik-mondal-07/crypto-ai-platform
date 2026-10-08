"""
CoinGecko HTTP client.

Responsible ONLY for talking to CoinGecko's API and returning raw
JSON. No normalization, no business logic — that's the mapper's job
(see `mapper.py`) and the sync service's job, respectively.

Uses CoinGecko's public REST API (no scraping). See
docs/market-data.md for endpoint documentation and rate-limit notes.
"""

import logging
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.providers.http import request_json

logger = logging.getLogger("crypto_ai_platform.providers.coingecko")


class CoinGeckoClient:
    """Thin async wrapper around CoinGecko's public REST API."""

    provider_name = "coingecko"

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.COINGECKO_API_BASE_URL.rstrip("/")
        self._api_key = settings.COINGECKO_API_KEY or None

    def _headers(self) -> dict[str, str]:
        # CoinGecko's free/demo tier accepts an optional key via this
        # header to raise the caller's rate limit; the public endpoints
        # used here work without one.
        if self._api_key:
            return {"x-cg-demo-api-key": self._api_key}
        return {}

    async def get_coins_list(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """
        GET /coins/list — the full coin universe (id, symbol, name),
        no market data, not paginated (CoinGecko returns everything in
        one call). This is the "broad listing source" for Step 3.
        """
        return await request_json(
            client, "GET", f"{self._base_url}/coins/list",
            headers=self._headers(), provider_name=self.provider_name,
        )

    async def get_coins_markets(
        self, client: httpx.AsyncClient, page: int, per_page: int
    ) -> list[dict[str, Any]]:
        """
        GET /coins/markets — paginated, ranked by market cap, includes
        current price and other live market fields.
        """
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "page": page,
            "per_page": per_page,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d,30d,1y",
        }
        return await request_json(
            client, "GET", f"{self._base_url}/coins/markets",
            params=params, headers=self._headers(), provider_name=self.provider_name,
        )

    async def get_coin_ohlc(
        self, client: httpx.AsyncClient, coingecko_id: str, days: int
    ) -> list[list[float]]:
        """
        GET /coins/{id}/ohlc — historical OHLC candles.

        Returns an array of `[timestamp_ms, open, high, low, close]`
        arrays. Note there is NO volume component in this endpoint's
        response; callers must leave volume unset rather than
        substituting a value from elsewhere.

        CoinGecko picks candle granularity from `days` — see
        app/providers/timeframes.py.
        """
        params = {"vs_currency": "usd", "days": days}
        return await request_json(
            client, "GET", f"{self._base_url}/coins/{coingecko_id}/ohlc",
            params=params, headers=self._headers(), provider_name=self.provider_name,
        )

    async def get_global(self, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
        """GET /global — aggregate market statistics."""
        data = await request_json(
            client, "GET", f"{self._base_url}/global",
            headers=self._headers(), provider_name=self.provider_name,
        )
        return data.get("data") if isinstance(data, dict) else None

    async def get_search_trending(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """GET /search/trending — CoinGecko's trending-coins list."""
        data = await request_json(
            client, "GET", f"{self._base_url}/search/trending",
            headers=self._headers(), provider_name=self.provider_name,
        )
        return data.get("coins", []) if isinstance(data, dict) else []

    async def get_coin_detail(self, client: httpx.AsyncClient, coingecko_id: str) -> dict[str, Any]:
        """
        GET /coins/{id} — project profile (description, links,
        categories, platforms, genesis date, developer/community data).

        market_data/tickers/sparkline are switched OFF: the market
        figures are already synchronized into `market_data` by the
        existing sync (one bulk /coins/markets call covers the whole
        universe), so re-fetching them per coin here would only waste
        rate limit and create a second, possibly disagreeing, copy.
        """
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "true",
            "developer_data": "true",
            "sparkline": "false",
        }
        data = await request_json(
            client, "GET", f"{self._base_url}/coins/{coingecko_id}",
            params=params, headers=self._headers(), provider_name=self.provider_name,
        )
        return data if isinstance(data, dict) else {}
