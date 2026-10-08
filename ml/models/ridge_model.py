"""Ridge regression baseline.

Not one of the headline models, but it serves three real purposes: a linear
benchmark every tree/sequence model must beat, a dependency-light fallback that
needs only scikit-learn, and JSON-only persistence (no pickle).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ml.models.base_model import BasePredictionModel, Preprocessor


class RidgeBaselineModel(BasePredictionModel):
    model_type = "ridge"

    def __init__(self, params=None):
        super().__init__(params)
        self.pre = Preprocessor()
        self.coef: np.ndarray = np.array([])
        self.intercept: float = 0.0

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        from sklearn.linear_model import Ridge

        if len(X_train) != len(y_train):
            raise ValueError("X_train and y_train must have the same length.")
        if len(X_train) < 10:
            raise ValueError("Too few training rows.")
        self.feature_names = list(X_train.columns)
        self.pre.fit(X_train)
        model = Ridge(alpha=float(self.params.get("alpha", 10.0)))
        model.fit(self.pre.transform(X_train), np.asarray(y_train, dtype="float64"))
        self.coef, self.intercept = model.coef_.astype("float64"), float(model.intercept_)
        self.fitted = True
        return self

    def predict(self, X):
        self._check_fitted()
        Z = self.pre.transform(self._check_columns(X))
        return Z @ self.coef + self.intercept

    def feature_importance(self):
        if not self.fitted:
            return {}
        mag = np.abs(self.coef)
        total = mag.sum()
        return {n: float(m / total) if total > 0 else 0.0 for n, m in zip(self.feature_names, mag)}

    def _save_impl(self, directory: Path) -> None:
        (directory / "ridge.json").write_text(
            json.dumps({"coef": self.coef.tolist(), "intercept": self.intercept, "preprocessor": self.pre.to_dict()})
        )

    def _load_impl(self, directory: Path) -> None:
        data = json.loads((directory / "ridge.json").read_text())
        self.coef, self.intercept = np.asarray(data["coef"]), float(data["intercept"])
        self.pre = Preprocessor.from_dict(data["preprocessor"])
