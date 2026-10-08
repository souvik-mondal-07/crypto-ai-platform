"""
Generic repository base class.

Established in Step 2 as the pattern feature-specific repositories
subclass. `CoinRepository` and `MarketDataRepository` (Step 3) are the
first concrete implementations.
"""

from typing import Any, Optional

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection

from app.database.collections import CollectionName
from app.database.database import get_collection


class BaseRepository:
    """
    Thin wrapper around a single collection, giving subclasses a
    consistent way to reach their collection without importing the
    database layer directly or hard-coding a collection name string.
    """

    collection_name: CollectionName

    @property
    def collection(self) -> AsyncCollection:
        return get_collection(self.collection_name)

    async def find_by_id(self, document_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single document by its ObjectId (as a string)."""
        if not ObjectId.is_valid(document_id):
            return None
        return await self.collection.find_one({"_id": ObjectId(document_id)})

    async def count(self, filter_: Optional[dict[str, Any]] = None) -> int:
        return await self.collection.count_documents(filter_ or {})
