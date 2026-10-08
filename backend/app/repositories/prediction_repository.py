"""Prediction repository — storage in the EXISTING `predictions` collection (Phase 2 schema).

Insert-only: every generated prediction is kept (the later user-facing history
feature reads from here). Fresh/stale is decided from `expires_at`; nothing is
overwritten, and `expires_at` is not a TTL index.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class PredictionRepository(BaseRepository):
    collection_name = CollectionName.PREDICTIONS

    async def insert(self, document: dict[str, Any]) -> None:
        await self.collection.insert_one(document)

    async def get_latest(
        self, coin_id: ObjectId, horizon: str, *, model: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        query: dict[str, Any] = {"coin_id": coin_id, "horizon": horizon, "status": "active"}
        if model:
            query["model"] = model
        return await self.collection.find_one(query, sort=[("generated_at", DESCENDING)])

    async def get_latest_any_horizon(self, coin_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one(
            {"coin_id": coin_id, "status": "active"}, sort=[("generated_at", DESCENDING)]
        )

    @staticmethod
    def is_expired(doc: dict[str, Any], now: Optional[datetime] = None) -> bool:
        expires_at = doc.get("expires_at")
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) >= expires_at
