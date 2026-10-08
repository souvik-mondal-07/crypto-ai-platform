"""Risk engine (Phase 14): component scoring, weighting, availability handling, level boundaries, determinism."""

from dataclasses import replace

import pytest

from app.config.risk_config import (
    DEFAULT_ENGINE_CONFIG,
    RISK_HIGH,
    RISK_LOW,
    RISK_MODERATE,
    RISK_VERY_HIGH,
    RISK_VERY_LOW,
    RiskConfig,
)
from app.services.decision_inputs import DecisionInputs
from app.services.risk_service import calculate_risk
from app.services.scoring import level_for_rounded_score, piecewise
from tests.decision_fixtures import (
    bearish_inputs,
    bullish_inputs,
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

CFG = DEFAULT_ENGINE_CONFIG.risk


def component(result, key):
    return next(c for c in result.components if c.key == key)


# ---- helpers ---------------------------------------------------------------


def test_piecewise_interpolates_and_clamps():
    curve = ((0, 10), (10, 30), (20, 90))
    assert piecewise(-5, curve) == 10
    assert piecewise(5, curve) == 20
    assert piecewise(15, curve) == 60
    assert piecewise(99, curve) == 90


def test_default_risk_weights_sum_to_one_and_sub_weights_are_complete():
    assert sum(CFG.component_weights.values()) == pytest.approx(1.0)
    for name, subs in CFG.sub_weights.items():
        assert name in CFG.component_weights
        assert all(w > 0 for w in subs.values())


# ---- volatility ---------------------------------------------------------------


def test_high_atr_scores_higher_volatility_risk_than_low_atr():
    low = calculate_risk(DecisionInputs(market=market(), technical=technical_bullish(atr=0.5)))
    high = calculate_risk(DecisionInputs(market=market(), technical=technical_bullish(atr=8.0)))
    assert component(high, "volatility").score > component(low, "volatility").score + 30


def test_wide_bollinger_bands_and_large_24h_range_raise_volatility_risk():
    calm = DecisionInputs(market=market(high_24h_usd=100.5, low_24h_usd=99.5),
                          technical=technical_bullish(bollinger_upper=101, bollinger_middle=100, bollinger_lower=99))
    wild = DecisionInputs(market=market(high_24h_usd=125.0, low_24h_usd=85.0),
                          technical=technical_bullish(bollinger_upper=140, bollinger_middle=100, bollinger_lower=60))
    assert component(calculate_risk(wild), "volatility").score > component(calculate_risk(calm), "volatility").score + 40


def test_volatility_still_uses_the_24h_range_when_technical_analysis_is_missing():
    inputs = DecisionInputs(market=market(high_24h_usd=110.0, low_24h_usd=90.0), technical=technical_bullish())
    inputs = without(inputs, "technical")
    vol = component(calculate_risk(inputs), "volatility")
    assert vol.available and [f.key for f in vol.factors] == ["range_24h_pct"]


# ---- liquidity ------------------------------------------------------------------


def test_thin_market_has_much_higher_liquidity_risk_than_a_deep_one():
    deep = calculate_risk(DecisionInputs(market=market(market_cap_usd=100e9, volume_24h_usd=5e9)))
    thin = calculate_risk(DecisionInputs(market=market(market_cap_usd=5e6, volume_24h_usd=50e3)))
    assert component(deep, "liquidity").score < 15
    assert component(thin, "liquidity").score > 85


def test_abnormal_volume_to_market_cap_ratio_is_penalised():
    healthy = calculate_risk(DecisionInputs(market=market(market_cap_usd=1e9, volume_24h_usd=1e8)))
    frothy = calculate_risk(DecisionInputs(market=market(market_cap_usd=1e9, volume_24h_usd=2e9)))
    sub = lambda r: next(f for f in component(r, "liquidity").factors if f.key == "volume_to_market_cap").score  # noqa: E731
    assert sub(frothy) > sub(healthy) + 40


# ---- technical -------------------------------------------------------------------


def test_bearish_overbought_technicals_are_riskier_than_balanced_bullish_ones():
    good = calculate_risk(DecisionInputs(market=market(), technical=technical_bullish()))
    bad = calculate_risk(DecisionInputs(market=market(), technical=technical_bearish(rsi=88.0)))
    assert component(bad, "technical").score > component(good, "technical").score + 20


def test_price_near_resistance_adds_support_resistance_risk():
    near_support = technical_bullish(support_levels=[99.0], resistance_levels=[120.0])
    near_resistance = technical_bullish(support_levels=[80.0], resistance_levels=[101.0])
    sub = lambda t: next(f for f in component(calculate_risk(DecisionInputs(market=market(), technical=t)), "technical").factors  # noqa: E731
                         if f.key == "support_resistance").score
    assert sub(near_resistance) > sub(near_support)


# ---- fundamental ------------------------------------------------------------------


def test_weak_fundamentals_are_riskier_than_strong_ones():
    strong = calculate_risk(DecisionInputs(market=market(), fundamental=fundamental_strong()))
    weak = calculate_risk(DecisionInputs(market=market(), fundamental=fundamental_weak()))
    assert component(weak, "fundamental").score > component(strong, "fundamental").score + 40


def test_capped_supply_only_counts_when_the_supply_is_actually_capped():
    capped = fundamental_strong(supply_type="capped", circulating_to_max_supply_percent=10.0)
    uncapped = fundamental_strong(supply_type="unlimited", circulating_to_max_supply_percent=10.0)
    keys = lambda f: {x.key for x in component(calculate_risk(DecisionInputs(market=market(), fundamental=f)), "fundamental").factors}  # noqa: E731
    assert "supply" in keys(capped) and "supply" not in keys(uncapped)


# ---- sentiment ---------------------------------------------------------------------


def test_negative_declining_sentiment_is_riskier_than_positive_improving_sentiment():
    pos = calculate_risk(DecisionInputs(market=market(), sentiment=sentiment_positive()))
    neg = calculate_risk(DecisionInputs(market=market(), sentiment=sentiment_negative()))
    assert component(neg, "sentiment").score > component(pos, "sentiment").score + 30


def test_insufficient_sentiment_is_excluded_not_treated_as_neutral():
    inputs = DecisionInputs(market=market(), sentiment=sentiment_positive(status=not_ok("insufficient_data", "too few")))
    comp = component(calculate_risk(inputs), "sentiment")
    assert not comp.available and comp.score is None and comp.contribution is None


# ---- prediction ---------------------------------------------------------------------


def test_bearish_wide_low_confidence_prediction_is_riskier_than_a_tight_confident_bullish_one():
    good = calculate_risk(DecisionInputs(market=market(), prediction=prediction_up(
        return_lower=0.02, return_upper=0.03, confidence=0.8)))
    bad = calculate_risk(DecisionInputs(market=market(), prediction=prediction_down(
        return_lower=-0.12, return_upper=0.02, confidence=0.52)))
    assert component(bad, "prediction").score > component(good, "prediction").score + 40


def test_uncalibrated_prediction_confidence_is_not_scored():
    p = prediction_up(confidence=None, confidence_status="unavailable")
    comp = component(calculate_risk(DecisionInputs(market=market(), prediction=p)), "prediction")
    assert comp.available and "model_confidence" not in {f.key for f in comp.factors}


def test_unavailable_prediction_is_excluded_not_assumed_low_or_high_risk():
    result = calculate_risk(without(bullish_inputs(), "prediction"))
    comp = component(result, "prediction")
    assert not comp.available and comp.score is None
    assert result.available and result.coverage == pytest.approx(0.85)


# ---- final score / weighting ---------------------------------------------------------


def test_final_score_is_the_weighted_average_of_available_components():
    result = calculate_risk(bullish_inputs())
    avail = [c for c in result.components if c.available]
    total_w = sum(c.weight for c in avail)
    expected = sum(c.score * c.weight for c in avail) / total_w
    assert result.score == pytest.approx(round(expected, 1), abs=0.051)
    assert sum(c.contribution for c in avail) == pytest.approx(result.score, abs=0.2)


def test_weights_are_configurable():
    inputs = bullish_inputs()
    base = calculate_risk(inputs)
    only_liquidity = replace(CFG, component_weights={"volatility": 0, "liquidity": 1.0, "technical": 0,
                                                     "fundamental": 0, "sentiment": 0, "prediction": 0},
                             min_coverage=0.1)
    custom = calculate_risk(inputs, only_liquidity)
    assert custom.score == pytest.approx(component(custom, "liquidity").score, abs=0.051)
    assert custom.score != base.score


def test_risk_is_higher_for_the_risky_scenario_than_for_the_safe_one():
    safe = calculate_risk(bullish_inputs())
    risky = calculate_risk(DecisionInputs(
        market=market(market_cap_usd=3e6, volume_24h_usd=40e3, high_24h_usd=130.0, low_24h_usd=70.0),
        technical=technical_bearish(atr=9.0, rsi=90.0, bollinger_upper=150, bollinger_middle=100, bollinger_lower=50),
        fundamental=fundamental_weak(), sentiment=sentiment_negative(), prediction=prediction_down(confidence=0.52)))
    assert safe.level in (RISK_VERY_LOW, RISK_LOW)
    assert risky.level in (RISK_HIGH, RISK_VERY_HIGH)
    assert risky.score > safe.score + 40


def test_risk_factors_are_generated_from_rules():
    safe = calculate_risk(bullish_inputs())
    risky = calculate_risk(bearish_inputs())
    assert any("liquidity" in t.lower() for t in safe.positive_factors)
    assert any("Price is" in t and "below its all-time high" in t for t in risky.negative_factors)
    assert safe.score is not None and risky.score is not None


# ---- availability / coverage -----------------------------------------------------------


def test_no_data_at_all_gives_no_risk_score():
    result = calculate_risk(DecisionInputs())
    assert not result.available and result.score is None and result.level is None and result.coverage == 0.0


def test_a_risk_score_needs_volatility_or_liquidity_evidence():
    bare_market = market(market_cap_usd=None, volume_24h_usd=None, high_24h_usd=None, low_24h_usd=None)
    inputs = DecisionInputs(market=bare_market, fundamental=fundamental_strong(), sentiment=sentiment_positive(), prediction=prediction_up())
    result = calculate_risk(inputs)
    assert not result.available and result.score is None and "volatility nor liquidity" in result.reason


def test_coverage_below_the_minimum_gives_no_score():
    strict = replace(CFG, min_coverage=0.95)
    result = calculate_risk(without(bullish_inputs(), "prediction"), strict)
    assert not result.available and result.score is None and "backed by data" in result.reason


def test_stale_market_data_is_not_used_for_risk():
    inputs = DecisionInputs(market=market(status=not_ok("stale", "old")))
    assert not calculate_risk(inputs).available


# ---- levels -----------------------------------------------------------------------------


@pytest.mark.parametrize("score,level", [
    (0, RISK_VERY_LOW), (20, RISK_VERY_LOW), (20.4, RISK_VERY_LOW), (20.6, RISK_LOW), (21, RISK_LOW), (40, RISK_LOW),
    (41, RISK_MODERATE), (60, RISK_MODERATE), (61, RISK_HIGH), (80, RISK_HIGH), (81, RISK_VERY_HIGH), (100, RISK_VERY_HIGH),
])
def test_risk_level_boundaries(score, level):
    assert level_for_rounded_score(score, CFG.level_bounds) == level


def test_result_level_matches_the_documented_band_for_its_score():
    result = calculate_risk(bearish_inputs())
    assert result.level == level_for_rounded_score(result.score, CFG.level_bounds)


# ---- determinism --------------------------------------------------------------------------


def test_same_input_gives_the_same_risk_result():
    assert calculate_risk(bullish_inputs()) == calculate_risk(bullish_inputs())


def test_custom_config_is_independent_of_the_default():
    assert isinstance(CFG, RiskConfig)
    assert DEFAULT_ENGINE_CONFIG.risk_config_version == "1.0"


def test_no_risk_score_without_usable_market_data_even_if_other_modules_have_data():
    for status in (not_ok("missing", "No market data"), not_ok("stale", "old")):
        inputs = replace(bullish_inputs(), market=market(status=status))
        result = calculate_risk(inputs)
        assert not result.available and result.score is None and result.level is None
