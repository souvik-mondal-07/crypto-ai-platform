"""LightGBM regressor — same interface as XGBoost so they are interchangeable."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.models.base_model import BasePredictionModel, ModelDependencyError


def _lgb():
    try:
        import lightgbm  # type: ignore
    except ImportError as exc:
        raise ModelDependencyError("lightgbm is not installed (pip install lightgbm).") from exc
    return lightgbm


class LightGBMModel(BasePredictionModel):
    model_type = "lightgbm"

    def __init__(self, params=None):
        super().__init__(params)
        self._model = None

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        lgb = _lgb()
        if len(X_train) != len(y_train):
            raise ValueError("X_train and y_train must have the same length.")
        if len(X_train) < 50:
            raise ValueError("Too few training rows for LightGBM.")
        params = dict(self.params)
        early = params.pop("early_stopping_rounds", None)
        self.feature_names = list(X_train.columns)
        model = lgb.LGBMRegressor(objective="regression", **params)
        kwargs = {}
        if X_val is not None and y_val is not None and len(X_val) > 0 and early:
            kwargs["eval_set"] = [(X_val[self.feature_names], y_val)]
            kwargs["callbacks"] = [lgb.early_stopping(int(early), verbose=False)]
        model.fit(X_train, y_train, **kwargs)
        self._model = model
        self.fitted = True
        return self

    def predict(self, X):
        self._check_fitted()
        return np.asarray(self._model.predict(self._check_columns(X)), dtype="float64")

    def feature_importance(self):
        if not self.fitted:
            return {}
        imp = np.asarray(self._model.booster_.feature_importance(importance_type="gain"), dtype="float64")
        total = imp.sum()
        return {n: float(v / total) if total > 0 else 0.0 for n, v in zip(self.feature_names, imp)}

    def _save_impl(self, directory: Path) -> None:
        self._model.booster_.save_model(str(directory / "model.txt"))  # LightGBM text format, no pickle

    def _load_impl(self, directory: Path) -> None:
        lgb = _lgb()
        booster = lgb.Booster(model_file=str(directory / "model.txt"))
        self._model = _BoosterRegressor(booster)
        # `feature_importance` / predict only need the booster on the load path.


class _BoosterRegressor:
    """Minimal adapter so a loaded Booster exposes the bits of LGBMRegressor we use."""

    def __init__(self, booster):
        self.booster_ = booster

    def predict(self, X):
        return self.booster_.predict(X)
