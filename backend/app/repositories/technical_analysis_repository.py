"""
Technical-analysis repository.

Storage shape follows docs/database-schema.md's `technical_analysis`
collection. Like `market_data`, this holds one upserted "latest
snapshot" document per (coin_id, timeframe) rather than an
ever-growing history — recomputing technical analysis is cheap enough
(one provider call + pure-Python math) that keeping every past
snapshot isn't needed yet, and this keeps the collection's read path
identical to `market_data`'s. A compound index on
`(coin_id, timeframe)` is the query pattern this repository relies on.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class TechnicalAnalysisRepository(BaseRepository):
    collection_name = CollectionName.TECHNICAL_ANALYSIS

    async def get_latest(self, coin_id: ObjectId, timeframe: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"coin_id": coin_id, "timeframe": timeframe})

    async def upsert(self, coin_id: ObjectId, timeframe: str, payload: dict[str, Any]) -> None:
        """
        Upserts the latest technical-analysis snapshot for one
        (coin_id, timeframe) pair. `payload` is the full document body
        the service has already assembled (symbol, calculated_at,
        indicator values, etc.) — this repository does not shape or
        validate indicator data, only persists it.
        """
        await self.collection.update_one(
            {"coin_id": coin_id, "timeframe": timeframe},
            {"$set": {**payload, "coin_id": coin_id, "timeframe": timeframe}},
            upsert=True,
        )

    @staticmethod
    def is_stale(doc: dict[str, Any], max_age_seconds: int) -> bool:
        calculated_at = doc.get("calculated_at")
        if calculated_at is None:
            return True
        if calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - calculated_at).total_seconds()
        return age > max_age_seconds
