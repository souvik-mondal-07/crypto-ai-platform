"""Builders for Phase 14 engine inputs (synthetic values — tests only; the application never imports this)."""

from dataclasses import replace
from datetime import datetime, timezone

from app.config.risk_config import STATE_AVAILABLE, STATE_MISSING
from app.services.decision_inputs import (
    DecisionInputs,
    FundamentalInput,
    MarketInput,
    ModuleStatus,
    PredictionInput,
    SentimentInput,
    TechnicalInput,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def ok(reason=None) -> ModuleStatus:
    return ModuleStatus(state=STATE_AVAILABLE, reason=reason, as_of=NOW)


def not_ok(state=STATE_MISSING, reason="no data") -> ModuleStatus:
    return ModuleStatus(state=state, reason=reason)


def market(**kw) -> MarketInput:
    base = dict(status=ok(), price_usd=100.0, market_cap_usd=50e9, volume_24h_usd=2e9, high_24h_usd=101.0,
                low_24h_usd=99.0, percent_change_24h=1.2, percent_change_7d=4.0, percent_change_30d=10.0)
    base.update(kw)
    return MarketInput(**base)


def technical_bullish(**kw) -> TechnicalInput:
    base = dict(status=ok(), timeframe="30D", trend="bullish", rsi=62.0, macd_histogram=1.2, macd_crossover="none",
                sma={"20": 95.0, "50": 90.0, "200": 80.0}, ema={"20": 96.0, "50": 92.0},
                bollinger_upper=104.0, bollinger_middle=98.0, bollinger_lower=92.0, atr=1.5,
                support_levels=[95.0], resistance_levels=[108.0], volume_trend="increasing")
    base.update(kw)
    return TechnicalInput(**base)


def technical_bearish(**kw) -> TechnicalInput:
    base = dict(status=ok(), timeframe="30D", trend="bearish", rsi=38.0, macd_histogram=-1.5, macd_crossover="bearish_crossover",
                sma={"20": 105.0, "50": 110.0, "200": 120.0}, ema={"20": 104.0, "50": 108.0},
                bollinger_upper=112.0, bollinger_middle=106.0, bollinger_lower=100.0, atr=1.5,
                support_levels=[92.0], resistance_levels=[101.0], volume_trend="decreasing")
    base.update(kw)
    return TechnicalInput(**base)


def fundamental_strong(**kw) -> FundamentalInput:
    base = dict(status=ok(), score=78.0, coverage_percent=90.0, market_cap_rank=3, market_cap_to_fdv=0.95,
                circulating_to_max_supply_percent=None, supply_type="not_reported", distance_from_ath_percent=-35.0)
    base.update(kw)
    return FundamentalInput(**base)


def fundamental_weak(**kw) -> FundamentalInput:
    base = dict(status=ok(), score=22.0, coverage_percent=60.0, market_cap_rank=1500, market_cap_to_fdv=0.18,
                circulating_to_max_supply_percent=None, supply_type="not_reported", distance_from_ath_percent=-92.0)
    base.update(kw)
    return FundamentalInput(**base)


def sentiment_positive(**kw) -> SentimentInput:
    base = dict(status=ok(), timeframe="24h", label="positive", average_score=0.4, positive_percent=60.0,
                negative_percent=15.0, total_articles=20, trend_direction="improving")
    base.update(kw)
    return SentimentInput(**base)


def sentiment_negative(**kw) -> SentimentInput:
    base = dict(status=ok(), timeframe="24h", label="negative", average_score=-0.5, positive_percent=10.0,
                negative_percent=70.0, total_articles=20, trend_direction="declining")
    base.update(kw)
    return SentimentInput(**base)


def prediction_up(**kw) -> PredictionInput:
    base = dict(status=ok(), horizon="24h", model="xgboost", direction="up", predicted_return=0.024,
                return_lower=0.01, return_upper=0.04, confidence=0.7, confidence_status="calibrated")
    base.update(kw)
    return PredictionInput(**base)


def prediction_down(**kw) -> PredictionInput:
    base = dict(status=ok(), horizon="24h", model="xgboost", direction="down", predicted_return=-0.03,
                return_lower=-0.045, return_upper=-0.012, confidence=0.72, confidence_status="calibrated")
    base.update(kw)
    return PredictionInput(**base)


def bullish_inputs() -> DecisionInputs:
    return DecisionInputs(market=market(), technical=technical_bullish(), fundamental=fundamental_strong(),
                          sentiment=sentiment_positive(), prediction=prediction_up())


def bearish_inputs() -> DecisionInputs:
    return DecisionInputs(
        market=market(price_usd=100.0, market_cap_usd=800e6, volume_24h_usd=40e6, high_24h_usd=104.0, low_24h_usd=97.0),
        technical=technical_bearish(), fundamental=fundamental_weak(), sentiment=sentiment_negative(),
        prediction=prediction_down())


def without(inputs: DecisionInputs, *modules: str) -> DecisionInputs:
    """Copy of `inputs` with the given modules set to a MISSING status."""
    changes = {}
    for m in modules:
        changes[m] = replace(getattr(inputs, m), status=not_ok(reason=f"{m} data missing"))
    return replace(inputs, **changes)


def risky_bullish_inputs() -> DecisionInputs:
    """Small, volatile coin with bullish momentum: the risk engine should land at HIGH while signals stay positive."""
    return DecisionInputs(
        market=market(market_cap_usd=4e6, volume_24h_usd=60e3, high_24h_usd=118.0, low_24h_usd=84.0),
        technical=technical_bullish(atr=9.0, rsi=66.0, bollinger_upper=140, bollinger_middle=100, bollinger_lower=60,
                                    support_levels=[70.0], resistance_levels=[101.0]),
        fundamental=fundamental_weak(score=65.0, market_cap_rank=700, market_cap_to_fdv=0.5, distance_from_ath_percent=-90.0),
        sentiment=sentiment_positive(average_score=0.5, total_articles=20, negative_percent=40.0),
        prediction=prediction_up(predicted_return=0.06, return_lower=0.01, return_upper=0.12, confidence=0.6))
