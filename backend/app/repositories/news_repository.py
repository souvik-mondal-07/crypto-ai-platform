"""
News repository (Phase 12) — all MongoDB access for the `news` collection.

Writes are idempotent upserts keyed on EITHER the public `news_id` or
the `dedupe_key`, so re-running ingestion (or two providers carrying the
same story) never creates a second record. A re-fetched article only
refreshes its tags/related coins; its title/description and any computed
sentiment are left untouched, so sentiment can never go stale against
the text it was computed from.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING, UpdateOne
from pymongo.errors import BulkWriteError

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


@dataclass
class UpsertCounts:
    inserted: int = 0
    existing: int = 0
    failed: int = 0


def build_news_filter(
    *,
    coin_id: Optional[ObjectId] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict[str, Any]:
    """Backend filter for the list endpoints (pure; unit-tested). User text is regex-escaped."""
    filter_: dict[str, Any] = {}
    if coin_id is not None:
        filter_["related_coin_ids"] = coin_id
    if source:
        filter_["source"] = source
    if sentiment:
        filter_["sentiment.label"] = sentiment
    if date_from or date_to:
        window: dict[str, Any] = {}
        if date_from:
            window["$gte"] = date_from
        if date_to:
            window["$lte"] = date_to
        filter_["published_at"] = window
    if search:
        pattern = {"$regex": re.escape(search.strip()), "$options": "i"}
        filter_["$or"] = [{"title": pattern}, {"description": pattern}]
    return filter_


class NewsRepository(BaseRepository):
    collection_name = CollectionName.NEWS

    async def upsert_articles(self, documents: list[dict[str, Any]]) -> UpsertCounts:
        if not documents:
            return UpsertCounts()
        now = datetime.now(timezone.utc)
        operations = []
        for doc in documents:
            insert_only = {
                k: v
                for k, v in doc.items()
                if k not in ("related_coin_ids", "related_symbols", "categories", "tags")
            }
            insert_only["created_at"] = now
            operations.append(
                UpdateOne(
                    {"$or": [{"news_id": doc["news_id"]}, {"dedupe_key": doc["dedupe_key"]}]},
                    {
                        "$set": {"updated_at": now},
                        "$addToSet": {
                            "related_coin_ids": {"$each": doc.get("related_coin_ids", [])},
                            "related_symbols": {"$each": doc.get("related_symbols", [])},
                            "categories": {"$each": doc.get("categories", [])},
                            "tags": {"$each": doc.get("tags", [])},
                        },
                        "$setOnInsert": insert_only,
                    },
                    upsert=True,
                )
            )
        try:
            result = await self.collection.bulk_write(operations, ordered=False)
            inserted = len(result.upserted_ids or {})
            return UpsertCounts(inserted=inserted, existing=result.matched_count)
        except BulkWriteError as exc:
            details = exc.details or {}
            return UpsertCounts(
                inserted=len(details.get("upserted", [])),
                existing=details.get("nMatched", 0),
                failed=len(details.get("writeErrors", [])),
            )

    async def list_articles(
        self, filter_: dict[str, Any], page: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        total = await self.collection.count_documents(filter_)
        cursor = (
            self.collection.find(filter_)
            .sort([("published_at", DESCENDING), ("_id", DESCENDING)])
            .skip((page - 1) * limit)
            .limit(limit)
        )
        return await cursor.to_list(length=limit), total

    async def get_by_news_id(self, news_id: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"news_id": news_id})

    async def list_sources(self) -> list[str]:
        sources = await self.collection.distinct("source")
        return sorted((s for s in sources if isinstance(s, str) and s), key=str.lower)

    async def find_pending_sentiment(self, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find(
                {"sentiment_status": "pending"}, {"news_id": 1, "title": 1, "description": 1}
            )
            .sort("published_at", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def save_sentiments(self, updates: list[tuple[str, dict[str, Any]]]) -> int:
        """Persist `(news_id, sentiment document)` pairs; returns how many were modified."""
        if not updates:
            return 0
        now = datetime.now(timezone.utc)
        operations = [
            UpdateOne(
                {"news_id": news_id, "sentiment_status": "pending"},
                {"$set": {"sentiment": sentiment, "sentiment_status": "analyzed", "updated_at": now}},
            )
            for news_id, sentiment in updates
        ]
        result = await self.collection.bulk_write(operations, ordered=False)
        return result.modified_count

    async def sentiment_points_for_coin(
        self, coin_id: ObjectId, since: datetime, until: datetime, limit: int = 10_000
    ) -> list[dict[str, Any]]:
        """Analyzed articles for a coin in [since, until] — only the fields aggregation needs."""
        cursor = self.collection.find(
            {
                "related_coin_ids": coin_id,
                "sentiment_status": "analyzed",
                "published_at": {"$gte": since, "$lte": until},
            },
            {"published_at": 1, "sentiment.label": 1, "sentiment.score": 1},
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_pending_for_coin(self, coin_id: ObjectId, since: datetime) -> int:
        return await self.collection.count_documents(
            {
                "related_coin_ids": coin_id,
                "sentiment_status": "pending",
                "published_at": {"$gte": since},
            }
        )
