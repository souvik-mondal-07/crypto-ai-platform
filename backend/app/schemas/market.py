"""Pydantic response models for market-data endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarketData(BaseModel):
    """Current market snapshot for a single coin."""

    coin_id: str
    price_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None
    percent_change_1h: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    percent_change_30d: Optional[float] = None
    percent_change_1y: Optional[float] = None
    #: Absolute USD change over 24h — distinct from percent_change_24h.
    price_change_24h_usd: Optional[float] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    fully_diluted_valuation_usd: Optional[float] = None
    ath_usd: Optional[float] = None
    atl_usd: Optional[float] = None
    ath_change_percentage: Optional[float] = None
    atl_change_percentage: Optional[float] = None
    ath_date: Optional[datetime] = None
    atl_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    data_source: str
    is_stale: bool = False


class MoverItem(BaseModel):
    """One entry in a top-gainers/top-losers list."""

    coin_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    market_cap_rank: Optional[int] = None
    price_usd: Optional[float] = None
    percent_change_24h: Optional[float] = None
    #: Added for the Dashboard's Market Movers rows; all optional so older
    #: consumers of this shape are unaffected.
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    #: (24h high - 24h low) / price * 100 — derived from synced data, None when
    #: any input is missing.
    volatility_24h_pct: Optional[float] = None


class MarketOverview(BaseModel):
    active_cryptocurrencies: int
    top_gainers: list[MoverItem]
    top_losers: list[MoverItem]
    last_updated: Optional[datetime] = None
    data_source: str


class GlobalMarket(BaseModel):
    total_market_cap_usd: Optional[float] = None
    total_volume_24h_usd: Optional[float] = None
    market_cap_percentage: Optional[dict[str, float]] = None
    active_cryptocurrencies: Optional[int] = None
    market_cap_change_percentage_24h: Optional[float] = None
    last_updated: Optional[datetime] = None
    data_source: str


class TrendingCoin(BaseModel):
    coingecko_id: str
    internal_coin_id: Optional[str] = None
    name: str
    symbol: str
    market_cap_rank: Optional[int] = None
    score: Optional[int] = None


class TrendingResponse(BaseModel):
    items: list[TrendingCoin]
    available: bool
    data_source: str
    last_updated: Optional[datetime] = None


class HistoricalCandle(BaseModel):
    """
    One OHLC candle. `volume` is Optional and is currently always
    null — CoinGecko's OHLC endpoint carries no volume component, and
    a value is never substituted from another source (see
    docs/market-data.md).
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class HistoricalPriceResponse(BaseModel):
    coin_id: str
    timeframe: str
    #: Provider-chosen candle granularity for this timeframe (e.g. "4h").
    granularity: str
    candles: list[HistoricalCandle]
    data_source: str


class ExchangeTicker(BaseModel):
    """
    Exchange-specific 24h stats for one trading pair. Distinct from
    MarketData (the cross-market aggregate) — see
    app/providers/normalized.py.
    """

    symbol: str
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None
    last_price: Optional[float] = None
    price_change_percent_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    quote_volume_24h: Optional[float] = None


class ExchangeTickerResponse(BaseModel):
    exchange: str
    tickers: list[ExchangeTicker]
    count: int


class MarketCoin(BaseModel):
    """
    A coin joined with its current market snapshot — the row shape for
    the Markets table. Combines coin identity with the market fields
    the table sorts and filters on, so the frontend needs one request
    per page instead of one per coin.
    """

    coin_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    market_cap_rank: Optional[int] = None
    price_usd: Optional[float] = None
    percent_change_24h: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    circulating_supply: Optional[float] = None
    last_updated: Optional[datetime] = None
    # --- Added for the redesigned Markets table / comparison. All optional:
    # None means the provider did not supply it, never a placeholder. ---
    percent_change_1h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    percent_change_30d: Optional[float] = None
    fully_diluted_valuation_usd: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    ath_usd: Optional[float] = None
    atl_usd: Optional[float] = None
    ath_change_percentage: Optional[float] = None
    atl_change_percentage: Optional[float] = None
    volatility_24h_pct: Optional[float] = None
    data_source: Optional[str] = None
    is_stale: bool = False


class MarketCoinListResponse(BaseModel):
    items: list[MarketCoin]
    page: int
    limit: int
    total: int
    pages: int
    sort_by: str
    sort_direction: str
    data_source: str
    #: Number of coins that have ANY synced market snapshot (unfiltered).
    #: `total` above is the filtered count.
    coins_with_market_data: Optional[int] = None
    #: Most recent market_data write across the collection, and whether it
    #: is older than the backend stale threshold (converters.STALE_AFTER).
    last_updated: Optional[datetime] = None
    is_stale: bool = False


class RefreshCycleStatus(BaseModel):
    """One completed background-refresh cycle's outcome (Parts 17-18)."""

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    binance_enabled: bool = False
    binance_mapped_coins: int = 0
    binance_tickers_fetched: int = 0
    binance_updated: int = 0
    coingecko_pages_requested: list[int] = []
    coingecko_pages_completed: int = 0
    coingecko_records_upserted: int = 0
    coingecko_reached_end: bool = False
    errors: list[str] = []


class MarketRefreshStatus(BaseModel):
    """
    Background market-data refresh scheduler state — for debugging why
    a coin is stale, not a public/monitoring API. Exposes no secrets or
    provider keys, only counts and timestamps.
    """

    enabled: bool
    is_running: bool
    total_cycles: int
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_universe_sync_at: Optional[datetime] = None
    last_cycle: Optional[RefreshCycleStatus] = None
