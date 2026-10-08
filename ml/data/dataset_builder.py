"""Reusable dataset pipeline: candles -> clean -> features -> targets -> chronological split.

Leakage rules enforced here (and asserted in ml/tests via the backend test-suite):

* a feature row at index ``t`` is computed ONLY from candles ``<= t`` (all feature
  builders use trailing windows; see their module docstrings);
* the target at ``t`` is ``close[t + steps] / close[t] - 1`` and is the ONLY column
  that looks forward; it is never part of ``X``;
* the final (still-open) candle is dropped before anything else;
* a target is valid only if the candle ``steps`` rows ahead is *exactly* one horizon
  later in wall-clock time (no silent gaps);
* sentiment uses only articles published at/before the candle's close time;
* split points are chronological, with an embargo of ``steps`` rows between
  segments so overlapping target windows cannot straddle a boundary;
* scaling/imputation statistics (``Preprocessor``) are fitted on the training
  segment only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ml.config.feature_config import FEATURE_VERSION, FeatureConfig
from ml.config.model_config import HorizonSpec, MLConfig
from ml.data.preprocessing import CleaningReport, clean_candles, drop_incomplete_last_candle
from ml.data.validation import CandleValidation, validate_candles
from ml.features.fundamental_features import FUNDAMENTAL_SNAPSHOT_FEATURES
from ml.features.market_features import build_market_features
from ml.features.sentiment_features import SENTIMENT_FEATURE_NAMES, build_sentiment_features
from ml.features.technical_features import build_technical_features
from ml.training.validation import ChronologicalSplit, chronological_split

TARGET_COLUMN = "target"


class InsufficientDataError(Exception):
    """Raised when real history is too short/poor to build or serve a dataset."""

    def __init__(self, message: str, *, rows: int = 0):
        super().__init__(message)
        self.rows = rows


@dataclass
class Dataset:
    X: pd.DataFrame                 # model inputs only (no target, no raw prices)
    y: pd.Series                    # future return over the horizon
    meta: pd.DataFrame              # timestamp (open), as_of (close time), close
    feature_names: list[str]
    horizon: HorizonSpec
    feature_version: str = FEATURE_VERSION
    dropped_features: dict[str, str] = field(default_factory=dict)
    cleaning: Optional[CleaningReport] = None
    validation: Optional[CandleValidation] = None
    future_volatility: Optional[pd.Series] = None

    def __len__(self) -> int:
        return len(self.X)

    def split(self, config: MLConfig) -> ChronologicalSplit:
        return chronological_split(
            len(self), config.train_fraction, config.validation_fraction, embargo=self.horizon.steps
        )


# --------------------------------------------------------------------------- features


def build_feature_frame(
    candles: pd.DataFrame,
    horizon: HorizonSpec,
    *,
    sentiment_articles: Optional[Iterable[dict]] = None,
    feature_config: FeatureConfig = FeatureConfig(),
) -> pd.DataFrame:
    """All candidate features for every candle (no targets). Index == candles' index."""
    parts = [build_market_features(candles, feature_config), build_technical_features(candles, feature_config)]
    if feature_config.include_sentiment:
        as_of = candles["timestamp"] + pd.Timedelta(seconds=horizon.interval_seconds)
        parts.append(build_sentiment_features(as_of, sentiment_articles, feature_config))
    return pd.concat(parts, axis=1)


def add_targets(candles: pd.DataFrame, horizon: HorizonSpec) -> tuple[pd.Series, pd.Series]:
    """Future return (and realised future volatility) — the only forward-looking columns."""
    steps = horizon.steps
    close = candles["close"].astype("float64")
    future_close = close.shift(-steps)
    ret = future_close / close - 1.0

    # Valid only if the future candle is exactly one horizon later in real time.
    delta = (candles["timestamp"].shift(-steps) - candles["timestamp"]).dt.total_seconds()
    ret = ret.where(delta == horizon.horizon_seconds)

    vol = pd.Series(np.nan, index=candles.index, dtype="float64")
    if steps >= 3:
        log_ret = np.log(close).diff()
        # std of the NEXT `steps` one-candle log returns (t+1 .. t+steps).
        vol = log_ret[::-1].rolling(steps, min_periods=steps).std()[::-1].shift(-1)
        vol = vol.where(delta == horizon.horizon_seconds)
    return ret, vol


# --------------------------------------------------------------------------- dataset


def build_dataset(
    raw_candles: pd.DataFrame,
    horizon: HorizonSpec,
    config: MLConfig,
    *,
    sentiment_articles: Optional[Iterable[dict]] = None,
    feature_config: FeatureConfig = FeatureConfig(),
    now: Optional[datetime] = None,
) -> Dataset:
    """Full training dataset. Raises ``InsufficientDataError`` instead of producing
    anything from too little data."""
    clean, report = clean_candles(raw_candles, horizon.interval_seconds)
    clean = drop_incomplete_last_candle(clean, horizon.interval_seconds, now)
    validation = validate_candles(
        clean, interval_seconds=horizon.interval_seconds, min_rows=config.min_history_length, report=report
    )
    if not validation.ok:
        raise InsufficientDataError(validation.reason or "history unusable", rows=validation.rows)

    frame = build_feature_frame(clean, horizon, sentiment_articles=sentiment_articles, feature_config=feature_config)
    target, fut_vol = add_targets(clean, horizon)
    as_of = clean["timestamp"] + pd.Timedelta(seconds=horizon.interval_seconds)

    # ---- choose features by coverage over the (chronological) training segment ----
    labelled = target.notna()
    n_labelled = int(labelled.sum())
    train_end_pos = max(int(n_labelled * config.train_fraction), 1)
    train_rows_idx = frame.index[labelled][:train_end_pos]
    coverage = frame.loc[train_rows_idx].notna().mean()

    dropped: dict[str, str] = {}
    keep = list(frame.columns)

    sentiment_cols = [c for c in SENTIMENT_FEATURE_NAMES if c in keep]
    if sentiment_cols:
        group_cov = float(coverage[sentiment_cols].mean())
        if group_cov < config.min_feature_coverage:
            for c in sentiment_cols:
                dropped[c] = f"sentiment coverage {group_cov:.0%} < {config.min_feature_coverage:.0%} in training window"
                keep.remove(c)
    for c in list(keep):
        if c in sentiment_cols:
            continue
        if coverage[c] < config.min_feature_coverage:
            dropped[c] = f"coverage {coverage[c]:.0%} < {config.min_feature_coverage:.0%}"
            keep.remove(c)
    # Snapshot-only fundamentals can never be selected here (they are not in `frame`).
    assert not set(keep) & set(FUNDAMENTAL_SNAPSHOT_FEATURES)

    required = [c for c in keep if c not in sentiment_cols]  # sentiment may stay NaN (trees handle it)
    X_all = frame[keep]
    row_ok = labelled & X_all[required].notna().all(axis=1)

    X = X_all[row_ok].reset_index(drop=True)
    y = target[row_ok].reset_index(drop=True).rename(TARGET_COLUMN)
    meta = pd.DataFrame(
        {"timestamp": clean["timestamp"][row_ok].values, "as_of": as_of[row_ok].values, "close": clean["close"][row_ok].values}
    ).reset_index(drop=True)
    fv = fut_vol[row_ok].reset_index(drop=True) if steps_has_vol(horizon) else None

    if len(X) < config.min_history_length // 2 + 1 or len(X) < (config.min_test_samples + config.min_calibration_samples) * 2:
        raise InsufficientDataError(
            f"Only {len(X)} labelled feature rows after cleaning/warm-up; not enough to train and validate.",
            rows=len(X),
        )

    return Dataset(
        X=X, y=y, meta=meta, feature_names=list(X.columns), horizon=horizon,
        dropped_features=dropped, cleaning=report, validation=validation, future_volatility=fv,
    )


def steps_has_vol(horizon: HorizonSpec) -> bool:
    return horizon.steps >= 3


# --------------------------------------------------------------------------- inference


def build_inference_row(
    raw_candles: pd.DataFrame,
    horizon: HorizonSpec,
    feature_names: list[str],
    config: MLConfig,
    *,
    sentiment_articles: Optional[Iterable[dict]] = None,
    feature_config: FeatureConfig = FeatureConfig(),
    required_context: int = 0,
    now: Optional[datetime] = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Feature rows for the most recent CLOSED candle (plus ``required_context`` earlier
    rows for sequence models), using exactly the features the model was trained on.

    Returns (X rows, info) where info has ``as_of``, ``close`` and ``candles_used``.
    Raises ``InsufficientDataError`` if the history is too short or any required
    (non-sentiment) feature is missing.
    """
    clean, report = clean_candles(raw_candles, horizon.interval_seconds)
    clean = drop_incomplete_last_candle(clean, horizon.interval_seconds, now)
    min_rows = max(horizon.predict_candles, 1)
    validation = validate_candles(
        clean, interval_seconds=horizon.interval_seconds, min_rows=min_rows, report=report,
        max_staleness_candles=max(3, required_context + 3), now=now,
    )
    if not validation.ok:
        raise InsufficientDataError(validation.reason or "history unusable", rows=validation.rows)

    frame = build_feature_frame(clean, horizon, sentiment_articles=sentiment_articles, feature_config=feature_config)
    missing_cols = [c for c in feature_names if c not in frame.columns]
    if missing_cols:
        raise InsufficientDataError(f"Model expects features that cannot be built: {missing_cols[:5]}")
    rows = frame[feature_names].iloc[-(required_context + 1):]
    required = [c for c in feature_names if c not in SENTIMENT_FEATURE_NAMES]
    if len(rows) < required_context + 1 or rows[required].isna().any().any():
        raise InsufficientDataError("Latest candles do not yet have enough history for every required feature.")
    last = clean.iloc[-1]
    info = {
        "as_of": last["timestamp"] + pd.Timedelta(seconds=horizon.interval_seconds),
        "close": float(last["close"]),
        "candles_used": int(len(clean)),
    }
    return rows.reset_index(drop=True), info
