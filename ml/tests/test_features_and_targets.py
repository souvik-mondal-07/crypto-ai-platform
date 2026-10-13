import math

import numpy as np
import pandas as pd
import pytest

from ml.config import FEATURE_VERSION, FeatureConfig, get_horizon
from ml.config.model_config import MLConfig
from ml.data.dataset_builder import InsufficientDataError, add_targets, build_dataset, build_feature_frame
from ml.features._indicators_bridge import load_indicators
from ml.features.fundamental_features import FUNDAMENTAL_SNAPSHOT_FEATURES, snapshot_fundamental_features
from ml.features.market_features import build_market_features
from ml.features.sentiment_features import SENTIMENT_FEATURE_NAMES, build_sentiment_features
from ml.features.technical_features import build_technical_features
from ml.tests.conftest import make_candles

NOW_AFTER = lambda df: (df["timestamp"].iloc[-1] + pd.Timedelta(hours=2)).to_pydatetime()


def test_market_features_expected_columns_finite_and_scale_free(candles):
    f = build_market_features(candles)
    for col in ("log_return_1", "return_1", "return_24", "volatility_24", "candle_range", "volume_change_1", "volume_zscore_24"):
        assert col in f.columns
    assert not np.isinf(f.to_numpy(dtype=float)).any()
    # raw prices / raw volume must not be model inputs
    assert not {"open", "high", "low", "close", "volume"} & set(f.columns)
    assert f["return_1"].iloc[1] == pytest.approx(candles["close"].iloc[1] / candles["close"].iloc[0] - 1)


def test_technical_features_reuse_phase10_indicators(candles):
    ind = load_indicators()
    closes = candles["close"].tolist()
    f = build_technical_features(candles)
    expected_rsi = [np.nan if v is None else v for v in ind.rsi(closes, 14)]
    np.testing.assert_allclose(f["rsi"].to_numpy(), expected_rsi, equal_nan=True)
    sma20 = np.array([np.nan if v is None else v for v in ind.sma(closes, 20)])
    np.testing.assert_allclose(f["close_vs_sma_20"].to_numpy(), candles["close"].to_numpy() / sma20 - 1, equal_nan=True)
    assert f["rsi"].dropna().between(0, 100).all()
    assert set(f["trend_code"].dropna().unique()) <= {-1.0, 0.0, 1.0}
    for col in ("macd", "macd_signal", "macd_hist", "bb_upper_dist", "bb_lower_dist", "bb_width", "atr_pct",
                "close_vs_ema_20", "volume_vs_sma_20", "dist_to_support", "dist_to_resistance"):
        assert col in f.columns


def test_warmup_rows_are_nan_not_filled(candles):
    f = build_technical_features(candles)
    assert f["close_vs_sma_200"].iloc[:199].isna().all()
    assert not np.isnan(f["close_vs_sma_200"].iloc[250])


# ------------------------------------------------------------------ targets


def test_target_is_exact_future_return(candles):
    spec = get_horizon("4h")
    target, _ = add_targets(candles, spec)
    c = candles["close"].to_numpy()
    for t in (0, 10, 500):
        assert target.iloc[t] == pytest.approx(c[t + 4] / c[t] - 1)
    assert target.iloc[-4:].isna().all()   # no future -> no label, never a guess


def test_target_invalid_across_time_gap(candles):
    spec = get_horizon("4h")
    gapped = candles.drop(index=[100]).reset_index(drop=True)
    target, _ = add_targets(gapped, spec)
    # rows whose +4 candles window spans the missing hour are unlabeled
    assert target.iloc[96:100].isna().all()
    assert target.iloc[95] == pytest.approx(gapped["close"].iloc[99] / gapped["close"].iloc[95] - 1) or math.isnan(target.iloc[95])


def test_future_volatility_uses_only_forward_window(candles):
    spec = get_horizon("24h")
    _, vol = add_targets(candles, spec)
    lr = np.log(candles["close"]).diff().to_numpy()
    t = 300
    assert vol.iloc[t] == pytest.approx(np.std(lr[t + 1:t + 25], ddof=1))
    _, vol1h = add_targets(candles, get_horizon("1h"))
    assert vol1h.isna().all()   # too few future points to define a volatility


def test_target_is_not_a_feature_and_dataset_is_aligned(candles):
    cfg = MLConfig()
    ds = build_dataset(candles, get_horizon("4h"), cfg, now=NOW_AFTER(candles))
    assert "target" not in ds.X.columns and not any(c.startswith("future") for c in ds.X.columns)
    assert len(ds.X) == len(ds.y) == len(ds.meta)
    assert ds.meta["timestamp"].is_monotonic_increasing
    assert ds.X.drop(columns=[c for c in ds.X.columns if c in SENTIMENT_FEATURE_NAMES]).notna().all().all()
    assert ds.feature_version == FEATURE_VERSION


def test_insufficient_history_raises_not_fabricates():
    short = make_candles(200)
    with pytest.raises(InsufficientDataError):
        build_dataset(short, get_horizon("24h"), MLConfig(), now=NOW_AFTER(short))


# ------------------------------------------------------------------ LEAKAGE


@pytest.mark.parametrize("horizon", ["1h", "24h"])
def test_features_at_t_do_not_change_when_future_candles_change(candles, horizon):
    """Truncation invariance: the feature row for candle t must be identical whether
    the series ends at t or continues with arbitrary (even absurd) future data."""
    spec = get_horizon(horizon)
    full = build_feature_frame(candles, spec)
    for t in (300, 700, 1200):
        truncated = build_feature_frame(candles.iloc[: t + 1].reset_index(drop=True), spec)
        pd.testing.assert_series_equal(full.iloc[t], truncated.iloc[t], check_names=False, rtol=1e-9, atol=1e-12)

    corrupted = candles.copy()
    corrupted.loc[801:, ["open", "high", "low", "close"]] *= 50.0
    corrupted.loc[801:, "volume"] *= 1000.0
    changed = build_feature_frame(corrupted, spec)
    pd.testing.assert_frame_equal(full.iloc[:801], changed.iloc[:801], rtol=1e-9, atol=1e-12)


def test_sentiment_features_ignore_articles_published_after_candle_close(candles):
    spec = get_horizon("1h")
    base_articles = [
        {"published_at": candles["timestamp"].iloc[i] + pd.Timedelta(minutes=5), "label": "positive", "score": 0.6}
        for i in range(200, 260)
    ]
    future_articles = [
        {"published_at": candles["timestamp"].iloc[400] + pd.Timedelta(minutes=5), "label": "negative", "score": -0.9}
        for _ in range(40)
    ]
    a = build_feature_frame(candles, spec, sentiment_articles=base_articles)
    b = build_feature_frame(candles, spec, sentiment_articles=base_articles + future_articles)
    cols = list(SENTIMENT_FEATURE_NAMES)
    # every row whose close time precedes the first "future" article is untouched
    cutoff = 399
    pd.testing.assert_frame_equal(a[cols].iloc[:cutoff], b[cols].iloc[:cutoff])
    # and the late articles DO show up later (the test is not vacuous)
    assert not a[cols].iloc[405:410].equals(b[cols].iloc[405:410])


def test_article_published_exactly_at_close_counts_but_one_second_later_does_not():
    ts = pd.Series(pd.date_range("2025-01-01", periods=1, freq="1h", tz="UTC") + pd.Timedelta(hours=1))  # as_of
    at = [{"published_at": ts.iloc[0], "label": "positive", "score": 0.5}] * 3
    after = [{"published_at": ts.iloc[0] + pd.Timedelta(seconds=1), "label": "positive", "score": 0.5}] * 3
    assert build_sentiment_features(ts, at)["sent_score"].iloc[0] == pytest.approx(0.5)
    assert np.isnan(build_sentiment_features(ts, after)["sent_score"].iloc[0])


def test_sentiment_needs_minimum_articles_and_is_never_invented(candles):
    spec = get_horizon("1h")
    one = [{"published_at": candles["timestamp"].iloc[300], "label": "positive", "score": 0.9}]
    f = build_feature_frame(candles, spec, sentiment_articles=one)
    assert f["sent_score"].isna().all()
    none = build_feature_frame(candles, spec, sentiment_articles=None)
    assert none[list(SENTIMENT_FEATURE_NAMES)].isna().all().all()


def test_sentiment_group_dropped_when_coverage_is_low(candles):
    ds = build_dataset(candles, get_horizon("4h"), MLConfig(), now=NOW_AFTER(candles))
    assert not set(SENTIMENT_FEATURE_NAMES) & set(ds.feature_names)
    assert set(SENTIMENT_FEATURE_NAMES) <= set(ds.dropped_features)


def test_sentiment_kept_when_real_coverage_exists(candles):
    arts = [
        {"published_at": candles["timestamp"].iloc[i] + pd.Timedelta(minutes=1), "label": "neutral", "score": 0.05}
        for i in range(0, 1490, 2)
    ]
    ds = build_dataset(candles, get_horizon("4h"), MLConfig(), sentiment_articles=arts, now=NOW_AFTER(candles))
    assert "sent_score" in ds.feature_names


def test_fundamental_snapshot_features_never_enter_training(candles):
    ds = build_dataset(candles, get_horizon("24h"), MLConfig(), now=NOW_AFTER(candles))
    assert not set(FUNDAMENTAL_SNAPSHOT_FEATURES) & set(ds.feature_names)
    assert FeatureConfig().include_fundamental_snapshot is False


def test_fundamental_features_handle_missing_data():
    f = snapshot_fundamental_features({"price_usd": 100.0, "ath_usd": 200.0, "market_cap_usd": None, "max_supply": 0})
    assert f["fund_ath_distance"] == pytest.approx(-0.5)
    assert math.isnan(f["fund_market_cap_log"]) and math.isnan(f["fund_circulating_to_max_supply"])
    full = snapshot_fundamental_features({"market_cap_usd": 1e9, "volume_24h_usd": 1e8, "circulating_supply": 50,
                                          "total_supply": 100, "max_supply": 200, "market_cap_rank": 5})
    assert full["fund_volume_to_market_cap"] == pytest.approx(0.1)
    assert full["fund_circulating_to_max_supply"] == pytest.approx(0.25)
