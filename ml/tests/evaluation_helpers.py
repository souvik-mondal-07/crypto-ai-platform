"""Test-only helpers for the Phase 17 evaluation tests (explicit, deterministic candles — never used by production code)."""

from datetime import datetime, timedelta, timezone

from ml.evaluation.matching import PredictionRecord
from ml.evaluation.series import Candle, PriceSeries

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
H = 3600


def candles_from_closes(closes, interval_s=H, start=T0, opens=None):
    out = []
    for i, c in enumerate(closes):
        o = opens[i] if opens else (closes[i - 1] if i else c)
        out.append(Candle(start + timedelta(seconds=i * interval_s), o, max(o, c) * 1.001, min(o, c) * 0.999, c, 10.0, interval_s))
    return out


def series_from_closes(closes, interval_s=H, start=T0, as_of=None, opens=None):
    return PriceSeries(candles_from_closes(closes, interval_s, start, opens), interval_s, as_of=as_of)


def make_prediction(**kw):
    base = dict(
        source_id="p1", coin_id="c1", symbol="BTC", horizon="24h",
        reference_time=T0 + timedelta(hours=1), target_time=T0 + timedelta(hours=25), reference_price=100.0,
        predicted_return=0.02, direction="up", model="xgboost", model_version="1", feature_version="f1",
        generated_at=T0 + timedelta(hours=1),
    )
    base.update(kw)
    return PredictionRecord(**base)
