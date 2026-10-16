"""Decision repository (Phase 14) — storage in the EXISTING `decisions` collection (Phase 2 schema).

Insert-only, like `predictions`: every generated decision is kept (the later
history / backtesting phases read from here). Fresh vs expired is decided from
`expires_at`; nothing is overwritten and `expires_at` is NOT a TTL index.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class DecisionRepository(BaseRepository):
    collection_name = CollectionName.DECISIONS

    async def insert(self, document: dict[str, Any]) -> None:
        await self.collection.insert_one(document)

    async def get_latest(self, coin_id: ObjectId, engine_version: Optional[str] = None) -> Optional[dict[str, Any]]:
        query: dict[str, Any] = {"coin_id": coin_id}
        if engine_version is not None:
            query["engine_version"] = engine_version
        return await self.collection.find_one(query, sort=[("generated_at", DESCENDING)])

    # --- Phase 17: read-only helpers for decision evaluation / backtests ---

    async def list_between(
        self, coin_id: ObjectId, start: datetime, end: datetime, *, limit: int = 20_000
    ) -> list[dict[str, Any]]:
        """A coin's stored decisions with start <= generated_at < end, OLDEST first (chronological)."""
        cursor = self.collection.find(
            {"coin_id": coin_id, "generated_at": {"$gte": start, "$lt": end}},
            {"decision": 1, "status": 1, "generated_at": 1, "engine_version": 1, "symbol": 1, "coin_id": 1, "confidence": 1},
        ).sort([("generated_at", 1), ("_id", 1)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def list_matured(self, before: datetime, *, skip: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """Decisions old enough for at least the shortest evaluation horizon, newest first."""
        cursor = self.collection.find(
            {"generated_at": {"$lte": before}},
            {"decision": 1, "status": 1, "generated_at": 1, "engine_version": 1, "symbol": 1, "coin_id": 1, "confidence": 1},
        ).sort([("generated_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_total(self) -> int:
        return await self.collection.count_documents({})

    @staticmethod
    def is_expired(doc: dict[str, Any], now: Optional[datetime] = None) -> bool:
        expires_at = doc.get("expires_at")
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) >= expires_at
