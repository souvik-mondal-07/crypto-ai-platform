"""
Unit tests for TechnicalAnalysisService, using in-memory fakes for the
coin/market-data/technical-analysis repositories and the CoinGecko
provider — no MongoDB, no live network calls.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.providers.normalized import NormalizedCandle
from app.providers.timeframes import Timeframe
from app.services.technical_analysis_service import TechnicalAnalysisService


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


def _candles(n=60, seed=1):
    rnd = random.Random(seed)
    now = datetime.now(timezone.utc)
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] + rnd.uniform(-3, 3)))
    return [
        NormalizedCandle(
            timestamp=now - timedelta(hours=n - i),
            open=c,
            high=c + rnd.uniform(0, 2),
            low=c - rnd.uniform(0, 2),
            close=c,
            volume=None,
        )
        for i, c in enumerate(closes)
    ]


class FakeCoinRepository:
    def __init__(self, docs=None):
        self.docs = docs if docs is not None else [_coin_doc()]

    async def find_by_internal_id(self, internal_id):
        for d in self.docs:
            if str(d["_id"]) == internal_id:
                return d
        return None


class FakeMarketDataRepository:
    def __init__(self, doc=None):
        self.doc = doc

    async def get_by_coin_id(self, coin_id):
        return self.doc


class FakeTechnicalAnalysisRepository:
    def __init__(self):
        self.stored = {}
        self.upsert_calls = 0

    async def get_latest(self, coin_id, timeframe):
        return self.stored.get((coin_id, timeframe))

    async def upsert(self, coin_id, timeframe, payload):
        self.upsert_calls += 1
        self.stored[(coin_id, timeframe)] = {**payload, "coin_id": coin_id, "timeframe": timeframe}

    @staticmethod
    def is_stale(doc, max_age_seconds):
        from app.repositories.technical_analysis_repository import TechnicalAnalysisRepository

        return TechnicalAnalysisRepository.is_stale(doc, max_age_seconds)


class FakeCoinGeckoProvider:
    supports_historical_ohlc = True

    def __init__(self, candles=None, raise_error=None):
        self._candles = candles if candles is not None else _candles()
        self._raise_error = raise_error
        self.calls = 0

    async def get_historical_ohlc(self, provider_coin_id, timeframe):
        self.calls += 1
        if self._raise_error:
            raise self._raise_error
        return self._candles


def _service(coin_docs=None, candles=None, market_doc=None, provider=None):
    return TechnicalAnalysisService(
        coin_repository=FakeCoinRepository(coin_docs),
        market_data_repository=FakeMarketDataRepository(market_doc),
        technical_analysis_repository=FakeTechnicalAnalysisRepository(),
        coingecko_provider=provider or FakeCoinGeckoProvider(candles),
    )


@pytest.mark.asyncio
async def test_rejects_invalid_coin_id():
    service = _service()
    with pytest.raises(AppError) as exc_info:
        await service.get_technical_analysis("not-an-objectid", Timeframe.DAY_30)
    assert exc_info.value.code == "INVALID_COIN_ID"


@pytest.mark.asyncio
async def test_returns_404_for_missing_coin():
    service = _service(coin_docs=[])
    with pytest.raises(AppError) as exc_info:
        await service.get_technical_analysis(str(ObjectId()), Timeframe.DAY_30)
    assert exc_info.value.code == "COIN_NOT_FOUND"


@pytest.mark.asyncio
async def test_returns_422_when_too_few_candles():
    coin = _coin_doc()
    service = _service(coin_docs=[coin], candles=_candles(n=5))
    with pytest.raises(AppError) as exc_info:
        await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    assert exc_info.value.code == "INSUFFICIENT_HISTORICAL_DATA"


@pytest.mark.asyncio
async def test_returns_404_when_coin_has_no_provider_mapping():
    # Realistic "not mapped" shape (mirrors what CoinRepository/sync
    # actually stores for a coin missing this provider) — an explicit
    # `providers.coingecko: null` is a distinct pre-existing edge case
    # shared with get_coin_history's identical resolution line, out of
    # scope for Phase 10.
    coin = _coin_doc(providers={"coingecko": {"id": None, "available": False}})
    service = _service(coin_docs=[coin])
    with pytest.raises(AppError) as exc_info:
        await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    assert exc_info.value.code == "TECHNICAL_ANALYSIS_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_computes_full_indicator_set_from_real_candles():
    coin = _coin_doc()
    market_doc = {"coin_id": coin["_id"], "volume_24h_usd": 42_000_000.0}
    service = _service(coin_docs=[coin], candles=_candles(n=80), market_doc=market_doc)

    result = await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)

    assert result.coin_id == str(coin["_id"])
    assert result.symbol == "BTC"
    assert result.candle_count == 80
    assert result.rsi.current is not None and 0 <= result.rsi.current <= 100
    assert result.moving_averages.sma["20"] is not None
    assert result.bollinger_bands.upper > result.bollinger_bands.lower
    assert result.atr.current is not None and result.atr.current > 0
    assert result.volume.current_volume_24h_usd == 42_000_000.0
    assert result.trend.trend in {"bullish", "bearish", "neutral"}
    # Never a trading decision anywhere on this response.
    assert not hasattr(result, "decision")
    assert not hasattr(result, "recommendation")


@pytest.mark.asyncio
async def test_volume_is_none_and_unavailable_when_not_synced():
    coin = _coin_doc()
    service = _service(coin_docs=[coin], candles=_candles(n=80), market_doc=None)

    result = await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)

    assert result.volume.current_volume_24h_usd is None
    assert result.volume.trend == "unavailable"


@pytest.mark.asyncio
async def test_caches_result_and_skips_recomputation_on_second_call():
    coin = _coin_doc()
    provider = FakeCoinGeckoProvider(_candles(n=80))
    service = _service(coin_docs=[coin], provider=provider)

    first = await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    assert provider.calls == 1

    second = await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    # Cache hit: no second provider call, same computed values returned.
    assert provider.calls == 1
    assert second.rsi.current == first.rsi.current


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache():
    coin = _coin_doc()
    provider = FakeCoinGeckoProvider(_candles(n=80))
    service = _service(coin_docs=[coin], provider=provider)

    await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    assert provider.calls == 1

    await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30, force_refresh=True)
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_response_never_contains_a_buy_sell_decision():
    coin = _coin_doc()
    service = _service(coin_docs=[coin], candles=_candles(n=80))
    result = await service.get_technical_analysis(str(coin["_id"]), Timeframe.DAY_30)
    dumped = result.model_dump()
    forbidden = {"buy", "sell", "hold", "decision", "recommendation", "action"}
    assert forbidden.isdisjoint(dumped.keys())
