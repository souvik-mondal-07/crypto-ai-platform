"""Alert repository — the EXISTING `alerts` collection.

User-facing methods always take `user_id`. The two `*_system` methods are the ONLY
cross-user reads/writes and exist solely for the alert-evaluation service (which
must look at every user's active alerts); they are never reachable from an API
route without going through that service.
"""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    collection_name = CollectionName.ALERTS

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def get(self, user_id: ObjectId, alert_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"_id": alert_id, "user_id": user_id})

    async def count_for_user(self, user_id: ObjectId, status: Optional[str] = None) -> int:
        query: dict[str, Any] = {"user_id": user_id}
        if status is not None:
            query["status"] = status
        return await self.collection.count_documents(query)

    async def list_for_user(
        self, user_id: ObjectId, skip: int, limit: int, status: Optional[str] = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if status is not None:
            query["status"] = status
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit), total

    async def update(self, user_id: ObjectId, alert_id: ObjectId, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = await self.collection.update_one({"_id": alert_id, "user_id": user_id}, {"$set": fields})
        if result.matched_count == 0:
            return None
        return await self.get(user_id, alert_id)

    async def delete(self, user_id: ObjectId, alert_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": alert_id, "user_id": user_id})
        return result.deleted_count > 0

    # ---- evaluation (system) -------------------------------------------------

    async def list_active(self, limit: int, user_id: Optional[ObjectId] = None) -> list[dict[str, Any]]:
        """ACTIVE alerts, oldest first. `user_id` narrows to one user (the user-triggered check); omitted = all users."""
        query: dict[str, Any] = {"status": "ACTIVE"}
        if user_id is not None:
            query["user_id"] = user_id
        cursor = self.collection.find(query).sort([("created_at", ASCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def transition_if_active(self, alert_id: ObjectId, fields: dict[str, Any]) -> bool:
        """
        Atomically move an alert out of ACTIVE. The `status: ACTIVE` guard means two overlapping
        evaluation runs (or a user disabling the alert mid-check) can never trigger it twice or
        resurrect a disabled one.
        """
        result = await self.collection.update_one({"_id": alert_id, "status": "ACTIVE"}, {"$set": fields})
        return result.matched_count > 0

    async def touch_checked(self, alert_ids: list[ObjectId], checked_at: datetime) -> None:
        if alert_ids:
            await self.collection.update_many(
                {"_id": {"$in": alert_ids}, "status": "ACTIVE"}, {"$set": {"last_checked_at": checked_at}}
            )
