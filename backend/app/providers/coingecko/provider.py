"""
CoinGecko provider: the `MarketDataProvider` implementation used as
the platform's broad cryptocurrency-universe source (see
docs/market-data.md).
"""

from typing import Optional

import httpx

from app.providers.base import MarketDataProvider
from app.providers.coingecko.client import CoinGeckoClient
from app.providers.coingecko.mapper import (
    map_coin_list_item,
    map_coin_market,
    map_coin_profile,
    map_global,
    map_ohlc,
    map_trending,
)
from app.providers.normalized import (
    NormalizedCandle,
    NormalizedCoin,
    NormalizedCoinProfile,
    NormalizedGlobalMarket,
    NormalizedMarketData,
    NormalizedTrendingCoin,
)
from app.providers.timeframes import TIMEFRAME_TO_DAYS, Timeframe


class CoinGeckoProvider(MarketDataProvider):
    provider_name = "coingecko"
    supports_full_listing = True
    supports_global_market = True
    supports_trending = True
    supports_historical_ohlc = True
    supports_coin_profile = True

    def __init__(self, client: Optional[CoinGeckoClient] = None) -> None:
        self._client = client or CoinGeckoClient()

    async def list_full_universe(self, http_client: httpx.AsyncClient) -> list[NormalizedCoin]:
        """
        Return CoinGecko's entire coin universe (id/symbol/name, no
        rank or market data) in one call. This is what makes the
        platform's coin list NOT limited to a hard-coded/top-N subset
        — see docs/market-data.md.
        """
        raw_items = await self._client.get_coins_list(http_client)
        return [map_coin_list_item(item) for item in raw_items]

    async def list_coins(self, page: int, per_page: int) -> list[NormalizedCoin]:
        async with httpx.AsyncClient() as http_client:
            raw_items = await self._client.get_coins_markets(http_client, page, per_page)
        return [map_coin_market(item)[0] for item in raw_items]

    async def get_market_data(self, page: int, per_page: int) -> list[NormalizedMarketData]:
        async with httpx.AsyncClient() as http_client:
            raw_items = await self._client.get_coins_markets(http_client, page, per_page)
        return [map_coin_market(item)[1] for item in raw_items]

    async def list_coins_with_market_data(
        self, http_client: httpx.AsyncClient, page: int, per_page: int
    ) -> list[tuple[NormalizedCoin, NormalizedMarketData]]:
        """
        Fetch one /coins/markets page and return both halves together
        — used by the sync service so it doesn't fetch the same page
        twice via `list_coins` + `get_market_data` separately.
        """
        raw_items = await self._client.get_coins_markets(http_client, page, per_page)
        return [map_coin_market(item) for item in raw_items]

    async def get_global_market(self) -> Optional[NormalizedGlobalMarket]:
        async with httpx.AsyncClient() as http_client:
            raw = await self._client.get_global(http_client)
        return map_global(raw) if raw else None

    async def get_trending(self) -> list[NormalizedTrendingCoin]:
        async with httpx.AsyncClient() as http_client:
            raw_items = await self._client.get_search_trending(http_client)
        return map_trending(raw_items)

    async def get_historical_ohlc(
        self, provider_coin_id: str, timeframe: Timeframe
    ) -> list[NormalizedCandle]:
        """
        Historical OHLC candles for one coin. `provider_coin_id` is
        CoinGecko's own coin ID (e.g. "bitcoin") — the caller resolves
        that from the platform's internal coin ID, never the symbol.
        """
        days = TIMEFRAME_TO_DAYS[timeframe]
        async with httpx.AsyncClient() as http_client:
            raw_rows = await self._client.get_coin_ohlc(http_client, provider_coin_id, days)
        return map_ohlc(raw_rows)

    async def get_coin_profile(self, provider_coin_id: str) -> Optional[NormalizedCoinProfile]:
        """
        Project/ecosystem profile for one coin. `provider_coin_id` is
        CoinGecko's own ID, resolved by the caller from the internal
        coin ID. Returns None for an empty payload rather than a
        profile full of blanks.
        """
        async with httpx.AsyncClient() as http_client:
            raw = await self._client.get_coin_detail(http_client, provider_coin_id)
        if not raw or not raw.get("id"):
            return None
        return map_coin_profile(raw)
