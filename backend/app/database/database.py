"""
Database-level accessor utilities.

Provides `get_database()` / `get_collection()` so the rest of the app
never touches the raw client or hard-codes a database name.
"""

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection

from app.config import get_settings
from app.database.client import get_client
from app.database.collections import CollectionName


def get_database() -> AsyncDatabase:
    """
    Return the application's database handle.

    Raises RuntimeError if called before the connection has been
    established (i.e. outside the FastAPI lifespan, or if startup
    connection failed) — this is intentionally loud rather than
    silently returning None and letting a query fail with a confusing
    error deeper in the stack.
    """
    client = get_client()
    if client is None:
        raise RuntimeError(
            "MongoDB client is not initialized. The application lifespan "
            "must establish a connection before the database can be used."
        )
    settings = get_settings()
    return client[settings.MONGODB_DATABASE]


def get_collection(name: CollectionName) -> AsyncCollection:
    """
    Return a collection handle by its centralized name.

    Usage: `get_collection(CollectionName.COINS)` — never pass a raw
    string literal here; add it to `CollectionName` instead.
    """
    return get_database()[name.value]
