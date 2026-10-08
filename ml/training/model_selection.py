"""Activation gate: which trained models are allowed to serve predictions.

A model is judged ONLY on the untouched test segment. Crypto returns are close to
unpredictable at short horizons, so a model that cannot beat trivial baselines is
not activated — the API then reports ``model_unavailable`` instead of serving
numbers with no demonstrated skill.
"""

from __future__ import annotations

from typing import Any, Optional

from ml.config.model_config import MLConfig


def evaluate_gate(test_metrics: dict[str, Any], config: MLConfig) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    n = test_metrics.get("n") or 0
    if n < config.min_test_samples:
        reasons.append(f"only {n} test rows (need {config.min_test_samples})")
    mae, base = test_metrics.get("mae"), test_metrics.get("baseline_mae")
    if mae is None or base is None:
        reasons.append("MAE could not be computed")
    else:
        improvement = test_metrics.get("mae_improvement")
        if improvement is None or improvement <= config.min_mae_improvement:
            reasons.append(f"MAE does not beat the zero-return baseline (improvement {improvement})")
    if config.require_directional_edge:
        acc, naive = test_metrics.get("directional_accuracy"), test_metrics.get("naive_directional_accuracy")
        if acc is None or naive is None:
            reasons.append("directional accuracy could not be computed")
        elif acc <= max(0.5, naive):
            reasons.append(f"directional accuracy {acc:.3f} does not beat max(0.5, majority baseline {naive:.3f})")
    return (not reasons), reasons


def rank_models(records: list, prefer: Optional[str] = None) -> list:
    """Order active records: preferred type first, then by test MAE improvement (higher = better)."""
    def key(r):
        imp = (r.metrics.get("test") or {}).get("mae_improvement")
        return (0 if prefer and r.model_type == prefer else 1, -(imp if imp is not None else -1e9))
    return sorted(records, key=key)
