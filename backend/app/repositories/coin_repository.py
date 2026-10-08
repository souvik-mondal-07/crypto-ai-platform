"""
Coin repository.

All MongoDB access for the `coins` collection goes through here —
provider clients, the sync service, and API routes never issue a
`coins` query directly.
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, UpdateOne

from app.database.collections import CollectionName
from app.providers.normalized import NormalizedCoin
from app.repositories.base import BaseRepository

# Whitelisted sort fields — never pass a user-supplied string straight
# into a MongoDB sort spec.
SORTABLE_FIELDS = {
    "name": "name",
    "symbol": "symbol",
    "market_cap_rank": "market_cap_rank",
    "updated_at": "updated_at",
}


class CoinRepository(BaseRepository):
    collection_name = CollectionName.COINS

    async def bulk_upsert_from_coingecko(self, coins: list[NormalizedCoin]) -> dict[str, int]:
        """
        Upsert a batch of coins keyed by their CoinGecko ID (the
        uniqueness anchor — see docs/database-schema.md). Uses a
        single bulk_write rather than one round-trip per coin.

        Existing coins not present in `coins` are left untouched —
        synchronization never deletes/deactivates coins just because
        one page/run didn't mention them (that would incorrectly wipe
        out coins on a partial/paginated sync). Returns counts of
        matched vs. newly inserted documents.
        """
        if not coins:
            return {"matched": 0, "upserted": 0}

        now = datetime.now(timezone.utc)
        operations = []
        for coin in coins:
            update_fields: dict[str, Any] = {
                "name": coin.name,
                "symbol": coin.symbol,
                "slug": coin.slug,
                "updated_at": now,
                "providers.coingecko.id": coin.coingecko_id,
                "providers.coingecko.available": True,
            }
            if coin.logo_url is not None:
                update_fields["logo_url"] = coin.logo_url
            if coin.market_cap_rank is not None:
                update_fields["market_cap_rank"] = coin.market_cap_rank

            operations.append(
                UpdateOne(
                    {"providers.coingecko.id": coin.coingecko_id},
                    {
                        "$set": update_fields,
                        "$setOnInsert": {
                            "created_at": now,
                            "is_active": True,
                        },
                    },
                    upsert=True,
                )
            )

        result = await self.collection.bulk_write(operations, ordered=False)
        return {
            "matched": result.matched_count,
            "upserted": len(result.upserted_ids or {}),
        }

    async def set_binance_mapping(self, coingecko_id: str, binance_symbol: str) -> bool:
        """Attach/refresh a coin's Binance trading-pair mapping."""
        result = await self.collection.update_one(
            {"providers.coingecko.id": coingecko_id},
            {
                "$set": {
                    "providers.binance.symbol": binance_symbol,
                    "providers.binance.available": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0

    async def list_binance_mapped(self) -> list[tuple[ObjectId, str]]:
        """
        Every active coin with a Binance trading-pair mapping, as
        `(internal_id, binance_symbol)` pairs — the input to the fast
        Binance-price refresh cycle (see MarketSyncService.
        sync_binance_market_prices). Projected to just the two fields
        needed, since this can be the whole coin universe's worth of
        documents.
        """
        cursor = self.collection.find(
            {"providers.binance.symbol": {"$exists": True, "$ne": None}, "is_active": True},
            {"providers.binance.symbol": 1},
        )
        docs = await cursor.to_list(length=None)
        result = []
        for doc in docs:
            symbol = (doc.get("providers") or {}).get("binance", {}).get("symbol")
            if symbol:
                result.append((doc["_id"], symbol))
        return result

    async def find_by_internal_id(self, internal_id: str) -> Optional[dict[str, Any]]:
        return await self.find_by_id(internal_id)

    async def find_by_internal_ids(self, internal_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        """Bulk lookup, keyed by _id — used to join coin info onto market-data results."""
        cursor = self.collection.find({"_id": {"$in": internal_ids}})
        docs = await cursor.to_list(length=len(internal_ids))
        return {doc["_id"]: doc for doc in docs}

    async def find_best_by_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        For each ticker, the highest-ranked ACTIVE coin carrying it
        (lowest market_cap_rank). Tickers are not unique across the coin
        universe, so ranked coins win; tickers that only match unranked
        coins are omitted rather than guessed.
        """
        if not symbols:
            return {}
        cursor = self.collection.find(
            {"symbol": {"$in": symbols}, "is_active": True, "market_cap_rank": {"$ne": None}},
            {"symbol": 1, "market_cap_rank": 1},
        ).sort("market_cap_rank", ASCENDING)
        docs = await cursor.to_list(length=None)
        best: dict[str, dict[str, Any]] = {}
        for doc in docs:
            best.setdefault(doc["symbol"], doc)
        return best

    async def find_by_coingecko_id(self, coingecko_id: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"providers.coingecko.id": coingecko_id})

    async def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Case-insensitive, relevance-ranked search across name, symbol,
        slug, and the provider coin ID. Searches the normalized
        MongoDB collection only — never calls out to a provider per
        keystroke.

        Ranking (lower `_rank` = stronger match), generic for any
        query/coin — nothing is hard-coded to a specific coin:
          0. Exact coin ID match (provider coingecko id)
          1. Exact name match
          2. Exact symbol match
          3. Name starts with the query
          4. Symbol starts with the query
          5. Name contains the query
          6. Symbol contains the query
          7. Everything else (slug/provider-id substring matches)

        Within a rank tier, results are ordered by `market_cap_rank`
        (nulls last) so the most prominent coin in a tier surfaces
        first. The whole computation happens in one aggregation so
        MongoDB does the ranking, not an in-memory Python sort of the
        full match set.

        The query is regex-escaped before use — a user-supplied "("
        or other regex metacharacter must never reach MongoDB as a
        literal pattern fragment (avoids both query errors and a
        ReDoS-prone expression).
        """
        raw = query.strip()
        escaped = re.escape(raw)
        # `$regexMatch` expects `regex` to be a string/expression, not a
        # MongoDB query-style `{ "$regex": ..., "$options": ... }` object.
        # Keep the query-style regex objects for `$match`, but use plain
        # patterns plus `options="i"` for the aggregation expressions.
        exact_pattern = f"^{escaped}$"
        starts_with_pattern = f"^{escaped}"
        contains_pattern = escaped

        exact = {"$regex": exact_pattern, "$options": "i"}
        starts_with = {"$regex": starts_with_pattern, "$options": "i"}
        contains = {"$regex": contains_pattern, "$options": "i"}

        pipeline: list[dict[str, Any]] = [
            {
                "$match": {
                    "$or": [
                        {"name": contains},
                        {"symbol": contains},
                        {"slug": contains},
                        {"providers.coingecko.id": contains},
                    ]
                }
            },
            {
                "$addFields": {
                    "_rank": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$providers.coingecko.id", ""]},
                                            "regex": exact_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 0,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$name", ""]},
                                            "regex": exact_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 1,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$symbol", ""]},
                                            "regex": exact_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 2,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$name", ""]},
                                            "regex": starts_with_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 3,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$symbol", ""]},
                                            "regex": starts_with_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 4,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$name", ""]},
                                            "regex": contains_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 5,
                                },
                                {
                                    "case": {
                                        "$regexMatch": {
                                            "input": {"$ifNull": ["$symbol", ""]},
                                            "regex": contains_pattern,
                                            "options": "i",
                                        }
                                    },
                                    "then": 6,
                                },
                            ],
                            "default": 7,
                        }
                    },
                    # MongoDB sorts a missing/null field first in
                    # ascending order — substitute a large sentinel so
                    # coins with no market_cap_rank yet sort *after*
                    # ranked ones within their tier, not before.
                    "_rank_tiebreak": {"$ifNull": ["$market_cap_rank", 10_000_000]},
                }
            },
            {
                "$sort": {
                    "_rank": ASCENDING,
                    "_rank_tiebreak": ASCENDING,
                    "name": ASCENDING,
                }
            },
            {"$limit": limit},
        ]
        # PyMongo's async `AsyncCollection.aggregate()` is itself a
        # coroutine (it issues the command to the server up front,
        # unlike the lazy `find()`), so it must be awaited to obtain
        # the `AsyncCommandCursor` before `to_list()` can be called.
        cursor = await self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=limit)
        return results[:limit]


    async def list_coins(
        self,
        page: int,
        limit: int,
        *,
        is_active: Optional[bool] = None,
        provider: Optional[str] = None,
        sort_by: str = "market_cap_rank",
        sort_direction: int = ASCENDING,
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated coin listing. `sort_by` must be a SORTABLE_FIELDS key."""
        sort_field = SORTABLE_FIELDS.get(sort_by, "market_cap_rank")

        filter_: dict[str, Any] = {}
        if is_active is not None:
            filter_["is_active"] = is_active
        if provider is not None:
            filter_[f"providers.{provider}"] = {"$exists": True}

        total = await self.collection.count_documents(filter_)
        cursor = (
            self.collection.find(filter_)
            .sort(sort_field, sort_direction)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        items = await cursor.to_list(length=limit)
        return items, total

    async def count_active(self) -> int:
        return await self.collection.count_documents({"is_active": True})

    async def deactivate_stale(self, seen_before: datetime) -> int:
        """
        Mark coins inactive if they weren't touched by a sync that
        started at/after `seen_before` (i.e. `updated_at` is still
        older than the sync's start time, meaning the full-universe
        fetch didn't include them anymore).

        Uses `updated_at` rather than collecting every seen ID into an
        in-memory `$nin` list — this stays efficient regardless of how
        many thousands of coins exist. Intended to be called only
        after a *complete* full-universe fetch (see
        `MarketSyncService.sync_full_coin_universe`) — never after a
        single paginated `/coins/markets` page, or active coins not on
        that page would be incorrectly deactivated.
        """
        result = await self.collection.update_many(
            {
                "providers.coingecko.id": {"$exists": True},
                "is_active": True,
                "updated_at": {"$lt": seen_before},
            },
            {"$set": {"is_active": False}},
        )
        return result.modified_count
