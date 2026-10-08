"""
Coin service — business logic for coin listing/search/detail.

Routes call this, never the repository or MongoDB directly.
"""

from typing import Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.coin_repository import SORTABLE_FIELDS, CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.coin import Coin, CoinListResponse, CoinSearchResponse
from app.schemas.converters import coin_doc_to_schema, coin_search_result_to_schema
from app.utils.pagination import clamp_pagination, total_pages


class CoinService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market_data = market_data_repository or MarketDataRepository()

    async def list_coins(
        self,
        page: int,
        limit: int,
        *,
        active_only: bool = True,
        provider: Optional[str] = None,
        sort_by: str = "market_cap_rank",
        sort_direction: str = "asc",
    ) -> CoinListResponse:
        safe_page, safe_limit = clamp_pagination(page, limit)

        if sort_by not in SORTABLE_FIELDS:
            raise AppError(400, "INVALID_SORT_FIELD", f"'{sort_by}' is not a sortable field.")
        if sort_direction not in ("asc", "desc"):
            raise AppError(400, "INVALID_SORT_DIRECTION", "sort_direction must be 'asc' or 'desc'.")
        if provider is not None and provider not in ("coingecko", "binance"):
            raise AppError(400, "INVALID_PROVIDER", "provider must be 'coingecko' or 'binance'.")

        direction = 1 if sort_direction == "asc" else -1
        docs, total = await self._coins.list_coins(
            safe_page,
            safe_limit,
            is_active=True if active_only else None,
            provider=provider,
            sort_by=sort_by,
            sort_direction=direction,
        )
        return CoinListResponse(
            items=[coin_doc_to_schema(doc) for doc in docs],
            page=safe_page,
            limit=safe_limit,
            total=total,
            pages=total_pages(total, safe_limit),
        )

    async def search_coins(self, query: str, limit: int = 20) -> CoinSearchResponse:
        query = query.strip()
        if not query:
            raise AppError(400, "INVALID_QUERY", "Search query must not be empty.")
        if len(query) > 100:
            raise AppError(400, "INVALID_QUERY", "Search query is too long.")

        _, safe_limit = clamp_pagination(1, limit)
        docs = await self._coins.search(query, limit=safe_limit)

        # Join each result with its current market snapshot in one
        # batched lookup — this is the actual fix for search results
        # showing no market data: the previous version returned bare
        # `Coin` identities with no price/market fields at all, which
        # no amount of frontend re-fetching could fix cleanly.
        coin_ids = [doc["_id"] for doc in docs]
        market_by_coin_id = await self._market_data.get_many_by_coin_ids(coin_ids) if coin_ids else {}

        return CoinSearchResponse(
            items=[
                coin_search_result_to_schema(doc, market_by_coin_id.get(doc["_id"]))
                for doc in docs
            ],
            query=query,
            count=len(docs),
        )

    async def get_coin(self, coin_id: str) -> Coin:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        doc = await self._coins.find_by_internal_id(coin_id)
        if doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        return coin_doc_to_schema(doc)
