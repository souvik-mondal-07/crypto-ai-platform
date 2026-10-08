"""
Market data repository.

All MongoDB access for the `market_data` collection goes through
here. `market_data` holds ONE upserted "current snapshot" document
per coin (see docs/market-data.md) — it is intentionally not a
growing time series (that's `historical_prices`, unimplemented until
a later step).
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, UpdateOne

from app.database.collections import CollectionName
from app.providers.normalized import NormalizedExchangeTicker, NormalizedMarketData
from app.repositories.base import BaseRepository


class MarketDataRepository(BaseRepository):
    collection_name = CollectionName.MARKET_DATA

    async def bulk_upsert(
        self,
        entries: list[tuple[ObjectId, NormalizedMarketData]],
        data_source: str,
    ) -> dict[str, int]:
        """
        Upsert current market data for a batch of coins.

        `entries` pairs each coin's internal `_id` (already resolved
        by the sync service — this repository never resolves
        CoinGecko IDs itself) with its normalized market snapshot.
        """
        if not entries:
            return {"matched": 0, "upserted": 0}

        now = datetime.now(timezone.utc)
        operations = []
        for coin_object_id, market in entries:
            operations.append(
                UpdateOne(
                    {"coin_id": coin_object_id},
                    {
                        "$set": {
                            "coin_id": coin_object_id,
                            "price_usd": market.price_usd,
                            "market_cap_usd": market.market_cap_usd,
                            "volume_24h_usd": market.volume_24h_usd,
                            "high_24h_usd": market.high_24h_usd,
                            "low_24h_usd": market.low_24h_usd,
                            "percent_change_1h": market.percent_change_1h,
                            "percent_change_24h": market.percent_change_24h,
                            "percent_change_7d": market.percent_change_7d,
                            "percent_change_30d": market.percent_change_30d,
                            "percent_change_1y": market.percent_change_1y,
                            "price_change_24h_usd": market.price_change_24h_usd,
                            "circulating_supply": market.circulating_supply,
                            "total_supply": market.total_supply,
                            "max_supply": market.max_supply,
                            "fully_diluted_valuation_usd": market.fully_diluted_valuation_usd,
                            "ath_usd": market.ath_usd,
                            "atl_usd": market.atl_usd,
                            "ath_change_percentage": market.ath_change_percentage,
                            "atl_change_percentage": market.atl_change_percentage,
                            "ath_date": market.ath_date,
                            "atl_date": market.atl_date,
                            "last_updated": market.last_updated,
                            "data_source": data_source,
                            "updated_at": now,
                        }
                    },
                    upsert=True,
                )
            )

        result = await self.collection.bulk_write(operations, ordered=False)
        return {
            "matched": result.matched_count,
            "upserted": len(result.upserted_ids or {}),
        }

    async def bulk_upsert_binance_prices(
        self,
        entries: list[tuple[ObjectId, NormalizedExchangeTicker]],
        data_source: str = "binance",
    ) -> dict[str, int]:
        """
        Fast-path partial refresh of the live-tracking fields only
        (price, 24h change, 24h high/low, 24h volume) from a Binance
        ticker, for coins with a valid Binance mapping.

        Deliberately narrower than `bulk_upsert`: it never touches
        market_cap_usd, supply, ATH/ATL, or the 1h/7d/30d/1y percent
        changes, since Binance's 24hr ticker doesn't carry those —
        those fields keep whatever value the last full CoinGecko sync
        set, rather than being cleared or guessed at. Only fields the
        ticker actually supplied a value for are written, so a
        momentary gap in one field never overwrites a previously-good
        value with `None`.

        `last_updated` is set to the fetch time: Binance's 24hr ticker
        response carries no separate "as of" timestamp of its own — it
        IS a live snapshot as of the moment of the request — so the
        fetch time is the accurate provider timestamp here, not a
        substitute for a missing one.
        """
        if not entries:
            return {"matched": 0, "upserted": 0}

        now = datetime.now(timezone.utc)
        operations = []
        for coin_object_id, ticker in entries:
            set_fields: dict[str, Any] = {
                "coin_id": coin_object_id,
                "last_updated": now,
                "data_source": data_source,
                "updated_at": now,
            }
            if ticker.last_price is not None:
                set_fields["price_usd"] = ticker.last_price
            if ticker.price_change_percent_24h is not None:
                set_fields["percent_change_24h"] = ticker.price_change_percent_24h
            if ticker.high_24h is not None:
                set_fields["high_24h_usd"] = ticker.high_24h
            if ticker.low_24h is not None:
                set_fields["low_24h_usd"] = ticker.low_24h
            if ticker.quote_volume_24h is not None:
                set_fields["volume_24h_usd"] = ticker.quote_volume_24h

            operations.append(
                UpdateOne({"coin_id": coin_object_id}, {"$set": set_fields}, upsert=True)
            )

        result = await self.collection.bulk_write(operations, ordered=False)
        return {
            "matched": result.matched_count,
            "upserted": len(result.upserted_ids or {}),
        }

    async def get_by_coin_id(self, coin_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"coin_id": coin_id})

    async def get_many_by_coin_ids(self, coin_ids: list[ObjectId]) -> dict[ObjectId, dict[str, Any]]:
        cursor = self.collection.find({"coin_id": {"$in": coin_ids}})
        docs = await cursor.to_list(length=len(coin_ids))
        return {doc["coin_id"]: doc for doc in docs}

    async def get_top_movers(self, direction: str, limit: int) -> list[dict[str, Any]]:
        """
        `direction` is `"gainers"` or `"losers"`. Sorts current
        snapshots by `percent_change_24h` — never returns hard-coded
        or sample data; an empty list means no market data has been
        synced yet.
        """
        sort_direction = DESCENDING if direction == "gainers" else ASCENDING
        cursor = (
            self.collection.find({"percent_change_24h": {"$ne": None}})
            .sort("percent_change_24h", sort_direction)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def get_top_by_field(self, field: str, limit: int) -> list[dict[str, Any]]:
        """
        Highest-ranked current snapshots by a numeric market field
        (e.g. market cap, 24h volume), descending.

        `field` is chosen by the service from a fixed whitelist — a
        raw client string is never passed here (see
        MarketService.RANKABLE_FIELDS).
        """
        cursor = (
            self.collection.find({field: {"$ne": None}})
            .sort(field, DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    #: Computed in-pipeline from synced fields: (high - low) / price * 100.
    #: Null whenever an input is missing, so it never sorts a guess.
    VOLATILITY_FIELD = "volatility_24h_pct"

    @staticmethod
    def _volatility_stage() -> dict[str, Any]:
        return {
            "$addFields": {
                "volatility_24h_pct": {
                    "$cond": [
                        {
                            "$and": [
                                {"$gt": ["$price_usd", 0]},
                                # BSON order puts null below every number, so
                                # `$gt: [x, null]` means "x is a number"
                                # (false for null or missing).
                                {"$gt": ["$high_24h_usd", None]},
                                {"$gt": ["$low_24h_usd", None]},
                                {"$gte": ["$high_24h_usd", "$low_24h_usd"]},
                            ]
                        },
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        {"$subtract": ["$high_24h_usd", "$low_24h_usd"]},
                                        "$price_usd",
                                    ]
                                },
                                100,
                            ]
                        },
                        None,
                    ]
                }
            }
        }

    @staticmethod
    def _range_bounds(minimum: Optional[float], maximum: Optional[float]) -> dict[str, float]:
        bounds: dict[str, float] = {}
        if minimum is not None:
            bounds["$gte"] = minimum
        if maximum is not None:
            bounds["$lte"] = maximum
        return bounds

    async def list_coins_with_market_data(
        self,
        *,
        skip: int,
        limit: int,
        sort_field: str,
        sort_direction: int,
        min_change_24h: Optional[float] = None,
        max_change_24h: Optional[float] = None,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        min_volume: Optional[float] = None,
        max_volume: Optional[float] = None,
        has_max_supply: Optional[bool] = None,
        coin_ids: Optional[list[ObjectId]] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Paginated coins joined with their current market snapshot,
        sortable by market fields (price, 24h change, market cap,
        volume, FDV, supply, volatility) that live in THIS collection
        rather than in `coins`.

        This is why the join runs from the market_data side: sorting by
        a market field requires the sort to happen on the collection
        that holds it, so MongoDB can use an index instead of sorting
        in memory after a lookup.

        `sort_field`, the filter bounds and `coin_ids` are supplied by
        the service after validation — never a raw client string.

        Returns (rows, total). Each row is the market_data document
        with the joined coin under `coin`.
        """
        # The computed volatility key doesn't exist until $addFields runs,
        # so it can't be part of the first $match (a missing field would
        # fail `$ne: None` and exclude every document).
        match_stage: dict[str, Any] = (
            {} if sort_field == self.VOLATILITY_FIELD else {sort_field: {"$ne": None}}
        )

        for field, minimum, maximum in (
            ("percent_change_24h", min_change_24h, max_change_24h),
            ("market_cap_usd", min_market_cap, max_market_cap),
            ("volume_24h_usd", min_volume, max_volume),
        ):
            bounds = self._range_bounds(minimum, maximum)
            if bounds:
                match_stage[field] = bounds

        if has_max_supply is True:
            match_stage["max_supply"] = {"$ne": None, "$gt": 0}
        elif has_max_supply is False:
            # No reported cap: missing, null or zero.
            match_stage["$or"] = [
                {"max_supply": None},
                {"max_supply": 0},
            ]

        if coin_ids is not None:
            match_stage["coin_id"] = {"$in": coin_ids}

        pipeline: list[dict[str, Any]] = [{"$match": match_stage}]

        # A computed sort key has to exist before the sort stage; real
        # stored fields sort first so MongoDB can use their indexes.
        if sort_field == self.VOLATILITY_FIELD:
            pipeline.append(self._volatility_stage())
            pipeline.append({"$match": {self.VOLATILITY_FIELD: {"$ne": None}}})
            # `_id` tie-breaker keeps pages stable for this computed sort
            # (many coins share identical ranges); stored-field sorts keep
            # their original, index-backed behaviour.
            pipeline.append({"$sort": {sort_field: sort_direction, "_id": 1}})
            row_stages: list[dict[str, Any]] = []
        else:
            pipeline.append({"$sort": {sort_field: sort_direction}})
            row_stages = [self._volatility_stage()]

        pipeline.append(
            {
                "$facet": {
                    "rows": [
                        {"$skip": skip},
                        {"$limit": limit},
                        *row_stages,
                        {
                            "$lookup": {
                                "from": CollectionName.COINS.value,
                                "localField": "coin_id",
                                "foreignField": "_id",
                                "as": "coin",
                            }
                        },
                        # Drop rows whose coin was removed/deactivated
                        # between syncs rather than emitting a row with
                        # no name/symbol.
                        {"$match": {"coin": {"$ne": []}}},
                        {"$unwind": "$coin"},
                    ],
                    "total": [{"$count": "value"}],
                }
            }
        )

        # `aggregate()` is a coroutine on PyMongo's async collection:
        # await it for the cursor, then await `to_list()` on that.
        cursor = await self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        if not result:
            return [], 0

        facet = result[0]
        rows = facet.get("rows", [])
        total_list = facet.get("total", [])
        total = total_list[0]["value"] if total_list else 0
        return rows, total

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def most_recent_update(self) -> Optional[datetime]:
        """Used to report overall data freshness on overview/global responses."""
        doc = await self.collection.find_one(sort=[("updated_at", DESCENDING)])
        return doc["updated_at"] if doc else None
