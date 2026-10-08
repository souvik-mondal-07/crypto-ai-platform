"""PredictionService tests — fake repositories + fake exchange, REAL `ml` code and a model
trained on test-suite-only synthetic candles (never used in production code paths)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.prediction_repository import PredictionRepository
from app.services import prediction_service as ps
from app.services.prediction_service import PredictionService, validate_horizon

ml_registry = pytest.importorskip("ml.models.model_registry")
from ml.config.model_config import MLConfig  # noqa: E402
from ml.pipelines.training_pipeline import train_coin_horizon  # noqa: E402
def make_candles(n, seed=7, ar=0.35, start=None):
    """Generate deterministic test-only OHLCV candles."""
    import numpy as np
    if start is None:
        start = pd.Timestamp("2025-01-01", tz="UTC")
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start=start, periods=n, freq="h", tz="UTC")
    returns = rng.normal(0.0002, 0.01, size=n)
    for i in range(1, n):
        returns[i] = ar * returns[i - 1] + (1 - ar) * returns[i]
    close = 100 * np.exp(np.cumsum(returns))
    open_ = np.concatenate(([close[0]], close[:-1]))
    spread = np.abs(rng.normal(0.005, 0.002, size=n))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(mean=10, sigma=0.25, size=n)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class FakeCoins:
    def __init__(self, docs): self.docs = docs
    async def find_by_internal_id(self, coin_id): return self.docs.get(coin_id)


class FakePredictions:
    def __init__(self): self.docs = []
    async def insert(self, doc): self.docs.append(doc)
    async def get_latest(self, coin_oid, horizon, *, model=None):
        rows = [d for d in self.docs if d["coin_id"] == coin_oid and d["horizon"] == horizon and (not model or d["model"] == model)]
        return max(rows, key=lambda d: d["generated_at"], default=None)
    async def get_latest_any_horizon(self, coin_oid):
        rows = [d for d in self.docs if d["coin_id"] == coin_oid]
        return max(rows, key=lambda d: d["generated_at"], default=None)


class FakeNews:
    async def sentiment_points_for_coin(self, coin_oid, since, until): return []


class FakeBinance:
    def __init__(self, candles): self.candles, self.calls = candles, 0
    async def get_klines(self, symbol, interval, limit):
        self.calls += 1
        df = self.candles.tail(limit)
        return [[int(t.timestamp() * 1000), o, h, l, c, v] for t, o, h, l, c, v in
                zip(df["timestamp"], df["open"], df["high"], df["low"], df["close"], df["volume"])]


def _recent_candles(n=3500, ar=0.35, seed=7):
    # ends with the last CLOSED hourly candle, so the real clock treats it as fresh
    start = pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=n)
    return make_candles(n, seed=seed, ar=ar, start=start)


@pytest.fixture
def env(tmp_path):
    coin_oid = ObjectId()
    coin_id = str(coin_oid)
    candles = _recent_candles()
    cfg = MLConfig(artifact_dir=tmp_path, default_model="ridge")
    out = train_coin_horizon(candles, coin_id=coin_id, horizon_name="1h", model_types=["ridge"], config=cfg,
                             registry=ml_registry.ModelRegistry(tmp_path), symbol="AAA")
    assert out.models[0]["status"] == "active"
    settings = SimpleNamespace(ML_ARTIFACT_DIR=str(tmp_path), ML_DEFAULT_HORIZON="24h", ML_DEFAULT_MODEL="ridge",
                               ML_MIN_HISTORY_LENGTH=500, ML_PREDICTION_TTL_SECONDS=900)
    coins = FakeCoins({coin_id: {"_id": coin_oid, "symbol": "AAA", "providers": {"binance": {"symbol": "AAAUSDT"}}}})
    nobinance = ObjectId()
    coins.docs[str(nobinance)] = {"_id": nobinance, "symbol": "NOB", "providers": {}}
    preds, binance = FakePredictions(), FakeBinance(candles)
    service = PredictionService(coins, preds, FakeNews(), binance)
    with patch.object(ps, "get_settings", return_value=settings):
        yield SimpleNamespace(service=service, coin_id=coin_id, preds=preds, binance=binance, nobinance=str(nobinance), coin_oid=coin_oid)


# --------------------------------------------------------------------- validation


def test_horizon_validation():
    assert validate_horizon("24H") == "24h"
    for bad in ("2h", "", "1d", "24 h"):
        with pytest.raises(AppError) as e:
            validate_horizon(bad)
        assert e.value.status_code == 400 and e.value.code == "INVALID_HORIZON"


async def test_invalid_coin_id_and_unknown_coin(env):
    with pytest.raises(AppError) as e:
        await env.service.get_prediction("not-an-object-id", "24h")
    assert (e.value.status_code, e.value.code) == (400, "INVALID_COIN_ID")
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(str(ObjectId()), "24h")
    assert (e.value.status_code, e.value.code) == (404, "COIN_NOT_FOUND")
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(env.coin_id, "3h")
    assert e.value.code == "INVALID_HORIZON"


# --------------------------------------------------------------------- generation + storage


async def test_generates_stores_and_then_serves_fresh_stored_prediction(env):
    first = await env.service.get_prediction(env.coin_id, "1h")
    assert first.kind == "model_prediction" and first.model == "ridge" and first.horizon == "1h"
    assert first.predicted_price_range.lower < first.predicted_price_range.upper
    assert len(env.preds.docs) == 1 and env.binance.calls == 1
    doc = env.preds.docs[0]
    for field in ("coin_id", "symbol", "horizon", "current_price", "prediction", "range", "direction", "confidence",
                  "model", "model_version", "feature_version", "generated_at", "expires_at", "status"):
        assert field in doc
    assert doc["status"] == "active" and doc["expires_at"] > doc["generated_at"]

    second = await env.service.get_prediction(env.coin_id, "1h")   # within TTL -> no new exchange call / insert
    assert env.binance.calls == 1 and len(env.preds.docs) == 1
    assert second.predicted_return == first.predicted_return and second.is_stale is False


async def test_expired_prediction_is_regenerated(env):
    await env.service.get_prediction(env.coin_id, "1h")
    env.preds.docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    await env.service.get_prediction(env.coin_id, "1h")
    assert len(env.preds.docs) == 2 and env.binance.calls == 2


async def test_confidence_is_null_or_a_probability_never_random(env):
    r = await env.service.get_prediction(env.coin_id, "1h")
    assert (r.confidence is None) == (r.confidence_status == "unavailable")
    if r.confidence is not None:
        assert 0.0 <= r.confidence <= 1.0


# --------------------------------------------------------------------- honest unavailable states


async def test_horizon_without_a_trained_model_is_404_model_unavailable_and_no_exchange_call(env):
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(env.coin_id, "30d")
    assert (e.value.status_code, e.value.code) == (404, "PREDICTION_MODEL_UNAVAILABLE")
    assert env.binance.calls == 0 and env.preds.docs == []


async def test_coin_without_exchange_pair_is_insufficient_data(env, tmp_path):
    # even with a model registered under that coin id, no real candles can exist for it
    import shutil
    shutil.copytree(tmp_path / env.coin_id, tmp_path / env.nobinance)
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(env.nobinance, "1h")
    assert (e.value.status_code, e.value.code) == (422, "INSUFFICIENT_HISTORICAL_DATA")
    assert env.preds.docs == []


async def test_too_little_exchange_history_is_insufficient_data_not_a_guess(env):
    env.binance.candles = env.binance.candles.tail(120)
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(env.coin_id, "1h")
    assert e.value.code == "INSUFFICIENT_HISTORICAL_DATA" and env.preds.docs == []


async def test_explicit_model_type_that_does_not_exist_is_unavailable(env):
    with pytest.raises(AppError) as e:
        await env.service.get_prediction(env.coin_id, "1h", model="lightgbm")
    assert e.value.code == "PREDICTION_MODEL_UNAVAILABLE"


# --------------------------------------------------------------------- list + latest


async def test_list_contains_only_horizons_with_valid_predictions(env):
    listing = await env.service.list_predictions(env.coin_id)
    assert [p.horizon for p in listing.predictions] == ["1h"]
    assert {u.horizon for u in listing.unavailable} == {"4h", "24h", "7d", "30d"}
    assert all(u.status == "model_unavailable" and u.reason for u in listing.unavailable)


async def test_latest_never_generates_and_flags_stale(env):
    with pytest.raises(AppError) as e:
        await env.service.get_latest(env.coin_id, "1h")
    assert (e.value.status_code, e.value.code) == (404, "PREDICTION_NOT_FOUND")
    assert env.binance.calls == 0

    await env.service.get_prediction(env.coin_id, "1h")
    fresh = await env.service.get_latest(env.coin_id, "1h")
    assert fresh.is_stale is False
    env.preds.docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    stale = await env.service.get_latest(env.coin_id)
    assert stale.is_stale is True and len(env.preds.docs) == 1


def test_repository_expiry_check():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert PredictionRepository.is_expired({"expires_at": now - timedelta(seconds=1)}, now)
    assert not PredictionRepository.is_expired({"expires_at": now + timedelta(seconds=1)}, now)
    assert PredictionRepository.is_expired({}, now)
    assert not PredictionRepository.is_expired({"expires_at": datetime(2026, 1, 1, 0, 5)}, datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
