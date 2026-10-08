"""
Integration tests for CoinRepository / MarketDataRepository against a
real MongoDB instance. Skipped automatically if MongoDB isn't
reachable — see tests/test_database.py for the same pattern.

Each test cleans up the specific documents it creates rather than
truncating the whole collection, so this is safe to run against a
shared development database.
"""

from datetime import datetime, timezone

import pytest
from pymongo.errors import PyMongoError

from app.database import client as db_client
from app.database.database import get_database
from app.database.indexes import initialize_indexes
from app.providers.normalized import NormalizedCoin, NormalizedExchangeTicker, NormalizedMarketData
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository


async def _mongodb_reachable() -> bool:
    try:
        test_client = db_client.create_client()
        await test_client.admin.command("ping")
        await test_client.close()
        return True
    except PyMongoError:
        return False


@pytest.fixture
async def connected_db():
    if not await _mongodb_reachable():
        pytest.skip("MongoDB is not reachable at the configured MONGODB_URI.")
    await db_client.connect()
    await initialize_indexes(get_database())
    yield
    await db_client.disconnect()


TEST_COINGECKO_ID = "test-fixture-coin-step3"


async def _cleanup(coin_repo: CoinRepository, market_repo: MarketDataRepository):
    doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)
    if doc:
        await coin_repo.collection.delete_one({"_id": doc["_id"]})
        await market_repo.collection.delete_one({"coin_id": doc["_id"]})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_upsert_coin_then_update_does_not_duplicate(connected_db):
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(
            coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin",
        )
        first = await coin_repo.bulk_upsert_from_coingecko([coin])
        assert first["upserted"] == 1
        assert first["matched"] == 0

        updated_coin = NormalizedCoin(
            coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin (renamed)",
            market_cap_rank=9999,
        )
        second = await coin_repo.bulk_upsert_from_coingecko([updated_coin])
        assert second["upserted"] == 0
        assert second["matched"] == 1

        doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)
        assert doc["name"] == "Test Fixture Coin (renamed)"
        assert doc["market_cap_rank"] == 9999

        # Only one document should exist for this coingecko_id.
        count = await coin_repo.collection.count_documents(
            {"providers.coingecko.id": TEST_COINGECKO_ID}
        )
        assert count == 1
    finally:
        await _cleanup(coin_repo, market_repo)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_market_data_upsert_and_gainers_query(connected_db):
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin")
        await coin_repo.bulk_upsert_from_coingecko([coin])
        doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)

        market = NormalizedMarketData(
            coingecko_id=TEST_COINGECKO_ID,
            price_usd=1.23,
            # Deliberately astronomical: get_top_movers("gainers") sorts
            # every document in the (possibly shared/dev-seeded)
            # collection by percent_change_24h descending with no cap,
            # so the fixture's own value must be provably higher than
            # anything a real coin could ever report — 987.6 (i.e. a
            # ~10x move) is well within range for real, volatile coins
            # and was observed to occasionally lose the "top gainer"
            # spot to genuine market data. A ten-orders-of-magnitude
            # value keeps this test deterministic and independent of
            # whatever unrelated data happens to exist in MongoDB,
            # without weakening the gainers[0] assertion itself.
            percent_change_24h=987_654_321.0,
            last_updated=datetime.now(timezone.utc),
        )
        result = await market_repo.bulk_upsert([(doc["_id"], market)], data_source="coingecko")
        assert result["upserted"] == 1

        fetched = await market_repo.get_by_coin_id(doc["_id"])
        assert fetched["price_usd"] == 1.23
        assert fetched["percent_change_24h"] == 987_654_321.0

        gainers = await market_repo.get_top_movers("gainers", limit=1)
        assert gainers[0]["coin_id"] == doc["_id"]
    finally:
        await _cleanup(coin_repo, market_repo)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coin_search_is_case_insensitive(connected_db):
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(
            coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin",
        )
        await coin_repo.bulk_upsert_from_coingecko([coin])

        for query in ("test fixture", "TEST FIXTURE", "TfX", "tfx"):
            results = await coin_repo.search(query, limit=10)
            matched = [r for r in results if r["providers"]["coingecko"]["id"] == TEST_COINGECKO_ID]
            assert matched, f"query {query!r} should have matched the fixture coin"
    finally:
        await _cleanup(coin_repo, market_repo)


# ---------------------------------------------------------------------------
# Real-time refresh upgrade — Binance fast-price partial upsert
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_binance_mapped_returns_only_mapped_active_coins(connected_db):
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin")
        await coin_repo.bulk_upsert_from_coingecko([coin])
        doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)

        # Before mapping: must not show up in list_binance_mapped.
        before = {coin_id for coin_id, _symbol in await coin_repo.list_binance_mapped()}
        assert doc["_id"] not in before

        await coin_repo.set_binance_mapping(TEST_COINGECKO_ID, "TFXUSDT")

        after = dict(await coin_repo.list_binance_mapped())
        assert after.get(doc["_id"]) == "TFXUSDT"
    finally:
        await _cleanup(coin_repo, market_repo)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_upsert_binance_prices_only_touches_live_fields(connected_db):
    """
    A Binance price refresh must update price/24h fields but must
    NEVER clear market_cap_usd or other CoinGecko-only fields that a
    prior full sync already set (Binance's ticker doesn't carry them).
    """
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin")
        await coin_repo.bulk_upsert_from_coingecko([coin])
        doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)

        # Seed a full CoinGecko-sourced record first.
        cg_market = NormalizedMarketData(
            coingecko_id=TEST_COINGECKO_ID, price_usd=1.00, market_cap_usd=123456.0,
            circulating_supply=1_000_000.0, last_updated=datetime.now(timezone.utc),
        )
        await market_repo.bulk_upsert([(doc["_id"], cg_market)], data_source="coingecko")

        ticker = NormalizedExchangeTicker(
            symbol="TFXUSDT", base_asset="TFX", quote_asset="USDT",
            last_price=1.05, price_change_percent_24h=5.0,
            high_24h=1.10, low_24h=0.95, quote_volume_24h=50_000.0,
        )
        result = await market_repo.bulk_upsert_binance_prices([(doc["_id"], ticker)], data_source="binance")
        assert result["matched"] == 1

        fetched = await market_repo.get_by_coin_id(doc["_id"])
        # Live fields updated from Binance:
        assert fetched["price_usd"] == 1.05
        assert fetched["percent_change_24h"] == 5.0
        assert fetched["high_24h_usd"] == 1.10
        assert fetched["low_24h_usd"] == 0.95
        assert fetched["data_source"] == "binance"
        # CoinGecko-only fields untouched:
        assert fetched["market_cap_usd"] == 123456.0
        assert fetched["circulating_supply"] == 1_000_000.0
    finally:
        await _cleanup(coin_repo, market_repo)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_upsert_binance_prices_never_writes_none_over_existing_value(connected_db):
    """A ticker missing a field must never blank out a previously-good value."""
    coin_repo = CoinRepository()
    market_repo = MarketDataRepository()
    await _cleanup(coin_repo, market_repo)

    try:
        coin = NormalizedCoin(coingecko_id=TEST_COINGECKO_ID, symbol="TFX", name="Test Fixture Coin")
        await coin_repo.bulk_upsert_from_coingecko([coin])
        doc = await coin_repo.find_by_coingecko_id(TEST_COINGECKO_ID)

        cg_market = NormalizedMarketData(
            coingecko_id=TEST_COINGECKO_ID, price_usd=1.00, high_24h_usd=1.20,
            last_updated=datetime.now(timezone.utc),
        )
        await market_repo.bulk_upsert([(doc["_id"], cg_market)], data_source="coingecko")

        # Ticker with no high_24h value at all.
        sparse_ticker = NormalizedExchangeTicker(symbol="TFXUSDT", last_price=1.05)
        await market_repo.bulk_upsert_binance_prices([(doc["_id"], sparse_ticker)], data_source="binance")

        fetched = await market_repo.get_by_coin_id(doc["_id"])
        assert fetched["price_usd"] == 1.05
        # high_24h_usd must be untouched, not overwritten with null.
        assert fetched["high_24h_usd"] == 1.20
    finally:
        await _cleanup(coin_repo, market_repo)
