import numpy as np
import pandas as pd
import pytest

from ml.config import get_horizon
from ml.config.model_config import MLConfig
from ml.data.dataset_builder import build_dataset
from ml.models.base_model import Preprocessor
from ml.prediction.confidence import (
    calibration_error, confidence_for, direction_for, fit_calibration, return_range,
)
from ml.training.evaluation import interval_coverage, regression_metrics
from ml.training.model_selection import evaluate_gate
from ml.training.validation import chronological_split, walk_forward_splits


# ------------------------------------------------------------------ chronological split


def test_split_is_ordered_non_overlapping_with_embargo():
    s = chronological_split(1000, 0.7, 0.15, embargo=24)
    assert s.train.stop + 24 == s.validation.start
    assert s.validation.stop + 24 == s.test.start
    assert s.train.start == 0 and s.test.stop == 1000
    sizes = s.sizes()
    assert sizes["train"] > sizes["validation"] > 0 and sizes["test"] > 0


def test_split_never_shuffles_and_rejects_bad_input():
    s = chronological_split(500, 0.6, 0.2)
    idx = np.arange(500)
    assert (idx[s.train].max() < idx[s.validation].min()) and (idx[s.validation].max() < idx[s.test].min())
    with pytest.raises(ValueError):
        chronological_split(0, 0.7, 0.15)
    with pytest.raises(ValueError):
        chronological_split(30, 0.7, 0.15, embargo=20)  # would leave nothing
    with pytest.raises(ValueError):
        chronological_split(100, 0.7, 0.15, embargo=-1)


def test_dataset_split_has_no_target_window_overlap(candles):
    spec = get_horizon("24h")
    cfg = MLConfig()
    ds = build_dataset(candles, spec, cfg, now=(candles["timestamp"].iloc[-1] + pd.Timedelta(hours=2)).to_pydatetime())
    s = ds.split(cfg)
    last_train_target_time = ds.meta["timestamp"].iloc[s.train.stop - 1] + pd.Timedelta(seconds=spec.horizon_seconds)
    first_val_feature_time = ds.meta["timestamp"].iloc[s.validation.start]
    assert last_train_target_time < first_val_feature_time
    last_val_target_time = ds.meta["timestamp"].iloc[s.validation.stop - 1] + pd.Timedelta(seconds=spec.horizon_seconds)
    assert last_val_target_time < ds.meta["timestamp"].iloc[s.test.start]


def test_walk_forward_folds_expand_and_stay_in_the_future():
    folds = list(walk_forward_splits(1000, 4, 300, 100, embargo=10))
    assert len(folds) == 4
    prev_end = 0
    for train, test in folds:
        assert train.max() + 10 < test.min()
        assert len(train) >= prev_end
        prev_end = len(train)
    with pytest.raises(ValueError):
        list(walk_forward_splits(100, 4, 90, 50))


def test_scaler_statistics_come_from_training_rows_only():
    train = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [10.0, 10.0, 12.0, 12.0]})
    holdout = pd.DataFrame({"a": [1000.0, 2000.0], "b": [5.0, 5.0]})
    pre = Preprocessor().fit(train)
    assert pre.mean[0] == pytest.approx(2.5)                 # unaffected by the huge hold-out values
    z = pre.transform(holdout)
    assert z[0, 0] == pytest.approx((1000 - 2.5) / np.std([1, 2, 3, 4]))
    # NaNs are filled with the TRAIN median, not the hold-out's
    nan_row = pd.DataFrame({"a": [np.nan], "b": [np.nan]})
    assert pre.transform(nan_row)[0, 0] == pytest.approx((2.5 - 2.5) / np.std([1, 2, 3, 4]))


# ------------------------------------------------------------------ metrics


def test_regression_metrics_match_hand_computation():
    y = np.array([0.01, -0.02, 0.03, -0.01])
    p = np.array([0.02, -0.01, 0.01, 0.01])
    m = regression_metrics(y, p)
    assert m["mae"] == pytest.approx(np.mean([0.01, 0.01, 0.02, 0.02]))
    assert m["rmse"] == pytest.approx(np.sqrt(np.mean([1e-4, 1e-4, 4e-4, 4e-4])))
    assert m["baseline_mae"] == pytest.approx(np.mean(np.abs(y)))
    assert m["directional_accuracy"] == pytest.approx(0.75)
    assert m["naive_directional_accuracy"] == pytest.approx(0.5)
    ss_res, ss_tot = np.sum((y - p) ** 2), np.sum((y - y.mean()) ** 2)
    assert m["r2"] == pytest.approx(1 - ss_res / ss_tot)
    assert m["mae_improvement"] == pytest.approx(1 - m["mae"] / m["baseline_mae"])


def test_price_mape_is_defined_but_return_mape_is_not_reported():
    m = regression_metrics(np.array([0.1, -0.1]), np.array([0.0, 0.0]))
    assert "mape" not in m
    assert m["price_mape"] == pytest.approx(np.mean([0.1 / 1.1, 0.1 / 0.9]) * 100)


def test_metrics_exclude_non_finite_predictions_and_handle_empty():
    m = regression_metrics(np.array([0.01, 0.02, 0.03]), np.array([np.nan, 0.02, 0.01]))
    assert m["n"] == 2 and m["n_excluded"] == 1
    empty = regression_metrics(np.array([0.01]), np.array([np.nan]))
    assert empty["n"] == 0 and empty["mae"] is None
    with pytest.raises(ValueError):
        regression_metrics(np.array([1.0]), np.array([1.0, 2.0]))


def test_r2_undefined_for_constant_target():
    assert regression_metrics(np.zeros(5), np.ones(5) * 0.01)["r2"] is None


def test_interval_coverage():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    assert interval_coverage(y, y - 0.5, y + 0.5) == 1.0
    assert interval_coverage(y, y + 0.5, y + 1.5) == 0.0


# ------------------------------------------------------------------ gate


def _m(**kw):
    base = {"n": 300, "mae": 0.9, "baseline_mae": 1.0, "mae_improvement": 0.1,
            "directional_accuracy": 0.58, "naive_directional_accuracy": 0.52}
    base.update(kw)
    return base


def test_gate_passes_only_with_demonstrated_skill():
    cfg = MLConfig()
    assert evaluate_gate(_m(), cfg) == (True, [])
    ok, why = evaluate_gate(_m(mae_improvement=-0.02, mae=1.02), cfg)
    assert not ok and any("baseline" in r for r in why)
    ok, why = evaluate_gate(_m(directional_accuracy=0.51), cfg)
    assert not ok and any("directional" in r for r in why)
    ok, why = evaluate_gate(_m(n=10), cfg)
    assert not ok and any("test rows" in r for r in why)
    ok, _ = evaluate_gate(_m(mae=None, baseline_mae=None, mae_improvement=None), cfg)
    assert not ok


# ------------------------------------------------------------------ calibration / confidence


def _calib_data(seed=0, n=600, skill=0.8):
    rng = np.random.default_rng(seed)
    true = rng.normal(0, 0.01, n)
    pred = skill * true + rng.normal(0, 0.006, n)
    return pred, true


def test_calibration_produces_interval_direction_and_confidence():
    pred, true = _calib_data()
    cal = fit_calibration(pred, true, alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    assert cal["interval"]["lower"] < 0 < cal["interval"]["upper"]
    lo, hi = return_range(0.01, cal)
    assert lo < 0.01 < hi
    c_small, c_big = confidence_for(0.0005, cal), confidence_for(0.02, cal)
    assert 0.0 <= c_small <= c_big <= 1.0        # monotone in magnitude
    assert direction_for(0.02, cal) == "up" and direction_for(-0.02, cal) == "down"
    assert direction_for(0.0, cal) == "flat"
    # on fresh data the reported confidence is close to the observed hit rate
    p2, t2 = _calib_data(seed=5)
    assert calibration_error(p2, t2, cal) < 0.1


def test_interval_empirical_coverage_close_to_nominal():
    pred, true = _calib_data(n=2000)
    cal = fit_calibration(pred[:1000], true[:1000], alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    lo, hi = pred[1000:] + cal["interval"]["lower"], pred[1000:] + cal["interval"]["upper"]
    assert abs(interval_coverage(true[1000:], lo, hi) - 0.8) < 0.06


def test_confidence_unavailable_when_too_little_validation_data():
    pred, true = _calib_data(n=60)
    cal = fit_calibration(pred, true, alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    assert cal["direction_calibration"] is None
    assert confidence_for(0.01, cal) is None
    tiny = fit_calibration(pred[:10], true[:10], alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    assert tiny["interval"] is None and return_range(0.01, tiny) is None


def test_confidence_is_deterministic_never_random():
    pred, true = _calib_data()
    a = fit_calibration(pred, true, alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    b = fit_calibration(pred, true, alpha=0.2, min_samples=100, flat_mae_fraction=0.25)
    assert a == b and confidence_for(0.012, a) == confidence_for(0.012, b)
