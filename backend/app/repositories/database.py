"""
Repository-layer database access utility.

Kept separate from `app/database/database.py` (the low-level
client/db accessor) so repositories have a single, obvious import for
the one thing they actually need: "is the database ready to query".
"""

from app.database.client import ping_database


async def ensure_database_ready() -> bool:
    """
    Convenience check a repository can call before an operation it
    wants to fail fast/clean on, rather than letting a PyMongo
    exception bubble up from deep inside a query.
    """
    return await ping_database()
