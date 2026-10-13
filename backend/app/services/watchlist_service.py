"""Watchlist business logic (Phase 16). Every method takes the authenticated user's ObjectId."""

import math
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.watchlist_repository import WatchlistEntryExistsError, WatchlistRepository
from app.schemas.converters import is_snapshot_stale
from app.schemas.watchlist import (
    WatchlistAddResponse,
    WatchlistItem,
    WatchlistRemoveResponse,
    WatchlistResponse,
    WatchlistStatusResponse,
)
from app.services.user_feature_common import parse_coin_id, require_coin, utcnow
from app.utils.pagination import clamp_pagination

#: Matches the shared pagination MAX_LIMIT so the whole list always fits in one request.
MAX_WATCHLIST_ENTRIES = 250


class WatchlistService:
    def __init__(
        self,
        watchlist: Optional[WatchlistRepository] = None,
        coins: Optional[CoinRepository] = None,
        market_data: Optional[MarketDataRepository] = None,
    ) -> None:
        self._watchlist = watchlist or WatchlistRepository()
        self._coins = coins or CoinRepository()
        self._market = market_data or MarketDataRepository()

    async def add(self, user_id: ObjectId, coin_id: str) -> WatchlistAddResponse:
        coin_oid, _ = await require_coin(self._coins, coin_id)
        if await self._watchlist.exists(user_id, coin_oid):
            raise AppError(409, "WATCHLIST_ALREADY_EXISTS", "This coin is already in your watchlist.")
        if await self._watchlist.count_for_user(user_id) >= MAX_WATCHLIST_ENTRIES:
            raise AppError(409, "WATCHLIST_LIMIT_REACHED", f"Your watchlist is full ({MAX_WATCHLIST_ENTRIES} coins).")
        try:
            doc = await self._watchlist.add(user_id, coin_oid, utcnow())
        except WatchlistEntryExistsError:
            # Lost a race with a concurrent identical request — the unique index is the real guarantee.
            raise AppError(409, "WATCHLIST_ALREADY_EXISTS", "This coin is already in your watchlist.")
        return WatchlistAddResponse(coin_id=coin_id, added_at=doc["created_at"])

    async def remove(self, user_id: ObjectId, coin_id: str) -> WatchlistRemoveResponse:
        coin_oid = parse_coin_id(coin_id)
        if not await self._watchlist.remove(user_id, coin_oid):
            raise AppError(404, "WATCHLIST_ENTRY_NOT_FOUND", "This coin is not in your watchlist.")
        return WatchlistRemoveResponse(coin_id=coin_id)

    async def status(self, user_id: ObjectId, coin_id: str) -> WatchlistStatusResponse:
        coin_oid = parse_coin_id(coin_id)
        return WatchlistStatusResponse(coin_id=coin_id, in_watchlist=await self._watchlist.exists(user_id, coin_oid))

    async def list_items(self, user_id: ObjectId, page: int, limit: int) -> WatchlistResponse:
        page, limit = clamp_pagination(page, limit)
        total = await self._watchlist.count_for_user(user_id)
        entries = await self._watchlist.list_for_user(user_id, (page - 1) * limit, limit)

        coin_ids = [entry["coin_id"] for entry in entries]
        coin_docs = await self._coins.find_by_internal_ids(coin_ids) if coin_ids else {}
        market_docs = await self._market.get_many_by_coin_ids(coin_ids) if coin_ids else {}

        items: list[WatchlistItem] = []
        for entry in entries:
            coin = coin_docs.get(entry["coin_id"])
            if coin is None:  # the coin no longer exists in the universe — nothing to show for it
                continue
            market: dict[str, Any] = market_docs.get(entry["coin_id"]) or {}
            items.append(
                WatchlistItem(
                    coin_id=str(entry["coin_id"]),
                    name=coin["name"],
                    symbol=coin["symbol"],
                    logo_url=coin.get("logo_url"),
                    market_cap_rank=coin.get("market_cap_rank"),
                    price_usd=market.get("price_usd"),
                    percent_change_24h=market.get("percent_change_24h"),
                    market_cap_usd=market.get("market_cap_usd"),
                    volume_24h_usd=market.get("volume_24h_usd"),
                    last_updated=market.get("last_updated") or market.get("updated_at"),
                    is_stale=is_snapshot_stale(market.get("updated_at")),
                    added_at=entry["created_at"],
                )
            )
        return WatchlistResponse(items=items, total=total, page=page, limit=limit, pages=math.ceil(total / limit) if limit else 0)
