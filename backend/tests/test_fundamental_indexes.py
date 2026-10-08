"""The fundamental_analysis index is created (unit test — no MongoDB needed)."""

from unittest.mock import AsyncMock

from app.database.collections import CollectionName
from app.database.indexes import initialize_indexes


class _FakeDatabase:
    def __init__(self):
        self.collections: dict[str, AsyncMock] = {}

    def __getitem__(self, name: str) -> AsyncMock:
        return self.collections.setdefault(name, AsyncMock())


async def test_fundamental_analysis_gets_a_unique_coin_id_index():
    db = _FakeDatabase()
    await initialize_indexes(db)

    collection = db.collections[CollectionName.FUNDAMENTAL_ANALYSIS.value]
    collection.create_index.assert_awaited_once_with(
        "coin_id", unique=True, name="uniq_fundamentalanalysis_coinid"
    )
