"""
Database layer tests.

Split into two groups:

- Unit tests (no `integration` marker): exercise client creation,
  collection-name registry, and error handling WITHOUT requiring a
  running MongoDB instance.
- Integration tests (marked `@pytest.mark.integration`): require an
  actual reachable MongoDB (see docs/development.md for how to start
  one locally). These are skipped automatically if MongoDB isn't
  reachable, rather than failing the whole suite in an environment
  that doesn't have it installed.

Run only unit tests:   pytest -m "not integration"
Run only integration:  pytest -m integration
"""

import pytest
from pymongo.errors import PyMongoError

from app.database import client as db_client
from app.database.collections import CollectionName
from app.database.database import get_database


# ---------------------------------------------------------------------------
# Unit tests — no MongoDB required
# ---------------------------------------------------------------------------

def test_create_client_does_not_require_reachable_server():
    """
    PyMongo connects lazily — constructing a client must not raise
    even if nothing is listening at MONGODB_URI.
    """
    test_client = db_client.create_client()
    assert test_client is not None


def test_collection_name_registry_has_all_planned_collections():
    expected = {
        "users", "coins", "market_data", "historical_prices",
        "technical_analysis", "fundamental_analysis", "news",
        "sentiment", "predictions", "decisions", "ai_analysis", "prediction_results",
        "watchlists", "portfolios", "portfolio_transactions", "alerts",
        "analysis_history", "model_metrics",
    }
    actual = {c.value for c in CollectionName}
    assert expected == actual


def test_get_database_raises_clean_error_before_connect():
    """
    Calling get_database() before the lifespan has established a
    connection must raise a clear RuntimeError, not a confusing
    AttributeError/TypeError from a None client deep in a query.
    """
    # Ensure no client is set for this test's purposes.
    db_client._client = None  # noqa: SLF001 — intentional for this test
    with pytest.raises(RuntimeError):
        get_database()


@pytest.mark.asyncio
async def test_ping_database_returns_false_without_client():
    db_client._client = None  # noqa: SLF001 — intentional for this test
    result = await db_client.ping_database()
    assert result is False


# ---------------------------------------------------------------------------
# Integration tests — require a reachable MongoDB
# ---------------------------------------------------------------------------

async def _mongodb_reachable() -> bool:
    try:
        test_client = db_client.create_client()
        await test_client.admin.command("ping")
        await test_client.close()
        return True
    except PyMongoError:
        return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connect_and_ping_against_real_mongodb():
    if not await _mongodb_reachable():
        pytest.skip("MongoDB is not reachable at the configured MONGODB_URI.")

    await db_client.connect()
    try:
        assert await db_client.ping_database() is True
    finally:
        await db_client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_index_initialization_does_not_crash():
    if not await _mongodb_reachable():
        pytest.skip("MongoDB is not reachable at the configured MONGODB_URI.")

    from app.database.indexes import initialize_indexes

    await db_client.connect()
    try:
        db = get_database()
        await initialize_indexes(db)  # must not raise
    finally:
        await db_client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disconnect_clears_client():
    if not await _mongodb_reachable():
        pytest.skip("MongoDB is not reachable at the configured MONGODB_URI.")

    await db_client.connect()
    await db_client.disconnect()
    assert db_client.get_client() is None
