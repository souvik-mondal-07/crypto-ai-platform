"""Common interface + shared preprocessing/persistence helpers for prediction models.

Every model predicts the *future return* over one horizon from engineered
features. The prediction pipeline only talks to this interface, so models can be
swapped or added without touching it.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.training.evaluation import regression_metrics


class ModelDependencyError(RuntimeError):
    """An optional library (xgboost / lightgbm / torch) is not installed."""


class ModelNotFittedError(RuntimeError):
    pass


class Preprocessor:
    """Median imputation + standardisation, fitted on TRAINING rows only and stored as JSON."""

    def __init__(self) -> None:
        self.columns: list[str] = []
        self.median: list[float] = []
        self.mean: list[float] = []
        self.scale: list[float] = []

    @property
    def fitted(self) -> bool:
        return bool(self.columns)

    def fit(self, X: pd.DataFrame) -> "Preprocessor":
        self.columns = list(X.columns)
        arr = X.to_numpy(dtype="float64")
        med = np.nanmedian(arr, axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        filled = np.where(np.isnan(arr), med, arr)
        mean = filled.mean(axis=0)
        std = filled.std(axis=0)
        std = np.where(std > 1e-12, std, 1.0)
        self.median, self.mean, self.scale = med.tolist(), mean.tolist(), std.tolist()
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise ModelNotFittedError("Preprocessor is not fitted.")
        missing = [c for c in self.columns if c not in X.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {missing[:5]}")
        arr = X[self.columns].to_numpy(dtype="float64")
        arr = np.where(np.isnan(arr), np.asarray(self.median), arr)
        return (arr - np.asarray(self.mean)) / np.asarray(self.scale)

    def to_dict(self) -> dict[str, Any]:
        return {"columns": self.columns, "median": self.median, "mean": self.mean, "scale": self.scale}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preprocessor":
        p = cls()
        p.columns, p.median, p.mean, p.scale = data["columns"], data["median"], data["mean"], data["scale"]
        return p


class BasePredictionModel(ABC):
    """fit / predict / evaluate / save / load for one (coin, horizon) model."""

    model_type: str = "base"
    #: Number of EARLIER rows a prediction needs as context (sequence models only).
    required_context: int = 0

    def __init__(self, params: Optional[dict[str, Any]] = None) -> None:
        self.params: dict[str, Any] = dict(params or {})
        self.feature_names: list[str] = []
        self.fitted = False

    # ---- interface ----
    @abstractmethod
    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "BasePredictionModel":
        """Train on the training segment. The validation segment may be used ONLY for
        early stopping — never for fitting scalers."""

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predicted future return per row. Sequence models return NaN for the first
        ``required_context`` rows (not enough history)."""

    @abstractmethod
    def _save_impl(self, directory: Path) -> None: ...

    @abstractmethod
    def _load_impl(self, directory: Path) -> None: ...

    def feature_importance(self) -> dict[str, float]:
        """Normalised importance per feature; empty if the model type has none."""
        return {}

    # ---- shared ----
    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Optional[float]]:
        preds = self.predict(X)
        return regression_metrics(np.asarray(y, dtype="float64"), preds)

    def _check_fitted(self) -> None:
        if not self.fitted:
            raise ModelNotFittedError(f"{self.model_type} model is not fitted.")

    def _check_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        if X.empty:
            raise ValueError("Cannot predict on an empty frame.")
        missing = [c for c in self.feature_names if c not in X.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {missing[:5]}")
        return X[self.feature_names]

    def save(self, directory: Path | str) -> Path:
        self._check_fitted()
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        self._save_impl(d)
        (d / "model_meta.json").write_text(
            json.dumps({"model_type": self.model_type, "feature_names": self.feature_names, "params": _jsonable(self.params)}, indent=2)
        )
        return d

    @classmethod
    def load(cls, directory: Path | str) -> "BasePredictionModel":
        d = Path(directory)
        meta_path = d / "model_meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(f"No model_meta.json in {d}")
        meta = json.loads(meta_path.read_text())
        if meta.get("model_type") != cls.model_type:
            raise ValueError(f"Artifact is a {meta.get('model_type')!r} model, not {cls.model_type!r}")
        model = cls(meta.get("params"))
        model.feature_names = list(meta["feature_names"])
        model._load_impl(d)
        model.fitted = True
        return model


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    return obj
