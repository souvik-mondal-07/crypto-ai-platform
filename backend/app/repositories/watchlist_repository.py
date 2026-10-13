"""Watchlist repository — the EXISTING `watchlists` collection, one document per (user_id, coin_id).

Every query includes `user_id`; there is deliberately no method that reads or writes
without it. Uniqueness of (user_id, coin_id) is enforced by a unique index (see
app/database/indexes.py), not only by an application-level check.
"""

from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class WatchlistEntryExistsError(Exception):
    """The coin is already on this user's watchlist (unique-index violation)."""


class WatchlistRepository(BaseRepository):
    collection_name = CollectionName.WATCHLISTS

    async def add(self, user_id: ObjectId, coin_id: ObjectId, now: datetime) -> dict[str, Any]:
        document = {"user_id": user_id, "coin_id": coin_id, "created_at": now, "updated_at": now}
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise WatchlistEntryExistsError() from exc
        document["_id"] = result.inserted_id
        return document

    async def remove(self, user_id: ObjectId, coin_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"user_id": user_id, "coin_id": coin_id})
        return result.deleted_count > 0

    async def exists(self, user_id: ObjectId, coin_id: ObjectId) -> bool:
        return await self.collection.count_documents({"user_id": user_id, "coin_id": coin_id}, limit=1) > 0

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    async def list_for_user(self, user_id: ObjectId, skip: int, limit: int) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort([("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
