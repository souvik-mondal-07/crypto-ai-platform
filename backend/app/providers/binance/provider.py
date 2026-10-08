"""
Binance provider.

Implements `MarketDataProvider` for interface consistency, but Binance
cannot support a broad coin-universe listing the way CoinGecko can —
`list_coins`/`get_market_data` raise `ProviderError` with a clear
explanation rather than silently returning an empty or misleading
result. The actual capability this provider offers is
`list_trading_pairs()`, used by the sync service to enrich coin
documents with Binance availability (see docs/market-data.md).
"""

import httpx
from datetime import datetime, timezone
from app.providers.normalized import NormalizedCandle
from app.providers.timeframes import Timeframe

from app.providers.base import MarketDataProvider
from app.providers.binance.client import BinanceClient
from app.providers.binance.mapper import map_exchange_info, map_ticker_24hr
from app.providers.errors import ProviderError
from app.providers.normalized import (
    NormalizedBinanceSymbol,
    NormalizedCoin,
    NormalizedExchangeTicker,
    NormalizedMarketData,
)


class BinanceProvider(MarketDataProvider):
    provider_name = "binance"
    supports_full_listing = False
    supports_global_market = False
    supports_trending = False

    def __init__(self, client: BinanceClient | None = None) -> None:
        self._client = client or BinanceClient()

    async def list_coins(self, page: int, per_page: int) -> list[NormalizedCoin]:
        raise ProviderError(
            "Binance does not provide a broad coin-universe listing — "
            "it only lists its own trading pairs. Use CoinGeckoProvider "
            "for the coin universe, and list_trading_pairs() on this "
            "provider to enrich coins with Binance availability."
        )

    async def get_market_data(self, page: int, per_page: int) -> list[NormalizedMarketData]:
        raise ProviderError(
            "Binance does not provide market data indexed the same way "
            "as the broad coin universe. Use get_exchange_tickers() for "
            "Binance-specific 24h ticker data keyed by trading symbol."
        )

    async def list_trading_pairs(self) -> list[NormalizedBinanceSymbol]:
        """All USDT-quoted trading pairs currently listed on Binance."""
        async with httpx.AsyncClient() as http_client:
            raw = await self._client.get_exchange_info(http_client)
        return map_exchange_info(raw)

    async def get_exchange_tickers(self) -> list[NormalizedExchangeTicker]:
        """
        Normalized 24h ticker stats for Binance's USDT trading pairs.

        This is exchange-specific data — one venue's view of one pair —
        and is never converted into a `NormalizedMarketData` (there is
        no `map_ticker_24hr -> NormalizedMarketData` path anywhere in
        this codebase). It also still backs `/market/exchange/binance/
        tickers`, presented to the frontend explicitly as Binance's own
        numbers, not the cross-market aggregate.

        As of the real-time refresh upgrade, `MarketSyncService.
        sync_binance_market_prices()` DOES use this data to update a
        handful of live-tracking fields (price, 24h change/high/low/
        volume) on `market_data` documents for coins with a valid
        Binance mapping — see `MarketDataRepository.
        bulk_upsert_binance_prices` for exactly which fields, and why
        that's disclosed via `data_source="binance"` rather than
        silently presented as CoinGecko's aggregate. Fields Binance
        doesn't carry (market cap, supply, ATH/ATL) are left alone.

        Fetches exchange info alongside the tickers so each result
        carries its base/quote asset rather than string-splitting the
        combined symbol (which is ambiguous).
        """
        async with httpx.AsyncClient() as http_client:
            raw_info = await self._client.get_exchange_info(http_client)
            raw_tickers = await self._client.get_ticker_24hr(http_client)

        symbol_index = {pair.symbol: pair for pair in map_exchange_info(raw_info)}
        tickers = map_ticker_24hr(raw_tickers, symbol_index)
        # Restrict to the pairs exchange info actually listed (USDT).
        return [ticker for ticker in tickers if ticker.symbol in symbol_index]

    async def get_historical_ohlcv(self, symbol: str, timeframe: Timeframe) -> list[NormalizedCandle]:
        """Fetch real exchange klines for a mapped Binance symbol. Volume units are base asset."""
        request = {Timeframe.DAY_1: ("1h", 24), Timeframe.DAY_7: ("4h", 42),
                   Timeframe.DAY_30: ("1d", 30), Timeframe.DAY_90: ("1d", 90),
                   Timeframe.YEAR_1: ("1w", 52)}
        interval, limit = request[timeframe]
        async with httpx.AsyncClient() as http_client:
            rows = await self._client.get_klines(http_client, symbol, interval, limit)
        out = []
        for row in rows:
            try:
                vals = [float(row[i]) for i in range(1, 6)]
                if vals[4] < 0 or not all(__import__("math").isfinite(v) for v in vals): continue
                out.append(NormalizedCandle(datetime.fromtimestamp(float(row[0])/1000, tz=timezone.utc), *vals[:4], vals[4]))
            except (TypeError, ValueError, IndexError, OverflowError):
                continue
        return out
