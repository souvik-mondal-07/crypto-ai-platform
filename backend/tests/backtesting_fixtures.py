"""Shared fixtures for the Phase 17 tests.

Everything here is TEST-ONLY synthetic input with an exactly known answer (candles, predictions, decisions).
Application code never imports this module, and no test result is ever presented as real platform accuracy.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.database.collections import CollectionName as C
from app.providers.errors import ProviderError
from app.services import evaluation_service
from app.services.market_history import MarketHistory, clear_cache
from tests.fake_mongo import FakeCollection
from tests.user_features_fixtures import NOW, PASSWORD, client, user_a, user_b  # noqa: F401

SYMBOL = "BTCUSDT"
#: 20 days ago, on the hour: every test timeline is in the past, relative to the real clock.
BASE = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=20)


@pytest.fixture(autouse=True)
def _reset_phase17_state():
    evaluation_service.reset_state_for_tests()
    clear_cache()
    yield
    evaluation_service.reset_state_for_tests()
    clear_cache()


@pytest.fixture
def db(monkeypatch):
    collections = {
        C.USERS: FakeCollection(), C.COINS: FakeCollection(), C.MARKET_DATA: FakeCollection(),
        C.WATCHLISTS: FakeCollection(unique=[("user_id", "coin_id")]), C.PORTFOLIOS: FakeCollection(unique=[("user_id", "coin_id")]),
        C.PORTFOLIO_TRANSACTIONS: FakeCollection(), C.ANALYSIS_HISTORY: FakeCollection(), C.ALERTS: FakeCollection(),
        C.DECISIONS: FakeCollection(), C.PREDICTIONS: FakeCollection(), C.AI_ANALYSIS: FakeCollection(),
        C.PREDICTION_RESULTS: FakeCollection(unique=[("record_type", "source_id", "horizon")]),
        C.BACKTEST_RUNS: FakeCollection(unique=[("run_id",)]),
    }
    monkeypatch.setattr("app.repositories.base.get_collection", lambda name: collections[name])
    return collections


@pytest.fixture
def coins(db):
    """BTC (mapped to Binance) and ETH (no Binance mapping)."""
    btc, eth = ObjectId(), ObjectId()
    db[C.COINS].docs.append({"_id": btc, "name": "Bitcoin", "symbol": "BTC", "is_active": True, "providers": {"binance": {"symbol": SYMBOL}}})
    db[C.COINS].docs.append({"_id": eth, "name": "Ethereum", "symbol": "ETH", "is_active": True})
    return {"btc": str(btc), "eth": str(eth), "btc_oid": btc, "eth_oid": eth}


def kline_rows(closes, start=BASE, interval_s=3600):
    """Binance-style rows; candle i opens at start + i*interval and closes at start + (i+1)*interval."""
    rows = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        rows.append([int((start + timedelta(seconds=i * interval_s)).timestamp() * 1000), o, max(o, c) * 1.001, min(o, c) * 0.999, c, 10.0])
    return rows


def rising_closes(n=24 * 19):
    return [100.0 + 0.1 * i for i in range(n)]


class FakeHistory(MarketHistory):
    """Serves explicit rows instead of calling the exchange; can simulate an outage."""

    def __init__(self, rows_by_key, fail=False):
        self.rows_by_key, self.fail, self.calls = rows_by_key, fail, 0

    async def rows(self, symbol, interval, start, end, max_candles=10_000):
        self.calls += 1
        if self.fail:
            raise ProviderError("exchange unavailable")
        lo, hi = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
        return [r for r in self.rows_by_key.get((symbol, interval), []) if lo <= r[0] <= hi]


def prediction_doc(coin_oid, k, *, horizon="24h", direction="up", predicted_return=0.01, reference_price=None,
                   model="xgboost", model_version="1", generated_at=None, closes=None):
    """A Phase 13 `predictions` document whose reference point is the CLOSE of candle k."""
    closes = closes or rising_closes()
    ref_time = BASE + timedelta(hours=k + 1)
    seconds = {"1h": 3600, "4h": 14400, "24h": 86400, "7d": 604800, "30d": 2592000}[horizon]
    return {
        "_id": ObjectId(), "coin_id": coin_oid, "symbol": "BTC", "horizon": horizon,
        "current_price": reference_price if reference_price is not None else closes[k],
        "prediction": {"predicted_return": predicted_return, "kind": "return"},
        "range": {"return_lower": -0.05, "return_upper": 0.05, "price_lower": None, "price_upper": None, "nominal_coverage": 0.8},
        "direction": direction, "confidence": None, "model": model, "model_version": model_version, "feature_version": "f1",
        "reference_time": ref_time, "target_time": ref_time + timedelta(seconds=seconds),
        "generated_at": generated_at or ref_time, "expires_at": ref_time + timedelta(hours=1), "created_at": ref_time, "status": "active",
    }


def decision_doc(coin_oid, k, decision, *, status="valid"):
    """A Phase 14 `decisions` document generated exactly at the close of candle k."""
    at = BASE + timedelta(hours=k + 1)
    return {"_id": ObjectId(), "coin_id": coin_oid, "symbol": "BTC", "decision": decision, "status": status, "confidence": 60.0,
            "generated_at": at, "created_at": at, "engine_version": "1.0"}


def history_for(closes=None):
    return FakeHistory({(SYMBOL, "1h"): kline_rows(closes or rising_closes())})
