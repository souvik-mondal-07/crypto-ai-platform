"""Portfolio repositories — the EXISTING `portfolios` and `portfolio_transactions` collections.

`portfolios` holds ONE document per (user_id, coin_id): the user's recorded holding
(quantity + average buy price). `portfolio_transactions` is an append-only ledger of
the user's recorded buys/adjustments. This is record-keeping only — nothing here
touches an exchange. Every query is scoped by `user_id`.
"""

from typing import Any, Optional

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


class HoldingExistsError(Exception):
    """A holding for this (user, coin) already exists (unique-index violation on a concurrent insert)."""


class PortfolioRepository(BaseRepository):
    collection_name = CollectionName.PORTFOLIOS

    async def get(self, user_id: ObjectId, coin_id: ObjectId) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"user_id": user_id, "coin_id": coin_id})

    async def list_for_user(self, user_id: ObjectId, limit: int) -> list[dict[str, Any]]:
        cursor = self.collection.find({"user_id": user_id}).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_for_user(self, user_id: ObjectId) -> int:
        return await self.collection.count_documents({"user_id": user_id})

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise HoldingExistsError() from exc
        document["_id"] = result.inserted_id
        return document

    async def update(self, user_id: ObjectId, coin_id: ObjectId, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Update only this user's holding; returns the updated document or None if it doesn't exist."""
        result = await self.collection.update_one({"user_id": user_id, "coin_id": coin_id}, {"$set": fields})
        if result.matched_count == 0:
            return None
        return await self.get(user_id, coin_id)

    async def delete(self, user_id: ObjectId, coin_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"user_id": user_id, "coin_id": coin_id})
        return result.deleted_count > 0


class PortfolioTransactionRepository(BaseRepository):
    collection_name = CollectionName.PORTFOLIO_TRANSACTIONS

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def list_for_user(
        self, user_id: ObjectId, skip: int, limit: int, coin_id: Optional[ObjectId] = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if coin_id is not None:
            query["coin_id"] = coin_id
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit), total

    async def delete_for_coin(self, user_id: ObjectId, coin_id: ObjectId) -> int:
        result = await self.collection.delete_many({"user_id": user_id, "coin_id": coin_id})
        return result.deleted_count


