"""Pydantic response models for coin endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CoinGeckoMapping(BaseModel):
    id: str
    available: bool = True


class BinanceMapping(BaseModel):
    symbol: str
    available: bool = True


class CoinProviders(BaseModel):
    coingecko: Optional[CoinGeckoMapping] = None
    binance: Optional[BinanceMapping] = None


class Coin(BaseModel):
    """Canonical internal coin representation returned by the API."""

    id: str = Field(..., description="Internal MongoDB ObjectId, as a string")
    name: str
    symbol: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    market_cap_rank: Optional[int] = None
    is_active: bool
    providers: CoinProviders
    created_at: datetime
    updated_at: datetime


class CoinListResponse(BaseModel):
    items: list[Coin]
    page: int
    limit: int
    total: int
    pages: int


class CoinSearchResult(Coin):
    """
    A search-result row: coin identity joined with its current market
    snapshot (when one has been synced), plus the match rank used to
    order results.

    Extends `Coin` rather than duplicating its fields, since a search
    result IS a coin — just with market data and ranking attached.
    Market fields mirror the subset shown in the Markets table
    (`MarketCoin`); `None` means no market_data has been synced yet
    for this coin, not that the field was omitted.
    """

    price_usd: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None


class CoinSearchResponse(BaseModel):
    items: list[CoinSearchResult]
    query: str
    count: int
