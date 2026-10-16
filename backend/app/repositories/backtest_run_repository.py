"""Backtest runs (Phase 17) — the new `backtest_runs` collection (run metadata + results).

Every read/update is scoped by `user_id` taken from the authenticated user (never from client input),
so one user can never read or influence another user's run.
"""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository

ACTIVE_STATUSES = ["queued", "running"]


class BacktestRunRepository(BaseRepository):
    collection_name = CollectionName.BACKTEST_RUNS

    async def insert(self, document: dict[str, Any]) -> None:
        await self.collection.insert_one(document)

    async def get_for_user(self, user_id: ObjectId, run_id: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"user_id": user_id, "run_id": run_id})

    async def list_for_user(self, user_id: ObjectId, *, skip: int, limit: int) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {"user_id": user_id}, {"trades": 0, "equity_curve": 0, "benchmark_curve": 0, "closed_trades": 0}
        ).sort([("created_at", DESCENDING)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    async def count_active_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id, "status": {"$in": ACTIVE_STATUSES}})

    async def update_for_user(self, user_id: ObjectId, run_id: str, fields: dict[str, Any]) -> None:
        await self.collection.update_one({"user_id": user_id, "run_id": run_id}, {"$set": fields})

    async def fail_stale(self, before: datetime, now: datetime, message: str) -> int:
        """Runs still queued/running although their last update is older than `before` (process restarted)."""
        res = await self.collection.update_many(
            {"status": {"$in": ACTIVE_STATUSES}, "updated_at": {"$lt": before}},
            {"$set": {"status": "failed", "error": message, "updated_at": now, "finished_at": now}},
        )
        return res.modified_count
