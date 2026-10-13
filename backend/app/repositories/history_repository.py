"""Analysis-history repository — the EXISTING `analysis_history` collection.

One document per recorded user action (viewing/generating an analysis). Only
references and short labels are stored — never the analysis itself, and never
anything sensitive. Every query is scoped by `user_id`.
"""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class HistoryRepository(BaseRepository):
    collection_name = CollectionName.ANALYSIS_HISTORY

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def find_recent_duplicate(
        self, user_id: ObjectId, coin_id: ObjectId, analysis_type: str, since: datetime
    ) -> Optional[dict[str, Any]]:
        """The user's own most recent identical entry at/after `since` (used to avoid duplicate rows on re-render)."""
        return await self.collection.find_one(
            {"user_id": user_id, "coin_id": coin_id, "analysis_type": analysis_type, "created_at": {"$gte": since}},
            sort=[("created_at", DESCENDING)],
        )

    async def get(self, user_id: ObjectId, entry_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"_id": entry_id, "user_id": user_id})

    async def delete(self, user_id: ObjectId, entry_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": entry_id, "user_id": user_id})
        return result.deleted_count > 0

    async def list_for_user(
        self,
        user_id: ObjectId,
        skip: int,
        limit: int,
        coin_id: Optional[ObjectId] = None,
        analysis_type: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if coin_id is not None:
            query["coin_id"] = coin_id
        if analysis_type is not None:
            query["analysis_type"] = analysis_type
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit), total
