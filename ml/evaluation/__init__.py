"""Backtesting & model-accuracy evaluation (Phase 17).

Pure-Python (standard library only) so it is deterministic, cheap to test and importable
without numpy/pandas. Nothing in here fabricates data: every function works on records and
candles handed to it, and returns an explicit status (``insufficient_data``, ``not_matured`` ...)
whenever an honest number cannot be produced.

Modules
-------
constants       versions, horizons, tolerances, thresholds
timestamps      timezone / format normalisation
series          validated, de-duplicated candle series with point-in-time lookups
matching        prediction -> actual outcome matching
metrics         accuracy metrics (directional accuracy, MAE, RMSE, range coverage, ...)
decision_eval   BUY/HOLD/SELL evaluation against subsequent returns
backtest        chronological, cost-aware strategy simulation
backtest_metrics equity-curve statistics (drawdown, annualised return, Sharpe, ...)
"""

from ml.evaluation.constants import BACKTEST_ENGINE_VERSION, METHODOLOGY_VERSION

__all__ = ["BACKTEST_ENGINE_VERSION", "METHODOLOGY_VERSION"]
