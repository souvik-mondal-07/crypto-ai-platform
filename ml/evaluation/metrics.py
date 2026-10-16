"""Prediction-accuracy metrics. All inputs are MATCHED outcomes only.

Definitions (r = actual return, p = predicted return, n = matched sample size)
-----------------------------------------------------------------------------
directional_accuracy  hits / directional_sample_size, where a hit is predicted ``up`` & r > 0 or
                      predicted ``down`` & r < 0. Predictions the model itself labelled ``flat`` make no
                      directional claim and are EXCLUDED (counted in ``flat_predictions_excluded``).
                      An up/down call whose actual return is exactly 0 is a miss.
mae                   mean(|p - r|)                      same units as returns (0.01 == 1 percentage point)
rmse                  sqrt(mean((p - r)^2))              penalises large misses more than MAE
mean_error (bias)     mean(p - r)                        positive => the model over-predicts on average
baseline_zero_mae     mean(|r|), the MAE of always predicting 0 — a model is only informative when
                      its MAE is below this; ``mae_vs_zero_baseline`` = mae / baseline_zero_mae
range_coverage        share of outcomes inside the stored prediction range (inclusive), over records
                      that carry a valid range; return range preferred, price range otherwise.
                      Compare with ``nominal_coverage`` (the coverage the range was designed for).

Deliberately NOT computed: MAPE (undefined/unstable when returns are 0 or near 0) and R² (not meaningful
for return forecasts with a near-zero mean and heavy tails).

Fewer than ``min_samples`` matched outcomes => ``status == "insufficient_data"`` and every metric is None
(the sample size and period are still reported). Nothing is ever defaulted to 0.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import fmean
from typing import Any, Callable, Iterable, Optional

from ml.evaluation.constants import MIN_SAMPLE_SIZE
from ml.evaluation.matching import Outcome

INSUFFICIENT_MESSAGE = "Insufficient historical predictions to calculate reliable accuracy metrics."


def _range_hit(o: Outcome) -> Optional[bool]:
    r = o.record
    if r.return_lower is not None and r.return_upper is not None and r.return_lower <= r.return_upper:
        return r.return_lower <= o.actual_return <= r.return_upper  # type: ignore[operator]
    if r.price_lower is not None and r.price_upper is not None and 0 < r.price_lower <= r.price_upper:
        return r.price_lower <= o.actual_price <= r.price_upper  # type: ignore[operator]
    return None


def accuracy_metrics(outcomes: Iterable[Outcome], min_samples: int = MIN_SAMPLE_SIZE) -> dict[str, Any]:
    """Aggregate metrics for a set of outcomes (non-matched ones are ignored, not counted as wrong)."""
    matched = [o for o in outcomes if o.matched and o.actual_return is not None and o.record.predicted_return is not None]
    n = len(matched)
    times = [o.target_time for o in matched if o.target_time is not None]
    out: dict[str, Any] = {
        "status": "ok" if n >= min_samples else ("no_data" if n == 0 else "insufficient_data"),
        "sample_size": n,
        "min_samples": min_samples,
        "period_start": min(times) if times else None,
        "period_end": max(times) if times else None,
        "directional_accuracy": None, "directional_sample_size": 0, "flat_predictions_excluded": 0,
        "mae": None, "rmse": None, "mean_error": None, "baseline_zero_mae": None, "mae_vs_zero_baseline": None,
        "mean_predicted_return": None, "mean_actual_return": None,
        "range_coverage": None, "range_sample_size": 0, "nominal_coverage": None,
        "message": None,
    }
    if n < min_samples:
        out["message"] = INSUFFICIENT_MESSAGE if n else "No matured predictions have been matched to market outcomes yet."
        return out

    errors = [o.record.predicted_return - o.actual_return for o in matched]  # type: ignore[operator]
    out["mae"] = fmean(abs(e) for e in errors)
    out["rmse"] = math.sqrt(fmean(e * e for e in errors))
    out["mean_error"] = fmean(errors)
    baseline = fmean(abs(o.actual_return) for o in matched)  # type: ignore[arg-type]
    out["baseline_zero_mae"] = baseline
    out["mae_vs_zero_baseline"] = out["mae"] / baseline if baseline > 0 else None
    out["mean_predicted_return"] = fmean(o.record.predicted_return for o in matched)  # type: ignore[misc]
    out["mean_actual_return"] = fmean(o.actual_return for o in matched)  # type: ignore[misc]

    directional = [o for o in matched if o.record.direction in ("up", "down")]
    out["flat_predictions_excluded"] = n - len(directional)
    out["directional_sample_size"] = len(directional)
    if directional:
        hits = sum(1 for o in directional if o.record.direction == o.actual_direction)
        out["directional_accuracy"] = hits / len(directional)

    hits_by_range = [h for h in (_range_hit(o) for o in matched) if h is not None]
    out["range_sample_size"] = len(hits_by_range)
    if hits_by_range:
        out["range_coverage"] = sum(hits_by_range) / len(hits_by_range)
        noms = [o.record.nominal_coverage for o in matched if o.record.nominal_coverage is not None]
        out["nominal_coverage"] = fmean(noms) if noms else None
    return out


def group_metrics(
    outcomes: Iterable[Outcome], key: Callable[[Outcome], Any], min_samples: int = MIN_SAMPLE_SIZE
) -> list[dict[str, Any]]:
    """Metrics per group (e.g. coin, horizon, model+version). Groups are returned in a stable order."""
    groups: dict[Any, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        groups[key(o)].append(o)
    rows = []
    for k in sorted(groups, key=lambda x: tuple(str(p) for p in (x if isinstance(x, tuple) else (x,)))):
        rows.append({"key": k, **accuracy_metrics(groups[k], min_samples)})
    return rows


def outcome_status_counts(outcomes: Iterable[Outcome]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for o in outcomes:
        counts[o.status] += 1
    return dict(counts)
