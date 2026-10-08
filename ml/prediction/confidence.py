"""Prediction intervals, direction and confidence — all derived from validation data.

Nothing here is random or hand-tuned per coin:

* **Range**: split-conformal style. Residuals ``(actual - predicted)`` on the
  validation segment give lower/upper quantiles; the range is
  ``predicted + [q_lo, q_hi]``. Its real coverage on the untouched test segment is
  measured and stored with the model (see training/trainer.py).
* **Direction**: sign of the predicted return; ``flat`` when the predicted move is
  smaller than ``flat_threshold_mae_fraction`` x validation MAE.
* **Confidence**: the empirical probability that the predicted DIRECTION was right,
  estimated on validation rows via monotone (isotonic) regression of
  "direction hit" on ``|predicted return|``. It is the probability of the direction
  being correct, not of reaching a price. If too few validation rows exist, or the
  calibration proves unreliable on the test segment, confidence is ``None`` with
  ``confidence_status == "unavailable"``.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np


def fit_calibration(
    val_pred: np.ndarray,
    val_true: np.ndarray,
    *,
    alpha: float,
    min_samples: int,
    flat_mae_fraction: float,
) -> dict[str, Any]:
    pred = np.asarray(val_pred, dtype="float64")
    true = np.asarray(val_true, dtype="float64")
    mask = np.isfinite(pred) & np.isfinite(true)
    pred, true = pred[mask], true[mask]
    n = len(pred)
    cal: dict[str, Any] = {"n_validation": int(n), "alpha": alpha, "interval": None, "direction_calibration": None,
                           "flat_threshold": None, "confidence_reliable": False}
    if n < 20:
        return cal

    resid = true - pred
    lo_level = max(0.0, math.floor((n + 1) * alpha / 2) / n)
    hi_level = min(1.0, math.ceil((n + 1) * (1 - alpha / 2)) / n)
    cal["interval"] = {
        "lower": float(np.quantile(resid, lo_level)),
        "upper": float(np.quantile(resid, hi_level)),
        "nominal_coverage": 1.0 - alpha,
    }
    cal["flat_threshold"] = float(flat_mae_fraction * np.mean(np.abs(resid)))

    if n >= min_samples:
        from sklearn.isotonic import IsotonicRegression

        moving = (true != 0) & (pred != 0)
        if moving.sum() >= min_samples:
            hit = (np.sign(pred[moving]) == np.sign(true[moving])).astype("float64")
            x = np.abs(pred[moving])
            iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip").fit(x, hit)
            cal["direction_calibration"] = {
                "x": [float(v) for v in iso.X_thresholds_],
                "y": [float(v) for v in iso.y_thresholds_],
                "n": int(moving.sum()),
                "overall_hit_rate": float(hit.mean()),
            }
    return cal


def confidence_for(pred_return: float, cal: dict[str, Any]) -> Optional[float]:
    dc = cal.get("direction_calibration")
    if not dc or not math.isfinite(pred_return):
        return None
    return float(np.clip(np.interp(abs(pred_return), dc["x"], dc["y"]), 0.0, 1.0))


def direction_for(pred_return: float, cal: dict[str, Any]) -> str:
    thr = cal.get("flat_threshold") or 0.0
    if abs(pred_return) <= thr:
        return "flat"
    return "up" if pred_return > 0 else "down"


def return_range(pred_return: float, cal: dict[str, Any]) -> Optional[tuple[float, float]]:
    iv = cal.get("interval")
    if not iv:
        return None
    return pred_return + iv["lower"], pred_return + iv["upper"]


def calibration_error(pred: np.ndarray, true: np.ndarray, cal: dict[str, Any]) -> Optional[float]:
    """|mean predicted confidence - observed direction hit rate| on a held-out segment."""
    pred = np.asarray(pred, dtype="float64")
    true = np.asarray(true, dtype="float64")
    mask = np.isfinite(pred) & np.isfinite(true) & (pred != 0) & (true != 0)
    if mask.sum() < 20 or not cal.get("direction_calibration"):
        return None
    conf = np.interp(np.abs(pred[mask]), cal["direction_calibration"]["x"], cal["direction_calibration"]["y"])
    hit = (np.sign(pred[mask]) == np.sign(true[mask])).astype("float64")
    return float(abs(conf.mean() - hit.mean()))
