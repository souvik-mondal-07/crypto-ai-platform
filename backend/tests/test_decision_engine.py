"""Decision engine (Phase 14): BUY/HOLD/SELL scenarios, overrides, confidence, availability, determinism."""

from dataclasses import replace

import pytest

from app.config.risk_config import (
    DEFAULT_ENGINE_CONFIG,
    STATE_STALE,
    STATE_UNAVAILABLE,
    DecisionConfig,
    EngineConfig,
)
from app.services.decision_engine import evaluate
from app.services.decision_inputs import DecisionInputs
from tests.decision_fixtures import (
    bearish_inputs,
    bullish_inputs,
    risky_bullish_inputs,
    fundamental_strong,
    fundamental_weak,
    market,
    not_ok,
    prediction_down,
    prediction_up,
    sentiment_negative,
    sentiment_positive,
    technical_bearish,
    technical_bullish,
    without,
)

MODULES = ("technical", "fundamental", "sentiment", "prediction")


# ---- BUY / HOLD / SELL ----------------------------------------------------------------


def test_aligned_bullish_signals_with_moderate_risk_give_buy():
    r = evaluate(bullish_inputs())
    assert r.status == "VALID" and r.decision == "BUY"
    assert r.decision_score >= DEFAULT_ENGINE_CONFIG.decision.buy_threshold
    assert r.risk.level in ("VERY_LOW", "LOW", "MODERATE")
    assert r.signals == {"technical": "BULLISH", "fundamental": "STRONG", "sentiment": "POSITIVE",
                         "prediction": "BULLISH", "risk": r.risk.level}
    assert r.confidence is not None and r.confidence > 70
    assert r.positive_factors and not r.negative_factors or r.positive_factors


def test_aligned_bearish_signals_give_sell():
    r = evaluate(bearish_inputs())
    assert r.decision == "SELL" and r.decision_score <= DEFAULT_ENGINE_CONFIG.decision.sell_threshold
    assert r.signals["technical"] == "BEARISH" and r.signals["fundamental"] == "WEAK"
    assert r.signals["sentiment"] == "NEGATIVE" and r.signals["prediction"] == "BEARISH"
    assert any("bearish" in t.lower() for t in r.negative_factors)


def test_neutral_signals_give_hold():
    inputs = DecisionInputs(
        market=market(),
        technical=technical_bullish(trend="neutral", macd_histogram=0.0, macd_crossover="none", rsi=50.0,
                                    sma={"20": 99.0, "50": 101.0}, ema={}, bollinger_upper=106, bollinger_middle=100,
                                    bollinger_lower=94, support_levels=[90.0], resistance_levels=[110.0]),
        fundamental=fundamental_strong(score=50.0, market_cap_rank=200, market_cap_to_fdv=0.5),
        sentiment=sentiment_positive(average_score=0.0, positive_percent=30, negative_percent=30, trend_direction="stable"),
        prediction=prediction_up(direction="flat", predicted_return=0.0004, return_lower=-0.01, return_upper=0.01))
    r = evaluate(inputs)
    assert r.decision == "HOLD" and abs(r.decision_score) < 25


def test_bullish_technicals_alone_do_not_force_buy_when_the_other_signals_disagree():
    inputs = DecisionInputs(market=market(), technical=technical_bullish(), fundamental=fundamental_weak(),
                            sentiment=sentiment_negative(), prediction=prediction_down())
    r = evaluate(inputs)
    assert r.decision != "BUY"
    assert r.agreement["conflicting"] is True
    assert r.signals["technical"] == "BULLISH"


# ---- risk adjustment / overrides ----------------------------------------------------------


def _risky_market():
    return market(market_cap_usd=4e6, volume_24h_usd=60e3, high_24h_usd=118.0, low_24h_usd=84.0)


def test_high_risk_dampens_bullish_conviction():
    risky = evaluate(risky_bullish_inputs())
    assert risky.risk.level in ("HIGH", "VERY_HIGH")
    assert risky.risk_adjustment < 0 and risky.decision_score < risky.raw_score
    assert evaluate(bullish_inputs()).risk_adjustment == 0


def test_buy_is_turned_into_hold_by_the_risk_gate_at_high_risk():
    r = evaluate(risky_bullish_inputs())
    assert r.risk.level in ("HIGH", "VERY_HIGH")
    assert r.base_decision == "BUY" and r.decision == "HOLD"
    assert [o["rule"] for o in r.overrides] == ["risk_buy_gate"]
    assert "risk" in r.explanation[-1].lower()


def test_bearish_scores_are_not_dampened_by_risk():
    r = evaluate(bearish_inputs())
    assert r.risk_adjustment == 0 and r.decision_score == r.raw_score


def test_strong_negative_signals_with_reasonable_risk_give_sell():
    inputs = replace(bearish_inputs(), market=market(market_cap_usd=30e9, volume_24h_usd=1e9))
    r = evaluate(inputs)
    assert r.decision == "SELL" and r.risk.level in ("VERY_LOW", "LOW", "MODERATE")


def test_mildly_negative_score_at_high_risk_escalates_to_sell():
    cfg = EngineConfig(decision=replace(DEFAULT_ENGINE_CONFIG.decision, sell_threshold=-80.0))
    r = evaluate(bearish_inputs(), cfg)
    # score is about -51; with the sell threshold pushed to -80 the base is HOLD …
    assert r.base_decision == "HOLD"
    # … and the risk level here is only MODERATE, so no escalation yet.
    assert r.decision == "HOLD" and r.overrides == []
    risky = replace(bearish_inputs(), market=market(market_cap_usd=3e6, volume_24h_usd=30e3, high_24h_usd=125.0, low_24h_usd=80.0),
                    technical=technical_bearish(atr=9.0, bollinger_upper=150, bollinger_middle=100, bollinger_lower=50))
    r2 = evaluate(risky, cfg)
    assert r2.risk.level in ("HIGH", "VERY_HIGH")
    assert r2.base_decision == "HOLD" and r2.decision == "SELL"
    assert [o["rule"] for o in r2.overrides] == ["risk_sell_escalation"]


def test_conflicting_signals_with_a_weak_score_give_hold():
    inputs = DecisionInputs(market=market(), technical=technical_bullish(), fundamental=fundamental_weak(),
                            sentiment=sentiment_negative(), prediction=prediction_up())
    cfg = EngineConfig(decision=replace(DEFAULT_ENGINE_CONFIG.decision, buy_threshold=5.0))
    r = evaluate(inputs, cfg)
    assert r.agreement["conflicting"] is True
    assert r.decision == "HOLD"
    assert "signal_conflict" in [o["rule"] for o in r.overrides] or r.base_decision == "HOLD"


def test_low_confidence_blocks_buy_and_sell():
    cfg = EngineConfig(decision=replace(DEFAULT_ENGINE_CONFIG.decision, min_confidence_for_action=99.9))
    r = evaluate(bullish_inputs(), cfg)
    assert r.base_decision == "BUY" and r.decision == "HOLD"
    assert "low_confidence" in [o["rule"] for o in r.overrides]
    assert evaluate(bearish_inputs(), cfg).decision == "HOLD"


# ---- unavailable prediction -----------------------------------------------------------------


def test_missing_prediction_is_optional_and_still_gives_a_decision_with_a_warning():
    r = evaluate(without(bullish_inputs(), "prediction"))
    assert r.status == "VALID" and r.decision == "BUY"
    assert r.signals["prediction"] == "UNAVAILABLE" and r.signal_scores["prediction"] is None
    assert r.data_quality["prediction"]["available"] is False
    assert r.data_quality["summary"]["prediction_available"] is False
    assert any("ML prediction unavailable" in w and "remaining available signals" in w for w in r.warnings)
    assert "prediction" not in r.effective_weights
    assert sum(r.effective_weights.values()) == pytest.approx(0.70)  # 0.35 + 0.20 + 0.15 re-normalised at use


def test_unavailable_prediction_lowers_confidence_compared_with_the_full_picture():
    full = evaluate(bullish_inputs())
    partial = evaluate(without(bullish_inputs(), "prediction"))
    assert partial.confidence < full.confidence


def test_prediction_can_be_made_required_by_configuration():
    cfg = EngineConfig(decision=replace(DEFAULT_ENGINE_CONFIG.decision, prediction_required=True))
    r = evaluate(without(bullish_inputs(), "prediction"), cfg)
    assert r.status == "PREDICTION_UNAVAILABLE" and r.decision is None


def test_engine_unavailable_prediction_is_reported_as_unavailable_not_as_a_zero():
    inputs = replace(bullish_inputs(), prediction=prediction_up(status=not_ok(STATE_UNAVAILABLE, "engine not installed")))
    r = evaluate(inputs)
    assert r.data_quality["prediction"]["state"] == "unavailable"
    assert r.signal_scores["prediction"] is None


def test_stale_prediction_is_excluded():
    inputs = replace(bullish_inputs(), prediction=prediction_up(status=not_ok(STATE_STALE, "too old")))
    r = evaluate(inputs)
    assert r.signals["prediction"] == "UNAVAILABLE" and r.data_quality["prediction"]["state"] == "stale"


def test_uncalibrated_prediction_confidence_counts_at_reduced_strength_and_is_disclosed():
    calibrated = evaluate(bullish_inputs())
    uncal = evaluate(replace(bullish_inputs(), prediction=prediction_up(confidence=None, confidence_status="unavailable")))
    assert uncal.signal_scores["prediction"] < calibrated.signal_scores["prediction"]
    assert any("not calibrated" in w for w in uncal.warnings)
    assert "ML prediction confidence is unavailable (not calibrated)" in uncal.negative_factors


def test_prediction_range_crossing_zero_weakens_the_signal():
    tight = evaluate(bullish_inputs()).signal_scores["prediction"]
    straddle = evaluate(replace(bullish_inputs(), prediction=prediction_up(return_lower=-0.01, return_upper=0.05))).signal_scores["prediction"]
    assert straddle < tight


# ---- missing / insufficient / stale data -----------------------------------------------------------


@pytest.mark.parametrize("missing", ["technical", "fundamental", "sentiment"])
def test_each_single_missing_module_still_gives_a_valid_decision_without_inventing_it(missing):
    r = evaluate(without(bullish_inputs(), missing))
    assert r.status == "VALID"
    assert r.signals[missing] == "UNAVAILABLE" and r.signal_scores[missing] is None
    assert r.data_quality[missing]["available"] is False and r.data_quality[missing]["state"] == "missing"
    assert any(missing.capitalize() in w for w in r.warnings)
    assert r.risk.coverage < 1.0


def test_too_few_usable_modules_gives_insufficient_data_and_no_decision():
    r = evaluate(without(bullish_inputs(), "fundamental", "sentiment", "prediction"))
    assert r.status == "INSUFFICIENT_DATA" and r.decision is None and r.decision_score is None
    assert r.confidence is None and r.confidence_status == "unavailable"
    assert r.positive_factors == [] and r.negative_factors == []
    assert "No decision was produced" in r.explanation[0]


def test_no_data_at_all_gives_insufficient_data():
    r = evaluate(DecisionInputs())
    assert r.status == "INSUFFICIENT_DATA" and r.decision is None and r.risk.score is None


def test_missing_market_data_gives_insufficient_data():
    r = evaluate(replace(bullish_inputs(), market=market(status=not_ok("missing", "No market data has been synchronized."))))
    assert r.status == "INSUFFICIENT_DATA" and r.decision is None


def test_stale_market_data_gives_stale_data_status():
    r = evaluate(replace(bullish_inputs(), market=market(status=not_ok(STATE_STALE, "The market data snapshot is out of date."))))
    assert r.status == "STALE_DATA" and r.decision is None and "out of date" in r.status_reason


def test_stale_underlying_modules_give_stale_data_status():
    base = bullish_inputs()
    inputs = replace(base, technical=replace(base.technical, status=not_ok(STATE_STALE, "old")),
                     fundamental=replace(base.fundamental, status=not_ok("missing", "x")),
                     sentiment=replace(base.sentiment, status=not_ok("insufficient_data", "x")),
                     prediction=replace(base.prediction, status=not_ok("missing", "x")))
    assert evaluate(inputs).status == "STALE_DATA"


def test_every_analysis_module_failing_gives_analysis_unavailable():
    base = bullish_inputs()
    inputs = replace(base, technical=replace(base.technical, status=not_ok(STATE_UNAVAILABLE, "down")),
                     fundamental=replace(base.fundamental, status=not_ok(STATE_UNAVAILABLE, "down")),
                     sentiment=replace(base.sentiment, status=not_ok(STATE_UNAVAILABLE, "down")),
                     prediction=replace(base.prediction, status=not_ok(STATE_UNAVAILABLE, "down")))
    r = evaluate(inputs)
    assert r.status == "ANALYSIS_UNAVAILABLE" and r.decision is None


def test_a_module_with_data_but_no_usable_indicators_counts_as_insufficient():
    inputs = replace(bullish_inputs(), fundamental=fundamental_strong(score=None, market_cap_rank=None, market_cap_to_fdv=None))
    r = evaluate(inputs)
    assert r.data_quality["fundamental"]["state"] == "insufficient_data" and r.signals["fundamental"] == "UNAVAILABLE"


def test_invalid_numeric_values_never_reach_the_scores():
    inputs = replace(bullish_inputs(), technical=technical_bullish(rsi=None, macd_histogram=None, atr=None))
    r = evaluate(inputs)
    assert r.status == "VALID" and r.signal_scores["technical"] is not None


# ---- confidence -------------------------------------------------------------------------------------


def test_aligned_signals_have_higher_confidence_than_conflicting_ones():
    aligned = evaluate(bullish_inputs())
    conflicting = evaluate(DecisionInputs(market=market(), technical=technical_bullish(), fundamental=fundamental_weak(),
                                          sentiment=sentiment_negative(), prediction=prediction_up()))
    assert aligned.confidence > conflicting.confidence + 20
    assert aligned.agreement["cross_module"] > conflicting.agreement["cross_module"]


def test_confidence_is_unavailable_rather_than_invented_when_it_cannot_be_established():
    cfg = EngineConfig(decision=replace(DEFAULT_ENGINE_CONFIG.decision, min_usable_modules=1))
    r = evaluate(without(bullish_inputs(), "fundamental", "sentiment", "prediction"), cfg)
    assert r.status == "VALID"
    assert r.confidence is None and r.confidence_status == "unavailable"  # one module cannot 'agree' with itself
    assert r.decision == "HOLD"  # a BUY/SELL needs a computed confidence
    assert [o["rule"] for o in r.overrides] == ["low_confidence"]


def test_thin_sentiment_counts_with_reduced_weight_and_says_so():
    thin = evaluate(replace(bullish_inputs(), sentiment=sentiment_positive(total_articles=3)))
    full = evaluate(bullish_inputs())
    assert thin.effective_weights["sentiment"] < full.effective_weights["sentiment"]
    assert any("analysed articles" in w for w in thin.warnings)


def test_high_risk_reduces_confidence_of_a_bullish_reading():
    risky = evaluate(risky_bullish_inputs())
    same_signals_low_risk = replace(risky_bullish_inputs(), market=market(), technical=technical_bullish(
        support_levels=[70.0], resistance_levels=[101.0]))
    calm = evaluate(same_signals_low_risk)
    assert calm.risk.score < risky.risk.score
    assert risky.confidence < calm.confidence


# ---- structure / explainability ---------------------------------------------------------------------------


def test_factors_are_rule_generated_sentences_without_duplicates_and_capped():
    r = evaluate(bearish_inputs())
    for factors in (r.positive_factors, r.negative_factors):
        assert len(factors) == len(set(factors)) <= 8
        assert all(isinstance(t, str) and t for t in factors)


def test_explanation_states_score_risk_and_module_counts():
    r = evaluate(bullish_inputs())
    text = " ".join(r.explanation)
    assert "Decision: BUY" in text and "Risk is" in text and "module(s) lean bullish" in text


def test_versions_are_reported():
    r = evaluate(bullish_inputs())
    assert r.engine_version == "1.0" and r.risk_config_version == "1.0"


def test_default_module_weights_sum_to_one():
    assert sum(DecisionConfig().module_weights.values()) == pytest.approx(1.0)
    for w in (DecisionConfig().technical_weights, DecisionConfig().fundamental_weights, DecisionConfig().sentiment_weights):
        assert sum(w.values()) == pytest.approx(1.0)


# ---- determinism --------------------------------------------------------------------------------------------


def test_same_input_always_gives_the_same_decision():
    runs = [evaluate(bullish_inputs()) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    runs = [evaluate(bearish_inputs()) for _ in range(5)]
    assert all(run == runs[0] for run in runs)


def test_the_engine_source_uses_no_randomness_llm_or_clock():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    for rel in ("services/decision_engine.py", "services/risk_service.py", "services/decision_inputs.py",
                "services/scoring.py", "config/risk_config.py"):
        text = (root / rel).read_text(encoding="utf-8").lower()
        for forbidden in ("import random", "from random", "numpy.random", "gemini", "openai", "anthropic", "datetime.now", "time.time"):
            assert forbidden not in text, (rel, forbidden)
