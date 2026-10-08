"""
Unit tests for CoinService using an in-memory fake repository — no
MongoDB required. Exercises validation (sort field whitelist, provider
whitelist, query length) and response-shape logic.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.services.coin_service import CoinService


def _coin_doc(**overrides):
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "name": "Bitcoin",
        "symbol": "BTC",
        "slug": "bitcoin",
        "logo_url": None,
        "market_cap_rank": 1,
        "is_active": True,
        "providers": {"coingecko": {"id": "bitcoin", "available": True}},
        "created_at": now,
        "updated_at": now,
    }
    doc.update(overrides)
    return doc


class FakeCoinRepository:
    def __init__(self, docs=None):
        self.docs = docs or [_coin_doc()]

    async def list_coins(self, page, limit, *, is_active=None, provider=None, sort_by="market_cap_rank", sort_direction=1):
        return self.docs, len(self.docs)

    async def search(self, query, limit=20):
        return [d for d in self.docs if query.lower() in d["name"].lower()][:limit]

    async def find_by_internal_id(self, internal_id):
        for d in self.docs:
            if str(d["_id"]) == internal_id:
                return d
        return None


class FakeMarketDataRepository:
    """In-memory stand-in for MarketDataRepository, keyed by coin_id (ObjectId)."""

    def __init__(self, docs_by_coin_id=None):
        self.docs_by_coin_id = docs_by_coin_id or {}

    async def get_many_by_coin_ids(self, coin_ids):
        return {cid: self.docs_by_coin_id[cid] for cid in coin_ids if cid in self.docs_by_coin_id}


@pytest.mark.asyncio
async def test_list_coins_rejects_unknown_sort_field():
    service = CoinService(coin_repository=FakeCoinRepository())
    with pytest.raises(AppError) as exc_info:
        await service.list_coins(1, 10, sort_by="$where")
    assert exc_info.value.code == "INVALID_SORT_FIELD"


@pytest.mark.asyncio
async def test_list_coins_rejects_unknown_provider():
    service = CoinService(coin_repository=FakeCoinRepository())
    with pytest.raises(AppError) as exc_info:
        await service.list_coins(1, 10, provider="coinmarketcap")
    assert exc_info.value.code == "INVALID_PROVIDER"


@pytest.mark.asyncio
async def test_list_coins_returns_paginated_shape():
    docs = [_coin_doc(name=f"Coin {i}") for i in range(5)]
    service = CoinService(coin_repository=FakeCoinRepository(docs))
    result = await service.list_coins(1, 100)
    assert result.total == 5
    assert result.page == 1
    assert len(result.items) == 5
    assert result.pages == 1


@pytest.mark.asyncio
async def test_search_rejects_empty_query():
    service = CoinService(coin_repository=FakeCoinRepository())
    with pytest.raises(AppError) as exc_info:
        await service.search_coins("   ")
    assert exc_info.value.code == "INVALID_QUERY"


@pytest.mark.asyncio
async def test_search_rejects_overly_long_query():
    service = CoinService(coin_repository=FakeCoinRepository())
    with pytest.raises(AppError) as exc_info:
        await service.search_coins("x" * 200)
    assert exc_info.value.code == "INVALID_QUERY"


@pytest.mark.asyncio
async def test_search_case_insensitive_via_repository():
    docs = [_coin_doc(name="Bitcoin"), _coin_doc(name="Ethereum")]
    service = CoinService(
        coin_repository=FakeCoinRepository(docs),
        market_data_repository=FakeMarketDataRepository(),
    )
    result = await service.search_coins("BITCOIN")
    # The fake repository's search() lower-cases both sides, mirroring
    # the real repository's case-insensitive regex search.
    assert result.count == 1
    assert result.items[0].name == "Bitcoin"


@pytest.mark.asyncio
async def test_search_joins_market_data_when_available():
    """
    Root-cause regression test for the "search results show — instead
    of real values" bug: a coin with a synced market_data document
    must come back from search_coins() with its price/change/market
    fields populated, not null.
    """
    coin = _coin_doc(name="Bitcoin")
    market_doc = {
        "coin_id": coin["_id"],
        "price_usd": 65000.5,
        "percent_change_24h": 2.5,
        "percent_change_7d": -1.2,
        "market_cap_usd": 1_280_000_000_000.0,
        "volume_24h_usd": 32_000_000_000.0,
        "high_24h_usd": 65500.0,
        "low_24h_usd": 64000.0,
    }
    service = CoinService(
        coin_repository=FakeCoinRepository([coin]),
        market_data_repository=FakeMarketDataRepository({coin["_id"]: market_doc}),
    )

    result = await service.search_coins("bitcoin")

    assert result.count == 1
    item = result.items[0]
    assert item.price_usd == 65000.5
    assert item.percent_change_24h == 2.5
    assert item.percent_change_7d == -1.2
    assert item.market_cap_usd == 1_280_000_000_000.0
    assert item.volume_24h_usd == 32_000_000_000.0


@pytest.mark.asyncio
async def test_search_leaves_market_fields_null_when_not_synced():
    """A coin with no market_data document yet must show null (→ "—"
    in the UI), never a fabricated value."""
    coin = _coin_doc(name="Bitcoin")
    service = CoinService(
        coin_repository=FakeCoinRepository([coin]),
        market_data_repository=FakeMarketDataRepository(),
    )

    result = await service.search_coins("bitcoin")

    item = result.items[0]
    assert item.price_usd is None
    assert item.percent_change_24h is None
    assert item.market_cap_usd is None


@pytest.mark.asyncio
async def test_search_returns_empty_market_map_for_empty_results():
    """No search matches → no market_data lookup should be attempted or required."""
    service = CoinService(
        coin_repository=FakeCoinRepository([]),
        market_data_repository=FakeMarketDataRepository(),
    )
    result = await service.search_coins("doesnotexist")
    assert result.count == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_get_coin_rejects_invalid_id_format():
    service = CoinService(coin_repository=FakeCoinRepository())
    with pytest.raises(AppError) as exc_info:
        await service.get_coin("not-a-valid-objectid")
    assert exc_info.value.code == "INVALID_COIN_ID"


@pytest.mark.asyncio
async def test_get_coin_returns_404_when_missing():
    service = CoinService(coin_repository=FakeCoinRepository(docs=[]))
    with pytest.raises(AppError) as exc_info:
        await service.get_coin(str(ObjectId()))
    assert exc_info.value.code == "COIN_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_coin_returns_schema_on_success():
    doc = _coin_doc()
    service = CoinService(coin_repository=FakeCoinRepository(docs=[doc]))
    coin = await service.get_coin(str(doc["_id"]))
    assert coin.symbol == "BTC"
    assert coin.providers.coingecko.id == "bitcoin"
