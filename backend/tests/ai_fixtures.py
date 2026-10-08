"""Builders shared by the Phase 15 tests. All values are synthetic test data."""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.ai.payload import build_payload, coin_section, unavailable
from app.ai.schemas.ai_analysis import GeminiAnalysisOutput

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
COIN_ID = "507f1f77bcf86cd799439011"


def available_payload(decision: str = "BUY") -> dict[str, Any]:
    return build_payload(
        coin=coin_section(COIN_ID, "BTC", "Bitcoin"),
        market={"available": True, "price_usd": 64000.0, "market_cap_usd": 1.2e12, "percent_change_24h": 2.5},
        technical={"available": True, "trend": "bullish", "rsi": {"current": 58.0, "zone": "neutral"}},
        fundamental={"available": True, "score": {"status": "scored", "value": 72.0}},
        news={"available": True, "recent_articles": [{"title": "Example headline", "source": "ExampleWire"}]},
        sentiment={"available": True, "label": "positive", "average_score": 0.31},
        prediction={"available": True, "direction": "up", "predicted_return": 0.021, "confidence": 0.62,
                    "predicted_price_range": {"lower": 63000.0, "upper": 66000.0}},
        risk={"available": True, "score": 34.0, "level": "LOW"},
        decision={"available": True, "decision": decision, "status": "VALID", "decision_score": 68.0,
                  "confidence": 78.0, "risk_level": "LOW"},
    )


def payload_without_prediction() -> dict[str, Any]:
    p = available_payload()
    p["prediction"] = unavailable("Prediction engine unavailable")
    return p


def good_output(**over: Any) -> GeminiAnalysisOutput:
    base = dict(
        summary="The platform's decision engine currently rates this coin BUY with low risk.",
        market_analysis="The market data shows a modest gain over the last 24 hours.",
        technical_analysis="The technical trend is bullish and RSI is in a neutral zone.",
        fundamental_analysis="The fundamental score is 72 out of 100.",
        sentiment_analysis="Recent news sentiment is positive.",
        prediction_analysis="The model indicates an upward direction with moderate confidence.",
        risk_analysis="The risk score of 34 corresponds to a LOW risk level.",
        decision_explanation="The official decision is BUY because most signals point the same way.",
        bullish_factors=["Bullish trend", "Positive sentiment"],
        bearish_factors=["Volatility could rise"],
        key_risks=["Crypto markets can move sharply"],
        uncertainties=["The prediction carries only moderate confidence"],
        data_quality="All inputs were available.",
    )
    base.update(over)
    return GeminiAnalysisOutput(**base)


def output_json(**over: Any) -> str:
    return good_output(**over).model_dump_json()


def later(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


def decision_response(**over: Any):
    """A Phase 14 DecisionResponse (reuses the Phase 14 API-test builder)."""
    from tests.test_decisions_api import _decision

    return _decision(**over)
