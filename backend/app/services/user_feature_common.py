"""Shared helpers for the Phase 16 user features (watchlist, portfolio, history, alerts).

Every user-scoped service gets the authenticated user's id from the JWT-backed
`get_current_user` dependency — never from a request body or query string — and
passes it down here as an ObjectId. Nothing in these helpers reads a user id from
client input.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.coin_repository import CoinRepository


def user_object_id(current_user: dict[str, Any]) -> ObjectId:
    """The authenticated user's `_id`, taken from the user document the auth dependency loaded."""
    return current_user["_id"]


def parse_object_id(value: str, code: str, message: str) -> ObjectId:
    """Strict ObjectId parsing: anything that is not a valid 24-char hex id is a 400, never a 500."""
    if not isinstance(value, str) or len(value) != 24 or not ObjectId.is_valid(value):
        raise AppError(400, code, message)
    return ObjectId(value)


def parse_coin_id(value: str) -> ObjectId:
    return parse_object_id(value, "INVALID_COIN_ID", "coin_id is not a valid identifier.")


async def require_coin(coins: CoinRepository, coin_id: str) -> tuple[ObjectId, dict[str, Any]]:
    """Validate the id format and that the coin exists in the synced universe."""
    object_id = parse_coin_id(coin_id)
    doc = await coins.find_by_internal_id(coin_id)
    if doc is None:
        raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
    return object_id, doc


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """MongoDB returns naive UTC datetimes by default; normalise so comparisons never raise."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
