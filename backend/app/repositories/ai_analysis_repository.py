"""AI analysis repository (Phase 15) — storage in the `ai_analysis` collection.

Insert-only, like `decisions`/`predictions`: every generated analysis is kept (later phases compare
prompt versions / models from here). Fresh vs expired is decided from `expires_at`; it is NOT a TTL index.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class AIAnalysisRepository(BaseRepository):
    collection_name = CollectionName.AI_ANALYSIS

    async def insert(self, document: dict[str, Any]) -> None:
        await self.collection.insert_one(document)

    async def get_latest(
        self, coin_id: ObjectId, *, prompt_version: Optional[str] = None, model: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        query: dict[str, Any] = {"coin_id": coin_id, "status": "ready"}
        if prompt_version is not None:
            query["prompt_version"] = prompt_version
        if model is not None:
            query["model"] = model
        return await self.collection.find_one(query, sort=[("generated_at", DESCENDING)])

    @staticmethod
    def is_expired(doc: dict[str, Any], now: Optional[datetime] = None) -> bool:
        expires_at = doc.get("expires_at")
        if expires_at is None:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) >= expires_at
