"""
Fundamental-analysis repository (Phase 11).

One upserted document per coin (unique `coin_id`). It stores only what
`market_data` does NOT already hold:

  - provider-fetched project/ecosystem data (slow-changing, cached with
    a TTL): `project_info`, `ecosystem`, `tokenomics`, `fetched_at`
  - this platform's latest calculation snapshot: `calculated`,
    `fundamental_score`, `development_activity_score`, `calculated_at`

Market values (market cap, supply, ATH/ATL, ...) are deliberately NOT
copied here — they are read live from `market_data` so there is one
source of truth and no second copy to drift out of sync.

The two write paths ($set of disjoint fields) never overwrite each
other: refreshing the provider profile leaves the last calculation
intact, and vice versa.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class FundamentalAnalysisRepository(BaseRepository):
    collection_name = CollectionName.FUNDAMENTAL_ANALYSIS

    async def get_by_coin_id(self, coin_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"coin_id": coin_id})

    async def save_profile(
        self, coin_id: ObjectId, symbol: str, payload: dict[str, Any], fetched_at: datetime
    ) -> None:
        """Persist freshly fetched provider project/ecosystem data."""
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"coin_id": coin_id},
            {
                "$set": {
                    **payload,
                    "symbol": symbol,
                    "source": "coingecko",
                    "fetched_at": fetched_at,
                    "updated_at": now,
                },
                "$setOnInsert": {"coin_id": coin_id, "created_at": now},
            },
            upsert=True,
        )

    async def save_analysis(
        self, coin_id: ObjectId, symbol: str, payload: dict[str, Any], calculated_at: datetime
    ) -> None:
        """Persist the latest calculated metrics/score snapshot."""
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"coin_id": coin_id},
            {
                "$set": {
                    **payload,
                    "symbol": symbol,
                    "calculated_at": calculated_at,
                    # Kept for continuity with the schema documented in Step 2.
                    "timestamp": calculated_at,
                    "updated_at": now,
                },
                "$setOnInsert": {"coin_id": coin_id, "created_at": now},
            },
            upsert=True,
        )

    @staticmethod
    def age_seconds(fetched_at: Optional[datetime]) -> Optional[float]:
        """Age of a timestamp in seconds, or None if it's missing."""
        if fetched_at is None:
            return None
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - fetched_at).total_seconds()
