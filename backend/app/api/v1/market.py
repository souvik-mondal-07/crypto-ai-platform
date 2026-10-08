"""
Market endpoints — overview, gainers, losers, global stats, trending.
All business logic lives in MarketService.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.core.market_refresh_state import get_refresh_state
from app.schemas.market import (
    ExchangeTickerResponse,
    GlobalMarket,
    MarketCoinListResponse,
    MarketOverview,
    MarketRefreshStatus,
    MoverItem,
    TrendingResponse,
)
from app.services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["Market"])


def _service() -> MarketService:
    return MarketService()


@router.get("/overview", response_model=MarketOverview)
async def get_overview(movers_limit: int = Query(5, ge=1, le=20)) -> MarketOverview:
    """Dashboard-ready summary: active coin count, top gainers/losers, freshness."""
    return await _service().get_overview(movers_limit=movers_limit)


@router.get("/gainers", response_model=list[MoverItem])
async def get_gainers(limit: int = Query(10, ge=1, le=100)) -> list[MoverItem]:
    """Top 24h gainers from currently synced market data — never hard-coded."""
    return await _service().get_top_movers("gainers", limit)


@router.get("/losers", response_model=list[MoverItem])
async def get_losers(limit: int = Query(10, ge=1, le=100)) -> list[MoverItem]:
    """Top 24h losers from currently synced market data — never hard-coded."""
    return await _service().get_top_movers("losers", limit)


@router.get("/global", response_model=GlobalMarket)
async def get_global_market() -> GlobalMarket:
    """Global market statistics, sourced live from CoinGecko's /global endpoint."""
    return await _service().get_global_market()


@router.get("/trending", response_model=TrendingResponse)
async def get_trending() -> TrendingResponse:
    """
    Trending coins, if the current provider supports it. Returns
    `available: false` (not fake data) when it doesn't.
    """
    return await _service().get_trending()


@router.get("/top/market-cap", response_model=list[MoverItem])
async def get_top_by_market_cap(limit: int = Query(20, ge=1, le=100)) -> list[MoverItem]:
    """Highest market-cap coins from currently synced market data."""
    return await _service().get_top_ranked("market_cap", limit)


@router.get("/top/volume", response_model=list[MoverItem])
async def get_top_by_volume(limit: int = Query(20, ge=1, le=100)) -> list[MoverItem]:
    """Highest 24h-volume coins from currently synced market data."""
    return await _service().get_top_ranked("volume", limit)


@router.get("/exchange/binance/tickers", response_model=ExchangeTickerResponse)
async def get_binance_tickers(limit: int = Query(50, ge=1, le=250)) -> ExchangeTickerResponse:
    """
    Binance's own 24h stats for its USDT trading pairs, highest
    quote-volume first.

    This is exchange-specific data — NOT the cross-market aggregate
    served by /coins/{id}/market. Binance lists only a subset of the
    coin universe (see docs/market-data.md).
    """
    return await _service().get_exchange_tickers(limit)


@router.get("/coins", response_model=MarketCoinListResponse)
async def list_market_coins(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query(
        "market_cap",
        description="market_cap | price | change_24h | change_7d | volume | fdv | supply | volatility",
    ),
    sort_direction: str = Query("desc", pattern="^(asc|desc)$"),
    filter: str = Query("all", description="all | gainers | losers"),
    change_min: Optional[float] = Query(None, description="Minimum 24h change, in percent"),
    change_max: Optional[float] = Query(None, description="Maximum 24h change, in percent"),
    market_cap_min: Optional[float] = Query(None, ge=0, description="Minimum market cap, USD"),
    market_cap_max: Optional[float] = Query(None, ge=0, description="Maximum market cap, USD"),
    volume_min: Optional[float] = Query(None, ge=0, description="Minimum 24h volume, USD"),
    volume_max: Optional[float] = Query(None, ge=0, description="Maximum 24h volume, USD"),
    has_max_supply: Optional[bool] = Query(None, description="true: capped supply; false: no reported max supply"),
    coin_ids: Optional[str] = Query(
        None, description="Comma-separated internal coin ids (watchlist, comparison, trending)"
    ),
) -> MarketCoinListResponse:
    """
    Paginated Markets-table rows: each coin joined with its current
    market snapshot, sortable by market fields and filterable by 24h
    direction/range, market cap, volume, supply cap, or an explicit
    set of coin ids.

    This exists so the Markets table can sort by price/change/volume/
    market cap/FDV/supply/volatility — fields that live in
    `market_data`, not `coins`, and so can't be sorted by the `/coins`
    listing. It also means one request per page instead of one
    market-data request per row. The same endpoint serves the
    watchlist, trending and comparison views via `coin_ids`.
    """
    parsed_ids = (
        [value.strip() for value in coin_ids.split(",") if value.strip()] if coin_ids is not None else None
    )
    return await _service().list_market_coins(
        page=page, limit=limit, sort_by=sort_by,
        sort_direction=sort_direction, market_filter=filter,
        change_min=change_min, change_max=change_max,
        market_cap_min=market_cap_min, market_cap_max=market_cap_max,
        volume_min=volume_min, volume_max=volume_max,
        has_max_supply=has_max_supply, coin_ids=parsed_ids,
    )


@router.get("/refresh-status", response_model=MarketRefreshStatus)
async def get_refresh_status() -> MarketRefreshStatus:
    """
    Background market-data refresh scheduler state (Part 18) — useful
    for debugging why a particular coin's data is still stale (was the
    last cycle's CoinGecko page fetch rate-limited? has the Binance
    price refresh run recently? when did the last full universe resync
    happen?). Exposes no secrets or provider keys.
    """
    return MarketRefreshStatus(**get_refresh_state().as_dict())
