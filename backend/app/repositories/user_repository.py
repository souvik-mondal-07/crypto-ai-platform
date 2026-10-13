"""
User repository.

All MongoDB access for the `users` collection goes through here — the
auth service, auth dependency, and API routes never issue a `users`
query directly. Email normalization (lowercase + trim) happens here
so every caller gets consistent behavior automatically, rather than
relying on every caller remembering to normalize first.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from app.database.collections import CollectionName
from app.repositories.base import BaseRepository


def normalize_email(email: str) -> str:
    """Consistent email normalization: trim whitespace, lowercase. Used everywhere an email is read or written."""
    return email.strip().lower()


class EmailAlreadyExistsError(Exception):
    """Raised when a create/update would violate the unique email index."""


class UserRepository(BaseRepository):
    collection_name = CollectionName.USERS

    async def create_user(self, *, name: str, email: str, password_hash: str) -> dict[str, Any]:
        """
        Insert a new user document. Relies on MongoDB's unique index on
        `email` as the actual source of truth for uniqueness — the
        `DuplicateKeyError` this raises on a race is translated into
        `EmailAlreadyExistsError` here so callers never see a raw
        PyMongo exception. An application-level pre-check
        (`email_exists`) is used first for a fast/clean path, but the
        index is what actually prevents a duplicate under concurrent
        requests.
        """
        now = datetime.now(timezone.utc)
        document = {
            "name": name,
            "email": normalize_email(email),
            "password_hash": password_hash,
            "is_active": True,
            "role": "user",
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise EmailAlreadyExistsError() from exc

        document["_id"] = result.inserted_id
        return document

    async def find_by_email(self, email: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"email": normalize_email(email)})

    async def email_exists(self, email: str) -> bool:
        count = await self.collection.count_documents({"email": normalize_email(email)}, limit=1)
        return count > 0

    # ---- Phase 16: profile / password / settings (always keyed by the authenticated user's _id) ----

    async def update_name(self, user_id, name: str) -> Optional[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one({"_id": user_id}, {"$set": {"name": name, "updated_at": now}})
        if result.matched_count == 0:
            return None
        return await self.collection.find_one({"_id": user_id})

    async def update_password_hash(self, user_id, password_hash: str) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"_id": user_id}, {"$set": {"password_hash": password_hash, "password_changed_at": now, "updated_at": now}}
        )
        return result.matched_count > 0

    async def get_settings(self, user_id) -> dict[str, Any]:
        doc = await self.collection.find_one({"_id": user_id}, {"settings": 1})
        return dict((doc or {}).get("settings") or {})

    async def update_settings(self, user_id, fields: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Merge the given dotted settings fields (e.g. {"settings.theme": "dark"}) into the user's own document."""
        now = datetime.now(timezone.utc)
        result = await self.collection.update_one({"_id": user_id}, {"$set": {**fields, "updated_at": now}})
        if result.matched_count == 0:
            return None
        return await self.get_settings(user_id)
