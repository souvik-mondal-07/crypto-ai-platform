"""Evaluation metrics for return prediction. All outputs are JSON-safe (None, never NaN)."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


def _f(x: float) -> Optional[float]:
    return float(x) if x is not None and math.isfinite(x) else None


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Optional[float]]:
    """MAE, RMSE, R², directional accuracy and the baselines they must beat.

    * ``baseline_mae`` / ``baseline_rmse`` — predicting a 0% return every time.
    * ``naive_directional_accuracy`` — always guessing the more common direction
      in the evaluated rows (an optimistic baseline, hence a strict test).
    * ``mape`` is deliberately NOT computed on returns (they cross zero, so a
      percentage error is undefined/meaningless); ``price_mape`` is the percentage
      error of the *implied price*, which is mathematically valid because
      price = reference * (1 + return) > 0.
    Rows with a non-finite prediction (e.g. sequence warm-up) are excluded and
    counted in ``n_excluded``.
    """
    y_true = np.asarray(y_true, dtype="float64")
    y_pred = np.asarray(y_pred, dtype="float64")
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape.")
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    n_excluded = int((~mask).sum())
    yt, yp = y_true[mask], y_pred[mask]
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "n_excluded": n_excluded, "mae": None, "rmse": None, "r2": None,
                "directional_accuracy": None, "baseline_mae": None, "baseline_rmse": None,
                "mae_improvement": None, "naive_directional_accuracy": None, "price_mape": None}
    err = yp - yt
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    base_mae = float(np.mean(np.abs(yt)))
    base_rmse = float(np.sqrt(np.mean(yt**2)))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    r2 = float(1.0 - np.sum(err**2) / ss_tot) if n >= 2 and ss_tot > 0 else None

    moving = yt != 0
    if moving.any():
        dir_acc = float(np.mean(np.sign(yp[moving]) == np.sign(yt[moving])))
        p_up = float(np.mean(yt[moving] > 0))
        naive = max(p_up, 1.0 - p_up)
    else:
        dir_acc = naive = None
    # implied-price MAPE: |ref(1+pred) - ref(1+true)| / (ref(1+true)) = |pred - true| / (1 + true)
    denom = 1.0 + yt
    price_mape = float(np.mean(np.abs(err[denom > 0]) / denom[denom > 0]) * 100.0) if (denom > 0).any() else None
    return {
        "n": n, "n_excluded": n_excluded,
        "mae": _f(mae), "rmse": _f(rmse), "r2": _f(r2) if r2 is not None else None,
        "directional_accuracy": _f(dir_acc) if dir_acc is not None else None,
        "baseline_mae": _f(base_mae), "baseline_rmse": _f(base_rmse),
        "mae_improvement": _f(1.0 - mae / base_mae) if base_mae > 0 else None,
        "naive_directional_accuracy": _f(naive) if naive is not None else None,
        "price_mape": _f(price_mape) if price_mape is not None else None,
    }


def interval_coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> Optional[float]:
    """Share of true values that fall inside [lower, upper]."""
    y_true, lower, upper = (np.asarray(a, dtype="float64") for a in (y_true, lower, upper))
    mask = np.isfinite(y_true) & np.isfinite(lower) & np.isfinite(upper)
    if not mask.any():
        return None
    return float(np.mean((y_true[mask] >= lower[mask]) & (y_true[mask] <= upper[mask])))
