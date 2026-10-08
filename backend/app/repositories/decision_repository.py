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

    @staticmethod
    def is_expired(doc: dict[str, Any], now: Optional[datetime] = None) -> bool:
        expires_at = doc.get("expires_at")
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) >= expires_at
