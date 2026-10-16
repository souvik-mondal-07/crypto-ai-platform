"""Evaluated outcomes (Phase 17) — the EXISTING `prediction_results` collection.

One document per (record_type, source_id, horizon):
  * record_type "prediction": a matured prediction compared with the actual market price
  * record_type "decision":   a stored BUY/HOLD/SELL decision compared with the subsequent return
Upserts make evaluation idempotent (the unique index guarantees no duplicates); results are derived purely
from stored predictions/decisions and real candles, never from user input.
"""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository

PREDICTION = "prediction"
DECISION = "decision"


class EvaluationResultRepository(BaseRepository):
    collection_name = CollectionName.PREDICTION_RESULTS

    async def upsert(self, document: dict[str, Any]) -> None:
        key = {"record_type": document["record_type"], "source_id": document["source_id"], "horizon": document["horizon"]}
        await self.collection.update_one(key, {"$set": document}, upsert=True)

    async def existing_keys(self, record_type: str, source_ids: list[ObjectId]) -> set[tuple[ObjectId, str]]:
        """(source_id, horizon) pairs that already have a stored result."""
        if not source_ids:
            return set()
        docs = await self.collection.find(
            {"record_type": record_type, "source_id": {"$in": source_ids}}, {"source_id": 1, "horizon": 1}
        ).to_list(length=None)
        return {(d["source_id"], d["horizon"]) for d in docs}

    @staticmethod
    def _query(record_type: str, *, coin_id: Optional[ObjectId] = None, horizon: Optional[str] = None,
               model: Optional[str] = None, model_version: Optional[str] = None,
               status: Optional[str] = None, engine_version: Optional[str] = None) -> dict[str, Any]:
        q: dict[str, Any] = {"record_type": record_type}
        for key, value in (("coin_id", coin_id), ("horizon", horizon), ("model", model),
                           ("model_version", model_version), ("status", status), ("engine_version", engine_version)):
            if value is not None:
                q[key] = value
        return q

    async def find(self, record_type: str, *, limit: int, **filters: Any) -> list[dict[str, Any]]:
        cursor = self.collection.find(self._query(record_type, **filters)).sort([("target_time", DESCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def count(self, record_type: str, **filters: Any) -> int:  # type: ignore[override]
        return await self.collection.count_documents(self._query(record_type, **filters))

    async def latest_evaluated_at(self, record_type: str) -> Optional[datetime]:
        doc = await self.collection.find_one({"record_type": record_type}, sort=[("evaluated_at", DESCENDING)])
        return doc.get("evaluated_at") if doc else None

    async def distinct_pairs(self, record_type: str, limit: int = 5000) -> list[dict[str, Any]]:
        """Light projection used to build the model/version/coin filter options."""
        docs = await self.collection.find(
            {"record_type": record_type, "status": "matched"}, {"model": 1, "model_version": 1, "coin_id": 1, "symbol": 1, "horizon": 1}
        ).limit(limit).to_list(length=limit)
        return docs
