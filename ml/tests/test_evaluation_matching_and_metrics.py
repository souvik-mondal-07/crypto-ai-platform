"""Phase 17 — prediction/outcome matching and accuracy metrics (pure Python, real-data contract)."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from ml.config.model_config import HORIZONS
from ml.evaluation import constants as K
from ml.evaluation.matching import Outcome, dedupe_predictions, match_prediction
from ml.evaluation.metrics import INSUFFICIENT_MESSAGE, accuracy_metrics, group_metrics
from ml.evaluation.series import Candle, PriceSeries
from ml.evaluation.timestamps import to_utc
from ml.tests.evaluation_helpers import H, T0, candles_from_closes, make_prediction, series_from_closes

NOW = T0 + timedelta(days=60)


def test_horizon_constants_match_prediction_engine():
    for name, spec in HORIZONS.items():
        assert K.HORIZON_SECONDS[name] == spec.horizon_seconds
        assert K.INTERVAL_SECONDS[K.HORIZON_INTERVAL[name]] == spec.interval_seconds


# ------------------------------------------------------------------ timestamps
def test_timestamp_normalisation():
    assert to_utc("2026-01-01T00:00:00Z") == T0
    assert to_utc("2026-01-01T05:30:00+05:30") == T0
    assert to_utc(datetime(2026, 1, 1)) == T0                      # naive == UTC (MongoDB)
    assert to_utc(T0.timestamp()) == T0 and to_utc(T0.timestamp() * 1000) == T0
    for bad in (None, "", "garbage", float("nan"), True, object()):
        assert to_utc(bad) is None


# ------------------------------------------------------------------ matching
def _closes_for_24h(actual):
    # candle i closes at T0 + (i+1)h. reference close at +1h (index 0). target = +25h (index 24).
    closes = [100.0] * 30
    closes[24] = actual
    return series_from_closes(closes)


def test_matched_return_uses_recorded_reference_price():
    out = match_prediction(make_prediction(reference_price=100.0), _closes_for_24h(105.0), NOW)
    assert out.status == "matched"
    assert out.actual_price == 105.0 and out.actual_return == pytest.approx(0.05)
    assert out.actual_direction == "up" and out.match_gap_seconds == 0


def test_not_matured_is_not_counted_and_has_no_return():
    out = match_prediction(make_prediction(), _closes_for_24h(105.0), T0 + timedelta(hours=24, minutes=59))
    assert out.status == "not_matured" and out.actual_return is None
    assert accuracy_metrics([out], min_samples=1)["sample_size"] == 0


def test_maturity_boundary_is_inclusive_when_candle_closed():
    assert match_prediction(make_prediction(), _closes_for_24h(105.0), T0 + timedelta(hours=25)).status == "matched"


def test_future_candles_beyond_now_are_ignored():
    # `now` is exactly the target; a candle closing after `now` must not be used.
    s = series_from_closes([100.0] * 40)
    out = match_prediction(make_prediction(), s, T0 + timedelta(hours=25))
    assert out.matched and out.matched_close_time == T0 + timedelta(hours=25)


def test_tolerance_accepts_half_interval_only():
    # Series on a grid shifted by 20 minutes: nearest close is 20 min away (< 30 min tolerance).
    shifted = series_from_closes([100.0] * 40, start=T0 + timedelta(minutes=20))
    assert match_prediction(make_prediction(), shifted, NOW).matched
    far = series_from_closes([100.0] * 40, start=T0 + timedelta(minutes=45))  # closest close is 15 min away on the other side
    assert match_prediction(make_prediction(), far, NOW).matched
    # A gap: remove the target candle and its neighbours.
    s = PriceSeries([c for c in candles_from_closes([100.0] * 40) if not (22 <= (c.open_time - T0).total_seconds() / H <= 26)], H)
    assert match_prediction(make_prediction(), s, NOW).status == "missing_future_price"


def test_missing_and_invalid_inputs():
    assert match_prediction(make_prediction(reference_price=None), _closes_for_24h(1.0), NOW).status == "missing_reference_price"
    assert match_prediction(make_prediction(reference_price=0.0), _closes_for_24h(1.0), NOW).status == "missing_reference_price"
    assert match_prediction(make_prediction(), None, NOW).status == "missing_future_price"
    assert match_prediction(make_prediction(), PriceSeries([], H), NOW).status == "missing_future_price"
    assert match_prediction(make_prediction(horizon="2h"), _closes_for_24h(1.0), NOW).status == "unsupported_horizon"
    assert match_prediction(make_prediction(reference_time=None), _closes_for_24h(1.0), NOW).status == "invalid_record"
    assert match_prediction(make_prediction(direction=None), _closes_for_24h(1.0), NOW).status == "invalid_record"
    assert match_prediction(make_prediction(target_time=T0 + timedelta(hours=40)), _closes_for_24h(1.0), NOW).status == "invalid_record"


def test_stale_market_data_when_series_ends_before_target():
    out = match_prediction(make_prediction(), series_from_closes([100.0] * 10), NOW)
    assert out.status == "stale_market_data"


def test_incomplete_and_duplicate_candles():
    candles = candles_from_closes([100.0] * 30)
    dup = Candle(candles[24].open_time, 1, 999.0, 1, 200.0, 5.0, H)  # re-fetched candle, last one wins
    s = PriceSeries(candles + [dup], H)
    assert s.report.dropped_duplicates == 1 and len(s) == 30
    assert s.nearest_close(T0 + timedelta(hours=25), 1).close == 200.0
    # Candle closing after as_of is incomplete.
    inc = PriceSeries(candles, H, as_of=T0 + timedelta(hours=10, minutes=30))
    assert inc.last_close_time == T0 + timedelta(hours=10) and inc.report.dropped_incomplete > 0


def test_invalid_candle_values_dropped_not_repaired():
    bad = [Candle(T0, 1, 2, 0.5, float("nan"), 1, H), Candle(T0 + timedelta(hours=1), 1, 0.5, 2, 1, 1, H),
           Candle(T0 + timedelta(hours=2), -1, 2, 0.5, 1, 1, H), Candle(T0 + timedelta(hours=3), 1, 2, 0.5, 1.5, -1, H)]
    assert len(PriceSeries(bad, H)) == 0


def test_timezone_aware_non_utc_reference_matches():
    ist = timezone(timedelta(hours=5, minutes=30))
    rec = make_prediction(reference_time=(T0 + timedelta(hours=1)).astimezone(ist), target_time=None)
    rec = type(rec)(**{**rec.__dict__, "reference_time": to_utc(rec.reference_time)})
    assert match_prediction(rec, _closes_for_24h(110.0), NOW).actual_return == pytest.approx(0.10)


def test_dedupe_keeps_latest_generated():
    a = make_prediction(source_id="a", generated_at=T0)
    b = make_prediction(source_id="b", generated_at=T0 + timedelta(minutes=5))
    c = make_prediction(source_id="c", model_version="2")
    kept, dropped = dedupe_predictions([a, b, c])
    assert dropped == 1 and {r.source_id for r in kept} == {"b", "c"}


# ------------------------------------------------------------------ metrics
def _matched(pred, actual, direction, **kw):
    rec = make_prediction(predicted_return=pred, direction=direction, reference_price=100.0, **kw)
    return Outcome(rec, "matched", None, rec.target_time, actual_price=100 * (1 + actual), actual_return=actual,
                   matched_close_time=rec.target_time, match_gap_seconds=0)


def test_accuracy_values_are_hand_checkable():
    outs = [_matched(0.02, 0.01, "up"), _matched(-0.01, -0.03, "down"), _matched(0.03, -0.01, "up"), _matched(0.0, 0.02, "flat")]
    m = accuracy_metrics(outs, min_samples=4)
    assert m["status"] == "ok" and m["sample_size"] == 4
    assert m["directional_sample_size"] == 3 and m["flat_predictions_excluded"] == 1
    assert m["directional_accuracy"] == pytest.approx(2 / 3)
    errs = [0.01, 0.02, 0.04, -0.02]
    assert m["mae"] == pytest.approx(sum(abs(e) for e in errs) / 4)
    assert m["rmse"] == pytest.approx(math.sqrt(sum(e * e for e in errs) / 4))
    assert m["mean_error"] == pytest.approx(sum(errs) / 4)
    assert m["baseline_zero_mae"] == pytest.approx((0.01 + 0.03 + 0.01 + 0.02) / 4)


def test_zero_actual_return_is_a_directional_miss():
    m = accuracy_metrics([_matched(0.01, 0.0, "up")], min_samples=1)
    assert m["directional_accuracy"] == 0.0


def test_insufficient_and_no_data_never_report_zero():
    few = accuracy_metrics([_matched(0.01, 0.01, "up")] * 5)
    assert few["status"] == "insufficient_data" and few["sample_size"] == 5
    assert few["message"] == INSUFFICIENT_MESSAGE
    assert few["mae"] is None and few["rmse"] is None and few["directional_accuracy"] is None
    none = accuracy_metrics([])
    assert none["status"] == "no_data" and none["mae"] is None


def test_unmatched_outcomes_are_ignored():
    rec = make_prediction()
    skipped = [Outcome(rec, s) for s in ("not_matured", "missing_future_price", "stale_market_data")]
    assert accuracy_metrics(skipped + [_matched(0.01, 0.01, "up")], min_samples=1)["sample_size"] == 1


def test_range_coverage_prefers_return_range_then_price_range():
    inside = _matched(0.0, 0.01, "flat", return_lower=-0.02, return_upper=0.02, nominal_coverage=0.8)
    outside = _matched(0.0, 0.05, "flat", return_lower=-0.02, return_upper=0.02, nominal_coverage=0.8)
    price_only = _matched(0.0, 0.01, "flat", price_lower=99.0, price_upper=102.0)
    no_range = _matched(0.0, 0.01, "flat")
    m = accuracy_metrics([inside, outside, price_only, no_range], min_samples=1)
    assert m["range_sample_size"] == 3 and m["range_coverage"] == pytest.approx(2 / 3)
    assert m["nominal_coverage"] == pytest.approx(0.8)
    assert accuracy_metrics([no_range], min_samples=1)["range_coverage"] is None
    bad = _matched(0.0, 0.01, "flat", return_lower=0.05, return_upper=-0.05)
    assert accuracy_metrics([bad], min_samples=1)["range_coverage"] is None


def test_group_metrics_by_horizon_and_model():
    outs = [_matched(0.01, 0.01, "up", horizon="24h"), _matched(0.01, -0.01, "up", horizon="7d", model_version="2")]
    rows = group_metrics(outs, lambda o: (o.record.horizon, o.record.model, o.record.model_version), min_samples=1)
    assert [r["key"] for r in rows] == [("24h", "xgboost", "1"), ("7d", "xgboost", "2")]
    assert rows[0]["directional_accuracy"] == 1.0 and rows[1]["directional_accuracy"] == 0.0
