"""ML Prediction Engine (Phase 13).

Everything in here works on real historical market data and produces
probabilistic / range-based forecasts. Nothing in this package fabricates data:
when history or a validated model is missing, callers get an explicit
``insufficient_data`` / ``model_unavailable`` status instead of a number.

Heavy optional libraries (xgboost, lightgbm, torch) are imported lazily inside
the model classes that need them, so importing ``ml`` never requires them.
"""

from ml.config.feature_config import FEATURE_VERSION

__all__ = ["FEATURE_VERSION"]
