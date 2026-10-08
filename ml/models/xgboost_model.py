"""XGBoost regressor on engineered tabular features (small, regularised, early-stopped)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.models.base_model import BasePredictionModel, ModelDependencyError


def _xgb():
    try:
        import xgboost  # type: ignore
    except ImportError as exc:
        raise ModelDependencyError("xgboost is not installed (pip install xgboost).") from exc
    return xgboost


class XGBoostModel(BasePredictionModel):
    model_type = "xgboost"

    def __init__(self, params=None):
        super().__init__(params)
        self._model = None

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        xgb = _xgb()
        if len(X_train) != len(y_train):
            raise ValueError("X_train and y_train must have the same length.")
        if len(X_train) < 50:
            raise ValueError("Too few training rows for XGBoost.")
        params = dict(self.params)
        early = params.pop("early_stopping_rounds", None)
        self.feature_names = list(X_train.columns)
        use_val = X_val is not None and y_val is not None and len(X_val) > 0 and early
        model = xgb.XGBRegressor(
            objective="reg:squarederror",
            tree_method="hist",
            **params,
            **({"early_stopping_rounds": int(early)} if use_val else {}),
        )
        if use_val:
            model.fit(X_train, y_train, eval_set=[(X_val[self.feature_names], y_val)], verbose=False)
        else:
            model.fit(X_train, y_train, verbose=False)
        self._model = model
        self.fitted = True
        return self

    def predict(self, X):
        self._check_fitted()
        return np.asarray(self._model.predict(self._check_columns(X)), dtype="float64")

    def feature_importance(self):
        if not self.fitted:
            return {}
        imp = np.asarray(self._model.feature_importances_, dtype="float64")
        total = imp.sum()
        return {n: float(v / total) if total > 0 else 0.0 for n, v in zip(self.feature_names, imp)}

    def _save_impl(self, directory: Path) -> None:
        self._model.save_model(str(directory / "model.json"))  # portable JSON, no pickle

    def _load_impl(self, directory: Path) -> None:
        xgb = _xgb()
        params = {k: v for k, v in self.params.items() if k != "early_stopping_rounds"}
        model = xgb.XGBRegressor(objective="reg:squarederror", tree_method="hist", **params)
        model.load_model(str(directory / "model.json"))
        self._model = model
