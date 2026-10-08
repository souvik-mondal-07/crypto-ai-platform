"""Assembles + registers an ensemble from already-trained, validated members."""

from __future__ import annotations

from typing import Optional

import numpy as np

from ml.config.model_config import MLConfig
from ml.data.dataset_builder import Dataset
from ml.models.model_registry import STATUS_ACTIVE, ModelRegistry
from ml.prediction.ensemble import EnsembleModel, normalise_config_weights, weights_from_validation_mae
from ml.training.trainer import TrainResult, finalize_model


def train_ensemble(
    results: list[TrainResult], dataset: Dataset, config: MLConfig, registry: ModelRegistry,
    *, coin_id: str, symbol: Optional[str] = None,
) -> Optional[TrainResult]:
    """Combine the members that exist AND passed the activation gate AND have finite
    validation metrics. Returns None when fewer than two qualify (no fabricated ensemble)."""
    members = [
        r for r in results
        if r.record.status == STATUS_ACTIVE and (r.record.metrics.get("validation") or {}).get("mae")
    ]
    if len(members) < 2:
        return None
    by_type = {r.record.model_type: r for r in members}
    if config.ensemble_weights:
        weights = normalise_config_weights(config.ensemble_weights, list(by_type))
        source = "configured"
    else:
        weights = weights_from_validation_mae({t: r.record.metrics["validation"]["mae"] for t, r in by_type.items()})
        source = "inverse_validation_mae"
    members = [by_type[t] for t in weights if t in by_type]
    if len(members) < 2:
        return None

    split = dataset.split(config)
    ens = EnsembleModel.from_members([
        (r.record.model_type, r.record.version, weights[r.record.model_type], r.model,
         f"../../{r.record.model_type}/{r.record.version}")
        for r in members
    ])
    val_pred = sum(weights[r.record.model_type] * r.val_pred for r in members)
    test_pred = sum(weights[r.record.model_type] * r.test_pred for r in members)
    return finalize_model(
        ens, dataset, split, config, registry, coin_id=coin_id, symbol=symbol,
        val_pred=np.asarray(val_pred), test_pred=np.asarray(test_pred),
        member_paths=[f"../../{r.record.model_type}/{r.record.version}" for r in members],
        extra_info={"ensemble_weights": weights, "ensemble_weight_source": source,
                    "ensemble_members": [f"{r.record.model_type}:{r.record.version}" for r in members]},
    )
