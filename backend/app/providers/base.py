"""
Common provider interface.

Every market-data provider (CoinGecko, Binance, and any future
provider — e.g. a licensed CoinMarketCap integration) implements this
interface, so the sync service and API layer never branch on "which
provider is this".

Not every provider can support every capability — CoinGecko provides
a broad cryptocurrency universe; Binance only provides data for its
own trading pairs (see docs/market-data.md for why these are NOT the
same set). Providers that can't support a capability raise
NotImplementedError with a clear message rather than silently
returning an empty/misleading result.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.providers.normalized import (
    NormalizedCandle,
    NormalizedCoin,
    NormalizedCoinProfile,
    NormalizedGlobalMarket,
    NormalizedMarketData,
    NormalizedTrendingCoin,
)
from app.providers.timeframes import Timeframe


class MarketDataProvider(ABC):
    """Common interface implemented by every market-data provider."""

    #: Short, stable identifier used in `provider`/`data_source` fields
    #: throughout the app (e.g. "coingecko", "binance").
    provider_name: str

    #: Whether this provider can enumerate a broad coin universe
    #: (`list_coins`). False for exchange-only providers like Binance.
    supports_full_listing: bool = False

    #: Whether this provider exposes global market statistics.
    supports_global_market: bool = False

    #: Whether this provider exposes a trending-coins endpoint.
    supports_trending: bool = False

    #: Whether this provider can return historical OHLC candles.
    supports_historical_ohlc: bool = False

    #: Whether this provider can return project/ecosystem profile data.
    supports_coin_profile: bool = False

    @abstractmethod
    async def list_coins(self, page: int, per_page: int) -> list[NormalizedCoin]:
        """
        Return one page of the provider's coin universe, richest-first
        (typically ordered by market cap). Raises NotImplementedError
        if `supports_full_listing` is False.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_market_data(self, page: int, per_page: int) -> list[NormalizedMarketData]:
        """Return one page of current market data, aligned with `list_coins`'s ordering."""
        raise NotImplementedError

    async def get_global_market(self) -> Optional[NormalizedGlobalMarket]:
        """Return global market statistics, or None if unsupported."""
        return None

    async def get_trending(self) -> list[NormalizedTrendingCoin]:
        """Return trending coins, or an empty list if unsupported."""
        return []

    async def get_historical_ohlc(self, provider_coin_id: str, timeframe: Timeframe) -> list[NormalizedCandle]:
        """
        Return historical OHLC candles for a coin, or an empty list if
        this provider can't supply them (`supports_historical_ohlc`
        is False).
        """
        return []

    async def get_coin_profile(self, provider_coin_id: str) -> Optional[NormalizedCoinProfile]:
        """
        Return project/ecosystem profile data for a coin, or None if
        this provider can't supply it (`supports_coin_profile` is False).
        """
        return None
