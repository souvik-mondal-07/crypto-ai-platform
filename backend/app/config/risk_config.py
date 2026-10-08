"""Risk & Decision Engine configuration (Phase 14).

EVERY weight, curve and threshold the engine uses lives in this file, so the
calculation is never hidden inside ad-hoc conditions. The engine itself
(`app/services/risk_service.py`, `app/services/decision_engine.py`) takes an
`EngineConfig` argument; tests and future backtests can pass a modified copy.

Nothing here is random and nothing is learned: the engine is a deterministic,
rule-based scoring system. Changing any number below changes the result, so
bump `DECISION_ENGINE_VERSION` / `RISK_CONFIG_VERSION` when you do — stored
decisions record both, which keeps old results comparable.

Conventions
-----------
* A *curve* is a tuple of `(input_value, output)` points, linearly interpolated
  and clamped at both ends (see `app/services/scoring.py::piecewise`).
* Risk sub-scores are 0-100 where HIGHER = RISKIER.
* Directional (decision) sub-scores are -100..+100 where POSITIVE = bullish.
"""

from dataclasses import dataclass, field
from typing import Mapping

DECISION_ENGINE_VERSION = "1.0"
RISK_CONFIG_VERSION = "1.0"

Curve = tuple[tuple[float, float], ...]

# ---------------------------------------------------------------------------
# Enumerations (string constants — stored in MongoDB and sent to the frontend)
# ---------------------------------------------------------------------------

RISK_VERY_LOW = "VERY_LOW"
RISK_LOW = "LOW"
RISK_MODERATE = "MODERATE"
RISK_HIGH = "HIGH"
RISK_VERY_HIGH = "VERY_HIGH"

DECISION_BUY = "BUY"
DECISION_HOLD = "HOLD"
DECISION_SELL = "SELL"

STATUS_VALID = "VALID"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_STALE_DATA = "STALE_DATA"
STATUS_PREDICTION_UNAVAILABLE = "PREDICTION_UNAVAILABLE"
STATUS_ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"

# Per-input availability states (see DataQuality in the decision response).
STATE_AVAILABLE = "available"
STATE_MISSING = "missing"                  # nothing stored / not generated yet
STATE_STALE = "stale"                      # exists but too old to use
STATE_INSUFFICIENT = "insufficient_data"   # exists but too little real data behind it
STATE_UNAVAILABLE = "unavailable"          # upstream failure / model not available

MODULES = ("technical", "fundamental", "sentiment", "prediction")


# ---------------------------------------------------------------------------
# Risk configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskConfig:
    #: Weight of each risk component in the final 0-100 risk score. Components
    #: whose data is unavailable are EXCLUDED and the remaining weights are
    #: re-normalised — a missing input is never assumed to be "low risk".
    component_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "volatility": 0.25,
            "liquidity": 0.15,
            "technical": 0.20,
            "fundamental": 0.15,
            "sentiment": 0.10,
            "prediction": 0.15,
        }
    )

    #: Minimum share of the total component weight that must be backed by real
    #: data for a risk score to be produced at all.
    min_coverage: float = 0.5
    #: Components that must be available (a risk score without market-derived
    #: volatility or liquidity evidence would be meaningless).
    required_any_of: tuple[str, ...] = ("volatility", "liquidity")
    #: Risk is always measured against the current price/volume, so without usable
    #: (present and fresh) market data no risk score is produced at all.
    require_market: bool = True

    #: Upper bound (inclusive) of each risk level on the 0-100 scale.
    level_bounds: tuple[tuple[str, float], ...] = (
        (RISK_VERY_LOW, 20.0),
        (RISK_LOW, 40.0),
        (RISK_MODERATE, 60.0),
        (RISK_HIGH, 80.0),
        (RISK_VERY_HIGH, 100.0),
    )

    #: Sub-factor weights INSIDE each component (re-normalised over available ones).
    sub_weights: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: {
            "volatility": {"atr_pct": 0.40, "bollinger_width_pct": 0.30, "range_24h_pct": 0.30},
            "liquidity": {"volume_24h_usd": 0.40, "market_cap_usd": 0.35, "volume_to_market_cap": 0.25},
            "technical": {"rsi": 0.20, "macd": 0.20, "trend": 0.25, "bollinger_position": 0.20, "support_resistance": 0.15},
            "fundamental": {"fundamental_score": 0.30, "market_rank": 0.25, "market_cap_to_fdv": 0.15,
                            "supply": 0.10, "ath_drawdown": 0.10, "data_completeness": 0.10},
            "sentiment": {"average_score": 0.40, "negative_share": 0.25, "trend": 0.20, "news_volume": 0.15},
            "prediction": {"direction": 0.35, "range_width": 0.30, "model_confidence": 0.35},
        }
    )

    # ---- curves: input -> risk sub-score (0-100, higher = riskier) ---------

    # Volatility. ATR% = ATR / price * 100 per candle of the analysis timeframe (30D => 4h candles).
    atr_pct_curve: Curve = ((0.5, 5), (1.0, 15), (2.0, 35), (3.5, 55), (5.0, 72), (8.0, 90), (15.0, 100))
    # Bollinger width% = (upper - lower) / middle * 100 (a 2-sigma, 20-candle historical-volatility measure).
    bollinger_width_curve: Curve = ((2.0, 5), (5.0, 20), (10.0, 40), (18.0, 60), (30.0, 80), (50.0, 95))
    # 24h range% = (high_24h - low_24h) / price * 100.
    range_24h_curve: Curve = ((1.0, 5), (3.0, 25), (6.0, 50), (10.0, 72), (20.0, 90), (40.0, 100))

    # Liquidity.
    volume_24h_curve: Curve = ((1e5, 95), (1e6, 80), (1e7, 55), (1e8, 28), (1e9, 10), (1e10, 3))
    market_cap_curve: Curve = ((1e7, 95), (1e8, 75), (1e9, 45), (1e10, 20), (1e11, 5), (1e12, 2))
    # volume / market cap — both too thin AND abnormally high turnover are risky.
    volume_to_mcap_curve: Curve = ((0.0, 90), (0.005, 80), (0.02, 50), (0.05, 25), (0.15, 15), (0.4, 40), (1.0, 70), (3.0, 90))

    # Technical.
    rsi_risk_curve: Curve = ((0, 75), (20, 62), (30, 40), (45, 15), (55, 15), (70, 40), (80, 62), (100, 78))
    trend_risk: Mapping[str, float] = field(default_factory=lambda: {"bullish": 20.0, "neutral": 45.0, "bearish": 75.0})
    macd_risk: Mapping[str, float] = field(
        default_factory=lambda: {"bullish_crossover": 15.0, "hist_positive": 28.0, "hist_negative": 58.0, "bearish_crossover": 72.0}
    )
    # Bollinger %B = (price - lower) / (upper - lower).
    bollinger_position_risk_curve: Curve = ((-0.2, 82), (0.0, 66), (0.2, 36), (0.5, 20), (0.8, 36), (1.0, 66), (1.2, 82))
    # share_down = downside_to_support / (downside_to_support + upside_to_resistance).
    sr_risk_curve: Curve = ((0.0, 25), (0.5, 45), (1.0, 72))

    # Fundamental. (market rank: 1 is best.)
    rank_risk_curve: Curve = ((1, 4), (10, 10), (50, 20), (200, 40), (1000, 65), (5000, 85), (20000, 95))
    # market cap / FDV — low = large share of supply still locked/unissued.
    mcap_to_fdv_risk_curve: Curve = ((0.1, 85), (0.3, 70), (0.5, 50), (0.8, 25), (1.0, 10))
    # circulating / max supply % (only for capped supplies).
    supply_circulating_risk_curve: Curve = ((5, 80), (20, 70), (50, 45), (80, 25), (100, 10))
    # Magnitude of the drawdown from ATH, in % (0 = at ATH).
    ath_drawdown_risk_curve: Curve = ((0, 45), (10, 35), (30, 30), (60, 50), (80, 70), (95, 88))

    # Sentiment. average_score in [-1, 1].
    sentiment_score_risk_curve: Curve = ((-1.0, 88), (-0.3, 66), (0.0, 45), (0.3, 28), (1.0, 15))
    sentiment_negative_pct_risk_curve: Curve = ((0, 15), (20, 25), (40, 50), (60, 75), (100, 92))
    sentiment_trend_risk: Mapping[str, float] = field(
        default_factory=lambda: {"declining": 70.0, "stable": 40.0, "improving": 25.0}
    )
    # Few analysed articles = thin evidence = more risk.
    news_volume_risk_curve: Curve = ((3, 60), (10, 45), (25, 35), (60, 35))

    # Prediction uncertainty.
    prediction_direction_risk: Mapping[str, float] = field(default_factory=lambda: {"up": 25.0, "flat": 50.0, "down": 75.0})
    # Width of the predicted RETURN range (fraction: 0.03 == 3 percentage points).
    prediction_range_width_curve: Curve = ((0.0, 10), (0.01, 25), (0.03, 50), (0.06, 75), (0.12, 90))
    # Calibrated probability the predicted direction is right.
    prediction_confidence_risk_curve: Curve = ((0.5, 78), (0.6, 50), (0.7, 30), (0.85, 10))

    #: A sub-score at or above this is surfaced as a NEGATIVE (risk) factor;
    #: at or below `low_risk_factor_at_or_below` as a POSITIVE factor.
    high_risk_factor_at_or_above: float = 65.0
    low_risk_factor_at_or_below: float = 25.0


# ---------------------------------------------------------------------------
# Decision configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionConfig:
    #: Weight of each directional module in the combined score (re-normalised
    #: over the modules that are actually usable).
    module_weights: Mapping[str, float] = field(
        default_factory=lambda: {"technical": 0.35, "fundamental": 0.20, "sentiment": 0.15, "prediction": 0.30}
    )

    #: Weights of the components INSIDE the technical / fundamental / sentiment scores.
    technical_weights: Mapping[str, float] = field(
        default_factory=lambda: {"trend": 0.25, "macd": 0.20, "rsi": 0.15, "moving_averages": 0.20,
                                 "bollinger": 0.10, "support_resistance": 0.10}
    )
    fundamental_weights: Mapping[str, float] = field(
        default_factory=lambda: {"fundamental_score": 0.55, "market_rank": 0.25, "market_cap_to_fdv": 0.20}
    )
    sentiment_weights: Mapping[str, float] = field(
        default_factory=lambda: {"average_score": 0.60, "label_balance": 0.20, "trend": 0.20}
    )

    # ---- curves: input -> directional sub-score (-100..+100) ----------------
    trend_score: Mapping[str, float] = field(default_factory=lambda: {"bullish": 60.0, "neutral": 0.0, "bearish": -60.0})
    macd_score: Mapping[str, float] = field(
        default_factory=lambda: {"bullish_crossover": 70.0, "hist_positive": 40.0, "hist_negative": -40.0, "bearish_crossover": -70.0}
    )
    # RSI: strength above 50 is bullish, but extreme readings are stretched (mean-reversion risk).
    rsi_score_curve: Curve = ((0, 20), (25, 15), (35, -25), (45, -10), (50, 0), (60, 30), (68, 35), (75, 0), (85, -35), (100, -45))
    #: Score for ONE moving average when price is above (+) / below (-) it.
    moving_average_step: float = 60.0
    #: %B <= 0 / >= 1 are "stretched" readings; linear in between.
    bollinger_score_curve: Curve = ((0.0, 20), (0.5, 0), (1.0, -30))
    # share_down as in the risk engine; near support (0) = favourable, near resistance (1) = unfavourable.
    support_resistance_score_curve: Curve = ((0.0, 40), (0.5, 0), (1.0, -40))

    rank_score_curve: Curve = ((1, 70), (20, 50), (100, 20), (500, -10), (2000, -40), (10000, -70))
    mcap_to_fdv_score_curve: Curve = ((0.2, -50), (0.5, -15), (0.8, 15), (1.0, 30))

    sentiment_trend_score: Mapping[str, float] = field(
        default_factory=lambda: {"improving": 40.0, "stable": 0.0, "declining": -40.0}
    )
    #: Sentiment weight is scaled by min(1, analysed_articles / this).
    sentiment_full_reliability_articles: int = 10

    prediction_return_score_curve: Curve = (
        (-0.06, -100), (-0.03, -70), (-0.01, -35), (0.0, 0), (0.01, 35), (0.03, 70), (0.06, 100)
    )
    #: Direction-confidence p -> factor in [0, 1]: 0 at/below chance (0.5), 1 at or above `full_at`.
    prediction_confidence_full_at: float = 0.75
    #: Applied when the model's confidence is "unavailable" (not calibrated).
    #: Documented meaning: the prediction still counts, at HALF strength.
    prediction_uncalibrated_factor: float = 0.5
    #: Applied when the predicted return range straddles zero (direction not established).
    prediction_range_straddles_zero_factor: float = 0.5
    #: A stored prediction older than this (seconds since generation) is excluded as stale.
    prediction_max_age_seconds: int = 4 * 3600
    #: The prediction is OPTIONAL: when unavailable the decision is made from the
    #: remaining modules (weights re-normalised, confidence reduced). Set True to
    #: return status PREDICTION_UNAVAILABLE (and no decision) instead.
    prediction_required: bool = False

    # ---- signal labels -------------------------------------------------------
    #: |module score| at or above this is a directional label (BULLISH/BEARISH, POSITIVE/NEGATIVE, STRONG/WEAK).
    signal_label_threshold: float = 20.0
    fundamental_label_threshold: float = 25.0
    #: A component contributes a factor sentence when |score| is at least this.
    factor_component_threshold: float = 25.0

    # ---- decision thresholds & risk adjustment -------------------------------
    buy_threshold: float = 25.0
    sell_threshold: float = -25.0
    #: Bullish conviction is dampened as risk rises: risk score -> multiplier lost (0..1).
    #: (Bearish scores are never dampened — high risk should make SELL easier, not harder.)
    risk_dampening_curve: Curve = ((0, 0.0), (40, 0.0), (60, 0.15), (80, 0.35), (100, 0.55))

    # ---- overrides ------------------------------------------------------------
    #: Minimum final score for BUY at the given risk level (default `buy_threshold`).
    buy_min_score_by_risk_level: Mapping[str, float] = field(
        default_factory=lambda: {RISK_HIGH: 35.0, RISK_VERY_HIGH: 55.0}
    )
    #: Maximum final score for SELL at the given risk level (default `sell_threshold`) —
    #: at elevated risk a milder negative reading is enough to exit.
    sell_max_score_by_risk_level: Mapping[str, float] = field(
        default_factory=lambda: {RISK_HIGH: -20.0, RISK_VERY_HIGH: -15.0}
    )
    #: Conflict override: when the modules disagree (conflict share >= this) and the
    #: final score is weaker than `conflict_hold_below_abs`, the decision is HOLD.
    conflict_share_threshold: float = 0.25
    conflict_hold_below_abs: float = 45.0
    #: A BUY/SELL needs at least this decision confidence (0-100), otherwise HOLD.
    min_confidence_for_action: float = 40.0

    # ---- confidence -------------------------------------------------------------
    #: Weights of the confidence ingredients (re-normalised over the ones available).
    confidence_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "cross_module_agreement": 0.40,
            "intra_module_agreement": 0.15,
            "data_coverage": 0.20,
            "sentiment_reliability": 0.10,
            "model_confidence": 0.15,
        }
    )
    #: Points subtracted when the modules clearly conflict.
    conflict_confidence_penalty: float = 10.0
    #: Points subtracted from the confidence of a BULLISH reading (final score > 0)
    #: at elevated risk — a bullish call made under high risk deserves less trust.
    confidence_risk_penalty_by_level: Mapping[str, float] = field(
        default_factory=lambda: {RISK_HIGH: 5.0, RISK_VERY_HIGH: 12.0}
    )
    #: |score| below this is "no stated direction" when measuring signal agreement.
    agreement_sign_threshold: float = 10.0
    #: Minimum number of usable directional modules for ANY decision / confidence.
    min_usable_modules: int = 2

    # ---- data freshness -----------------------------------------------------------
    #: Technical snapshots older than this are treated as stale (the technical
    #: service recomputes after 300s, so this is only hit on a failed refresh).
    technical_max_age_seconds: int = 1800
    #: Lifetime of a generated decision (`expires_at`), and of the stored-result cache.
    decision_ttl_seconds: int = 300
    #: Lifetime of a NON-valid result (insufficient/stale/unavailable data). Short, so a
    #: transient provider failure is retried soon instead of being served for minutes.
    decision_failure_ttl_seconds: int = 60


@dataclass(frozen=True)
class EngineConfig:
    risk: RiskConfig = field(default_factory=RiskConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    engine_version: str = DECISION_ENGINE_VERSION
    risk_config_version: str = RISK_CONFIG_VERSION


DEFAULT_ENGINE_CONFIG = EngineConfig()
