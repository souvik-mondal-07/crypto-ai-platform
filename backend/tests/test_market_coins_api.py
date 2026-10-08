"""
Tests for GET /api/v1/market/coins (Phase 8) — the joined, sortable,
filterable Markets-table endpoint. Service layer mocked; no MongoDB.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.schemas.market import MarketCoin, MarketCoinListResponse
from app.services.market_service import MARKET_SORT_FIELDS, MarketService


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _response(items=None) -> MarketCoinListResponse:
    return MarketCoinListResponse(
        items=items if items is not None else [],
        page=1, limit=25, total=0, pages=0,
        sort_by="market_cap", sort_direction="desc", data_source="coingecko",
    )


def _market_coin() -> MarketCoin:
    return MarketCoin(
        coin_id="507f1f77bcf86cd799439011",
        name="Real Backend Coin", symbol="RBC", logo_url=None, market_cap_rank=1,
        price_usd=100.0, percent_change_24h=2.5, high_24h_usd=110.0, low_24h_usd=95.0,
        market_cap_usd=1_000_000.0, volume_24h_usd=50_000.0, circulating_supply=10_000.0,
        last_updated=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_market_coins_returns_joined_rows(client):
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.list_market_coins = AsyncMock(
            return_value=_response([_market_coin()])
        )
        response = client.get("/api/v1/market/coins?page=1&limit=25")

    assert response.status_code == 200
    body = response.json()
    row = body["items"][0]
    # Coin identity AND market fields arrive together in one request.
    assert row["name"] == "Real Backend Coin"
    assert row["price_usd"] == 100.0
    assert row["high_24h_usd"] == 110.0
    assert row["circulating_supply"] == 10_000.0


def test_market_coins_rejects_oversized_limit(client):
    assert client.get("/api/v1/market/coins?limit=99999").status_code == 422


def test_market_coins_rejects_invalid_sort_direction(client):
    assert client.get("/api/v1/market/coins?sort_direction=sideways").status_code == 422


def test_market_coins_invalid_sort_field_returns_clean_error(client):
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.list_market_coins = AsyncMock(
            side_effect=AppError(400, "INVALID_SORT_FIELD", "bad sort field")
        )
        response = client.get("/api/v1/market/coins?sort_by=%24where")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SORT_FIELD"


@pytest.mark.asyncio
async def test_list_market_coins_rejects_unknown_sort_field():
    """A client string must never reach the aggregation pipeline."""
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=AsyncMock(),
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )
    with pytest.raises(AppError) as exc_info:
        await service.list_market_coins(page=1, limit=10, sort_by="$where")
    assert exc_info.value.code == "INVALID_SORT_FIELD"


@pytest.mark.asyncio
async def test_list_market_coins_rejects_unknown_filter():
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=AsyncMock(),
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )
    with pytest.raises(AppError) as exc_info:
        await service.list_market_coins(page=1, limit=10, market_filter="everything")
    assert exc_info.value.code == "INVALID_FILTER"


@pytest.mark.asyncio
async def test_list_market_coins_maps_sort_key_to_real_field():
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([], 0))
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )

    await service.list_market_coins(page=1, limit=10, sort_by="change_24h")

    kwargs = repo.list_coins_with_market_data.await_args.kwargs
    assert kwargs["sort_field"] == MARKET_SORT_FIELDS["change_24h"] == "percent_change_24h"


@pytest.mark.asyncio
async def test_gainers_filter_becomes_a_lower_bound_on_24h_change():
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([], 0))
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )

    await service.list_market_coins(page=1, limit=10, market_filter="gainers")

    kwargs = repo.list_coins_with_market_data.await_args.kwargs
    assert kwargs["min_change_24h"] == 0.0
    assert kwargs["max_change_24h"] is None


@pytest.mark.asyncio
async def test_losers_filter_becomes_an_upper_bound_on_24h_change():
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([], 0))
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )

    await service.list_market_coins(page=1, limit=10, market_filter="losers")

    kwargs = repo.list_coins_with_market_data.await_args.kwargs
    assert kwargs["max_change_24h"] == 0.0
    assert kwargs["min_change_24h"] is None


@pytest.mark.asyncio
async def test_pagination_skip_is_derived_from_page_and_limit():
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([], 0))
    service = MarketService(
        coin_repository=AsyncMock(), market_data_repository=repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )

    await service.list_market_coins(page=3, limit=25)

    assert repo.list_coins_with_market_data.await_args.kwargs["skip"] == 50


# ---------------------------------------------------------------------------
# Redesigned Markets explorer: extra filters, sorts and freshness metadata
# ---------------------------------------------------------------------------

from bson import ObjectId  # noqa: E402


def _service_with_repo(repo):
    return MarketService(
        coin_repository=AsyncMock(), market_data_repository=repo,
        coingecko_provider=AsyncMock(), binance_provider=AsyncMock(),
    )


def _empty_repo():
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([], 0))
    return repo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort_key, field",
    [
        ("fdv", "fully_diluted_valuation_usd"),
        ("supply", "circulating_supply"),
        ("change_7d", "percent_change_7d"),
        ("volatility", "volatility_24h_pct"),
    ],
)
async def test_new_sort_keys_map_to_whitelisted_fields(sort_key, field):
    repo = _empty_repo()
    await _service_with_repo(repo).list_market_coins(page=1, limit=10, sort_by=sort_key)
    assert repo.list_coins_with_market_data.await_args.kwargs["sort_field"] == field


@pytest.mark.asyncio
async def test_range_filters_are_forwarded_to_the_repository():
    repo = _empty_repo()
    await _service_with_repo(repo).list_market_coins(
        page=1, limit=10,
        market_cap_min=1e9, market_cap_max=1e10,
        volume_min=1e6, volume_max=1e8,
        has_max_supply=True,
    )
    kwargs = repo.list_coins_with_market_data.await_args.kwargs
    assert (kwargs["min_market_cap"], kwargs["max_market_cap"]) == (1e9, 1e10)
    assert (kwargs["min_volume"], kwargs["max_volume"]) == (1e6, 1e8)
    assert kwargs["has_max_supply"] is True


@pytest.mark.asyncio
async def test_explicit_change_range_combines_with_gainers_filter_using_tighter_bound():
    repo = _empty_repo()
    await _service_with_repo(repo).list_market_coins(
        page=1, limit=10, market_filter="gainers", change_min=5.0, change_max=10.0,
    )
    kwargs = repo.list_coins_with_market_data.await_args.kwargs
    assert kwargs["min_change_24h"] == 5.0   # tighter than gainers' implicit 0.0
    assert kwargs["max_change_24h"] == 10.0


@pytest.mark.asyncio
async def test_inverted_range_is_rejected():
    service = _service_with_repo(_empty_repo())
    with pytest.raises(AppError) as exc_info:
        await service.list_market_coins(page=1, limit=10, market_cap_min=10, market_cap_max=1)
    assert exc_info.value.code == "INVALID_RANGE"


@pytest.mark.asyncio
async def test_coin_ids_are_validated_and_converted_to_object_ids():
    repo = _empty_repo()
    valid = str(ObjectId())
    await _service_with_repo(repo).list_market_coins(page=1, limit=10, coin_ids=[valid])
    assert repo.list_coins_with_market_data.await_args.kwargs["coin_ids"] == [ObjectId(valid)]


@pytest.mark.asyncio
async def test_invalid_coin_id_never_reaches_the_repository():
    repo = _empty_repo()
    with pytest.raises(AppError) as exc_info:
        await _service_with_repo(repo).list_market_coins(page=1, limit=10, coin_ids=["not-an-id"])
    assert exc_info.value.code == "INVALID_COIN_ID"
    repo.list_coins_with_market_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_too_many_coin_ids_are_rejected():
    ids = [str(ObjectId()) for _ in range(101)]
    with pytest.raises(AppError) as exc_info:
        await _service_with_repo(_empty_repo()).list_market_coins(page=1, limit=10, coin_ids=ids)
    assert exc_info.value.code == "TOO_MANY_COIN_IDS"


@pytest.mark.asyncio
async def test_response_reports_real_freshness_and_universe_size():
    repo = _empty_repo()
    repo.count = AsyncMock(return_value=1234)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    repo.most_recent_update = AsyncMock(return_value=old)

    response = await _service_with_repo(repo).list_market_coins(page=1, limit=10)

    assert response.coins_with_market_data == 1234
    assert response.last_updated == old
    # Same 6h backend threshold as MarketData.is_stale — not loosened.
    assert response.is_stale is True


@pytest.mark.asyncio
async def test_rows_carry_extended_fields_and_derived_volatility():
    row = {
        "coin_id": ObjectId(),
        "coin": {"name": "Real Coin", "symbol": "RC", "logo_url": None, "market_cap_rank": 3},
        "price_usd": 100.0, "high_24h_usd": 110.0, "low_24h_usd": 90.0,
        "percent_change_7d": 4.2, "fully_diluted_valuation_usd": 5e9,
        "max_supply": 21_000_000.0, "ath_usd": 150.0, "atl_usd": 1.0,
        "updated_at": datetime.now(timezone.utc),
    }
    repo = AsyncMock()
    repo.list_coins_with_market_data = AsyncMock(return_value=([row], 1))
    repo.count = AsyncMock(return_value=1)
    repo.most_recent_update = AsyncMock(return_value=datetime.now(timezone.utc))

    response = await _service_with_repo(repo).list_market_coins(page=1, limit=10)

    item = response.items[0]
    assert item.percent_change_7d == 4.2
    assert item.fully_diluted_valuation_usd == 5e9
    assert item.ath_usd == 150.0
    assert item.volatility_24h_pct == pytest.approx(20.0)
    assert item.is_stale is False


def test_volatility_is_none_when_inputs_missing():
    from app.schemas.converters import volatility_24h_pct

    assert volatility_24h_pct(None, 1.0, 1.0) is None
    assert volatility_24h_pct(2.0, 1.0, 0) is None
    assert volatility_24h_pct(1.0, 2.0, 1.0) is None  # high < low is inconsistent data


def test_market_coins_route_parses_filters_and_coin_ids(client):
    first, second = str(ObjectId()), str(ObjectId())
    with patch("app.api.v1.market.MarketService") as mock_cls:
        mock_cls.return_value.list_market_coins = AsyncMock(return_value=_response())
        response = client.get(
            f"/api/v1/market/coins?market_cap_min=1000000000&volume_max=5000&change_min=-5"
            f"&has_max_supply=true&coin_ids={first},{second}"
        )

    assert response.status_code == 200
    kwargs = mock_cls.return_value.list_market_coins.await_args.kwargs
    assert kwargs["market_cap_min"] == 1_000_000_000
    assert kwargs["volume_max"] == 5000
    assert kwargs["change_min"] == -5
    assert kwargs["has_max_supply"] is True
    assert kwargs["coin_ids"] == [first, second]


def test_market_coins_route_rejects_negative_market_cap(client):
    assert client.get("/api/v1/market/coins?market_cap_min=-1").status_code == 422


# --- Repository pipeline shape (no MongoDB: collection is a stub) ----------

class _StubCursor:
    async def to_list(self, length=None):
        return []


class _StubCollection:
    def __init__(self):
        self.pipeline = None

    async def aggregate(self, pipeline):
        # PyMongo's async aggregate() is a coroutine returning a cursor —
        # this stub reproduces that so the `await ... .to_list()` pattern
        # (the earlier 'coroutine has no attribute to_list' bug) stays covered.
        self.pipeline = pipeline
        return _StubCursor()


def _repo_with_stub():
    from app.repositories.market_data_repository import MarketDataRepository

    stub_collection = _StubCollection()

    # BaseRepository.collection is a read-only property (it resolves the real
    # collection lazily through get_collection()), so it can't be assigned to.
    # Override it in a test-only subclass instead of adding a setter to
    # production code; no MongoDB connection is ever opened.
    class _StubMarketDataRepository(MarketDataRepository):
        @property
        def collection(self):
            return stub_collection

    return _StubMarketDataRepository.__new__(_StubMarketDataRepository)


@pytest.mark.asyncio
async def test_repository_awaits_aggregate_cursor_before_to_list():
    repo = _repo_with_stub()
    rows, total = await repo.list_coins_with_market_data(
        skip=0, limit=10, sort_field="market_cap_usd", sort_direction=-1,
    )
    assert (rows, total) == ([], 0)


@pytest.mark.asyncio
async def test_repository_builds_filter_match_stage():
    repo = _repo_with_stub()
    ids = [ObjectId()]
    await repo.list_coins_with_market_data(
        skip=0, limit=10, sort_field="market_cap_usd", sort_direction=-1,
        min_market_cap=1e9, max_volume=1e6, has_max_supply=True, coin_ids=ids,
    )
    match = repo.collection.pipeline[0]["$match"]
    assert match["market_cap_usd"] == {"$gte": 1e9}
    assert match["volume_24h_usd"] == {"$lte": 1e6}
    assert match["max_supply"] == {"$ne": None, "$gt": 0}
    assert match["coin_id"] == {"$in": ids}


@pytest.mark.asyncio
async def test_repository_computes_volatility_before_sorting_on_it():
    repo = _repo_with_stub()
    await repo.list_coins_with_market_data(
        skip=0, limit=10, sort_field="volatility_24h_pct", sort_direction=-1,
    )
    pipeline = repo.collection.pipeline
    stages = [next(iter(stage)) for stage in pipeline]
    assert stages.index("$addFields") < stages.index("$sort")
    # The first $match must NOT require the computed field to already exist.
    assert "volatility_24h_pct" not in pipeline[0]["$match"]
