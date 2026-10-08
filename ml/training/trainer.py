"""Train + validate + evaluate + persist ONE model for one (coin, horizon).

    Dataset -> chronological split -> fit (train; validation only for early stopping)
            -> calibrate on validation -> evaluate on the untouched test segment
            -> activation gate -> artifact + registry record

Training only ever happens when a caller (the training pipeline / CLI) invokes
``train_one``. Nothing in the API or the application start-up path calls it.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.config.feature_config import FEATURE_VERSION
from ml.config.model_config import MLConfig
from ml.data.dataset_builder import Dataset
from ml.models.base_model import BasePredictionModel
from ml.models.model_registry import (
    STATUS_ACTIVE, STATUS_REJECTED, ModelRecord, ModelRegistry, create_model,
)
from ml.prediction.confidence import calibration_error, confidence_for, fit_calibration, return_range
from ml.training.evaluation import interval_coverage, regression_metrics
from ml.training.model_selection import evaluate_gate
from ml.training.validation import ChronologicalSplit, walk_forward_splits

logger = logging.getLogger("crypto_ai_platform.ml.training")


@dataclass
class TrainResult:
    record: ModelRecord
    model: BasePredictionModel
    calibration: dict[str, Any]
    val_pred: np.ndarray
    test_pred: np.ndarray
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)


def predict_segment(model: BasePredictionModel, X: pd.DataFrame, seg: slice) -> np.ndarray:
    """Predictions for rows ``seg`` of ``X``. Sequence models get the ``required_context``
    PRECEDING rows (earlier in time only), so a segment does not lose its first rows."""
    start, stop, _ = seg.indices(len(X))
    ctx = min(model.required_context, start)
    preds = model.predict(X.iloc[start - ctx:stop])
    return preds[ctx:]


def train_one(
    dataset: Dataset,
    model_type: str,
    config: MLConfig,
    registry: ModelRegistry,
    *,
    coin_id: str,
    symbol: Optional[str] = None,
    horizon_name: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    extra_info: Optional[dict[str, Any]] = None,
) -> TrainResult:
    split: ChronologicalSplit = dataset.split(config)
    X, y = dataset.X, dataset.y

    model = create_model(model_type, params if params is not None else config.model_params.get(model_type))
    model.fit(X.iloc[split.train], y.iloc[split.train], X.iloc[split.validation], y.iloc[split.validation])

    return finalize_model(
        model, dataset, split, config, registry, coin_id=coin_id, symbol=symbol,
        horizon_name=horizon_name, extra_info=extra_info,
        val_pred=predict_segment(model, X, split.validation),
        test_pred=predict_segment(model, X, split.test),
        train_pred=predict_segment(model, X, split.train),
    )


def finalize_model(
    model: BasePredictionModel,
    dataset: Dataset,
    split: ChronologicalSplit,
    config: MLConfig,
    registry: ModelRegistry,
    *,
    coin_id: str,
    val_pred: np.ndarray,
    test_pred: np.ndarray,
    train_pred: Optional[np.ndarray] = None,
    symbol: Optional[str] = None,
    horizon_name: Optional[str] = None,
    extra_info: Optional[dict[str, Any]] = None,
    member_paths: Optional[list[str]] = None,
) -> TrainResult:
    """Calibrate on validation, evaluate on test, apply the gate, persist, register.

    Shared by single models and the ensemble (whose predictions are combinations of
    member predictions over the same segments)."""
    horizon = horizon_name or dataset.horizon.name
    model_type = model.model_type
    y = dataset.y
    y_val = y.iloc[split.validation].to_numpy()
    y_test = y.iloc[split.test].to_numpy()

    cal = fit_calibration(
        val_pred, y_val, alpha=config.interval_alpha, min_samples=config.min_calibration_samples,
        flat_mae_fraction=config.flat_threshold_mae_fraction,
    )
    metrics: dict[str, Any] = {
        "validation": regression_metrics(y_val, val_pred),
        "test": regression_metrics(y_test, test_pred),
    }
    if train_pred is not None:
        metrics["train"] = regression_metrics(y.iloc[split.train].to_numpy(), train_pred)
    if cal.get("interval"):
        lo = test_pred + cal["interval"]["lower"]
        hi = test_pred + cal["interval"]["upper"]
        metrics["interval_coverage_test"] = interval_coverage(y_test, lo, hi)
        metrics["interval_nominal_coverage"] = cal["interval"]["nominal_coverage"]
    cal_err = calibration_error(test_pred, y_test, cal)
    metrics["confidence_calibration_error_test"] = cal_err
    cal["confidence_reliable"] = bool(
        cal.get("direction_calibration") is not None and cal_err is not None and cal_err <= config.max_calibration_error
    )

    passed, reasons = evaluate_gate(metrics["test"], config)
    importance = model.feature_importance()
    top_features = dict(sorted(importance.items(), key=lambda kv: kv[1], reverse=True)[:15])

    version = registry.next_version(coin_id, horizon, model_type)
    directory = registry.version_dir(coin_id, horizon, model_type, version)
    try:
        if member_paths is not None:
            model._member_paths = member_paths  # type: ignore[attr-defined]
        model.save(directory)
        (directory / "calibration.json").write_text(json.dumps(cal, indent=2))
        info = {
            "rows": len(dataset), "split_sizes": split.sizes(), "embargo_rows": split.embargo,
            "date_range": [str(dataset.meta["timestamp"].iloc[0]), str(dataset.meta["timestamp"].iloc[-1])],
            "n_features": len(dataset.feature_names), "dropped_features": dataset.dropped_features,
            "top_feature_importance": top_features, "gate_reasons": reasons,
            "confidence_reliable": cal["confidence_reliable"], "params": model.params,
            **(extra_info or {}),
        }
        record = ModelRegistry.new_record(
            model_type=model_type, version=version, coin_id=coin_id, horizon=horizon,
            feature_version=dataset.feature_version or FEATURE_VERSION, metrics=metrics,
            artifact_path=registry.relative(directory), status=STATUS_REJECTED, symbol=symbol, info=info,
        )
        registry.write_record(record)
        if passed:
            registry.activate(record)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)  # never leave a half-written artifact behind
        raise

    logger.info("%s %s %s -> %s (test MAE improvement=%s, dir.acc=%s)", coin_id, horizon, model_type,
                record.status, metrics["test"].get("mae_improvement"), metrics["test"].get("directional_accuracy"))
    return TrainResult(record, model, cal, val_pred, test_pred, passed, reasons)


def walk_forward_evaluate(
    dataset: Dataset, model_type: str, config: MLConfig, *, n_splits: int = 4, params: Optional[dict[str, Any]] = None
) -> list[dict[str, Any]]:
    """Expanding-window walk-forward metrics (no artifacts are saved). Each fold trains
    only on rows before its test window, with an embargo of ``steps`` rows."""
    n = len(dataset)
    test_size = max(config.min_test_samples, n // (n_splits + 3))
    min_train = max(int(n * 0.4), 100)
    folds = []
    for i, (tr, te) in enumerate(walk_forward_splits(n, n_splits, min_train, test_size, dataset.horizon.steps)):
        model = create_model(model_type, params if params is not None else config.model_params.get(model_type))
        val_n = max(len(tr) // 6, 20)
        fit_idx, val_idx = tr[:-val_n], tr[-val_n:]
        model.fit(dataset.X.iloc[fit_idx], dataset.y.iloc[fit_idx], dataset.X.iloc[val_idx], dataset.y.iloc[val_idx])
        start = int(te[0])
        pred = predict_segment(model, dataset.X, slice(start, int(te[-1]) + 1))
        folds.append({"fold": i, "train_rows": len(tr), "test_rows": len(te),
                      "test_start": str(dataset.meta["timestamp"].iloc[start]),
                      **regression_metrics(dataset.y.iloc[te].to_numpy(), pred)})
    return folds
