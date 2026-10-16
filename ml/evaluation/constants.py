"""Versions, horizons and thresholds for Phase 17. Change a rule => bump the matching version."""

from __future__ import annotations

#: Version of the prediction/decision *evaluation* methodology (matching rules + metric definitions).
#: Stored on every evaluated record so results from different methodologies are never mixed.
METHODOLOGY_VERSION = "1.0.0"
#: Version of the backtest simulation engine (execution rules, cost model, statistics).
BACKTEST_ENGINE_VERSION = "1.0.0"
#: Name of the only strategy currently supported: act on the stored Phase 14 decisions.
STRATEGY_PHASE14 = "phase14_decisions"
STRATEGY_VERSION = "1.0.0"

#: Horizon name -> seconds. Mirrors ``ml.config.model_config.HORIZONS`` (a test asserts they agree).
HORIZON_SECONDS: dict[str, int] = {"1h": 3600, "4h": 14400, "24h": 86400, "7d": 604800, "30d": 2592000}
#: Candle interval used to look up the ACTUAL price for a horizon (same grid the model used).
HORIZON_INTERVAL: dict[str, str] = {"1h": "1h", "4h": "1h", "24h": "1h", "7d": "4h", "30d": "1d"}
INTERVAL_SECONDS: dict[str, int] = {"1h": 3600, "4h": 14400, "1d": 86400}
SUPPORTED_HORIZONS = tuple(HORIZON_SECONDS)

#: Horizons used to evaluate BUY/HOLD/SELL decisions. Decisions are multi-day views, so sub-day
#: horizons are not evaluated.
DECISION_HORIZONS = ("24h", "7d", "30d")

#: Matching tolerance = this fraction of the candle interval. Prediction targets sit exactly on the
#: exchange candle-close grid, so a half-interval tolerance can only ever pick the intended candle.
MATCH_TOLERANCE_FRACTION = 0.5
#: A reference price derived from candles must come from a candle that closed within this many
#: intervals before the decision time, otherwise it is treated as stale.
REFERENCE_MAX_AGE_INTERVALS = 1.5

#: Below this many matured, matched samples, metrics are reported as ``insufficient_data``.
MIN_SAMPLE_SIZE = 30
#: Minimum samples for a (decision type, horizon) cell of the decision evaluation.
MIN_DECISION_SAMPLE_SIZE = 20

#: HOLD is "neutral" when |forward return| is within this band (fraction). An explicit, documented
#: assumption used only for the ``within_neutral_band_rate`` — never labelled "success".
HOLD_NEUTRAL_BAND: dict[str, float] = {"24h": 0.02, "7d": 0.05, "30d": 0.10}

#: Annualised return / Sharpe are only reported for periods at least this long.
MIN_DAYS_FOR_ANNUALISATION = 30
MIN_RETURN_OBSERVATIONS_FOR_SHARPE = 30
