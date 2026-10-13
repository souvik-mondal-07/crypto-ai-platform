"""Pydantic models for /api/v1/watchlist (Phase 16)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WatchlistAddRequest(BaseModel):
    """Only the coin — the user is ALWAYS the authenticated one; a `user_id` in the body is rejected (422)."""

    model_config = ConfigDict(extra="forbid")

    coin_id: str = Field(..., min_length=24, max_length=24)


class WatchlistItem(BaseModel):
    """A watched coin joined with its CURRENT market snapshot (read at request time, never stored on the watchlist)."""

    coin_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    market_cap_rank: Optional[int] = None
    price_usd: Optional[float] = None
    percent_change_24h: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    last_updated: Optional[datetime] = None
    is_stale: bool = False
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    total: int
    page: int
    limit: int
    pages: int


class WatchlistStatusResponse(BaseModel):
    coin_id: str
    in_watchlist: bool


class WatchlistAddResponse(BaseModel):
    coin_id: str
    in_watchlist: bool = True
    added_at: datetime


class WatchlistRemoveResponse(BaseModel):
    coin_id: str
    in_watchlist: bool = False
