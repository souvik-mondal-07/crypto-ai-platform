"""Optional ensemble of already-trained, already-validated models.

Only models that exist, passed the activation gate and have finite validation
metrics are combined. Weights are either supplied by configuration or derived from
validated performance (inverse validation MAE) — never made up.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.models.base_model import BasePredictionModel


def weights_from_validation_mae(maes: dict[str, float]) -> dict[str, float]:
    """Inverse-MAE weights, normalised to 1. Models without a finite positive MAE are excluded."""
    usable = {k: v for k, v in maes.items() if v is not None and np.isfinite(v) and v > 0}
    if not usable:
        return {}
    inv = {k: 1.0 / v for k, v in usable.items()}
    total = sum(inv.values())
    return {k: v / total for k, v in inv.items()}


def normalise_config_weights(weights: dict[str, float], available: list[str]) -> dict[str, float]:
    """Configured weights restricted to models that actually exist, renormalised."""
    chosen = {k: float(w) for k, w in weights.items() if k in available and w and w > 0}
    total = sum(chosen.values())
    return {k: v / total for k, v in chosen.items()} if total > 0 else {}


class EnsembleModel(BasePredictionModel):
    model_type = "ensemble"

    def __init__(self, params: Optional[dict[str, Any]] = None):
        super().__init__(params)
        self.members: list[tuple[str, str, float, BasePredictionModel]] = []  # (type, version, weight, model)
        self._member_paths: list[str] = []

    @classmethod
    def from_members(
        cls, members: list[tuple[str, str, float, BasePredictionModel, str]]
    ) -> "EnsembleModel":
        """``members``: (model_type, version, weight, fitted model, path relative to the ensemble dir)."""
        if len(members) < 2:
            raise ValueError("An ensemble needs at least two validated models.")
        total = sum(m[2] for m in members)
        if total <= 0:
            raise ValueError("Ensemble weights must sum to a positive number.")
        feats = members[0][3].feature_names
        if any(m[3].feature_names != feats for m in members):
            raise ValueError("Ensemble members must share the same feature set.")
        ens = cls()
        ens.members = [(t, v, w / total, m) for t, v, w, m, _ in members]
        ens._member_paths = [p for *_, p in members]
        ens.feature_names = list(feats)
        ens.required_context = max(m[3].required_context for m in members)
        ens.fitted = True
        return ens

    def fit(self, *args, **kwargs):  # pragma: no cover - ensembles are assembled, not fitted
        raise NotImplementedError("Ensembles are assembled from trained members via from_members().")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        self._check_fitted()
        out = np.zeros(len(X), dtype="float64")
        for _, _, weight, model in self.members:
            out += weight * model.predict(X)  # NaN from any member propagates (never silently dropped)
        return out

    def feature_importance(self) -> dict[str, float]:
        agg: dict[str, float] = {}
        for _, _, weight, model in self.members:
            for k, v in model.feature_importance().items():
                agg[k] = agg.get(k, 0.0) + weight * v
        return agg

    def _save_impl(self, directory: Path) -> None:
        (directory / "ensemble.json").write_text(json.dumps({
            "members": [
                {"model_type": t, "version": v, "weight": w, "path": p}
                for (t, v, w, _), p in zip(self.members, self._member_paths)
            ]
        }, indent=2))

    def _load_impl(self, directory: Path) -> None:
        from ml.models.model_registry import MODEL_CLASSES

        spec = json.loads((directory / "ensemble.json").read_text())
        root = directory.resolve()
        members = []
        for entry in spec["members"]:
            mdir = (root / entry["path"]).resolve()
            # member dirs must live next to the ensemble dir, inside the same artifact tree
            if not mdir.is_relative_to(root.parents[2]):
                raise ValueError("Ensemble member path escapes the artifact tree.")
            members.append((entry["model_type"], entry["version"], float(entry["weight"]),
                            MODEL_CLASSES[entry["model_type"]].load(mdir)))
        self.members = members
        self.required_context = max(m[3].required_context for m in members)
