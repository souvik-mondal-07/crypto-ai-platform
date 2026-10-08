"""
Centralized MongoDB client.

One application-level client is created at FastAPI startup and reused
for the lifetime of the process — never create a client per request.
Uses PyMongo's async API (AsyncMongoClient), introduced in PyMongo 4.9.
"""

import logging
from typing import Optional

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.config import get_settings

logger = logging.getLogger("crypto_ai_platform.database")

_client: Optional[AsyncMongoClient] = None


def create_client() -> AsyncMongoClient:
    """
    Create (but do not yet verify) the application's MongoDB client.

    Does not raise on an unreachable server — PyMongo connects lazily.
    Reachability is confirmed separately via `ping_database()`.
    """
    settings = get_settings()
    return AsyncMongoClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )


async def connect() -> AsyncMongoClient:
    """
    Initialize the module-level client if it doesn't exist yet, and
    verify connectivity with a ping. Called once from the FastAPI
    lifespan on startup.

    Raises PyMongoError if MongoDB is unreachable — callers decide how
    to handle that (see app/main.py, which logs a clean message rather
    than crashing with a raw traceback).
    """
    global _client
    if _client is None:
        _client = create_client()

    await _client.admin.command("ping")
    logger.info("MongoDB connection established.")
    return _client


async def disconnect() -> None:
    """Close the MongoDB client cleanly. Called from the FastAPI lifespan on shutdown."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("MongoDB connection closed.")


def get_client() -> Optional[AsyncMongoClient]:
    """Return the current client instance, or None if not yet connected."""
    return _client


async def ping_database() -> bool:
    """
    Lightweight reachability check, safe to call at any time (e.g. from
    the health endpoint). Returns False instead of raising if MongoDB
    is unavailable or the client hasn't been initialized.
    """
    if _client is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except PyMongoError as exc:
        logger.warning("MongoDB ping failed: %s", exc.__class__.__name__)
        return False
