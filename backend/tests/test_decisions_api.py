"""API-level tests for /api/v1/decisions (service mocked — no MongoDB, no providers)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.schemas.decisions import (
    DISCLAIMER, AgreementSchema, DataQualitySchema, DataQualitySummary, DecisionResponse, ModuleQualitySchema,
    RiskResponse, RiskSchema, SignalScoresSchema, SignalsSchema,
)

COIN_ID = "507f1f77bcf86cd799439011"
NOW = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _quality(prediction_available=True) -> DataQualitySchema:
    ok = ModuleQualitySchema(available=True, state="available")
    no = ModuleQualitySchema(available=False, state="unavailable", reason="The prediction engine is not available on the server right now.")
    return DataQualitySchema(market=ok, technical=ok, fundamental=ok, sentiment=ok, prediction=ok if prediction_available else no,
                             summary=DataQualitySummary(usable_modules=["technical"], module_coverage_percent=100.0,
                                                        risk_coverage_percent=100.0, prediction_available=prediction_available))


def _risk() -> RiskSchema:
    return RiskSchema(available=True, score=34.0, level="LOW", coverage_percent=100.0, config_version="1.0")


def _decision(**over) -> DecisionResponse:
    base = dict(
        coin_id=COIN_ID, symbol="BTC", decision="BUY", status="VALID", decision_score=68.0, raw_score=68.0, risk_adjustment=0.0,
        confidence=78.0, confidence_status="computed", risk_score=34.0, risk_level="LOW", risk=_risk(),
        signals=SignalsSchema(technical="BULLISH", fundamental="STRONG", sentiment="POSITIVE", prediction="BULLISH", risk="LOW"),
        signal_scores=SignalScoresSchema(technical=40.0, fundamental=50.0, sentiment=30.0, prediction=45.0),
        positive_factors=["Positive MACD momentum"], negative_factors=["High volatility"], agreement=AgreementSchema(cross_module=1.0),
        data_quality=_quality(), generated_at=NOW, expires_at=NOW + timedelta(minutes=5), engine_version="1.0", risk_config_version="1.0",
    )
    base.update(over)
    return DecisionResponse(**base)


def test_decision_endpoint_returns_the_documented_shape(client):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(return_value=_decision())
        r = client.get(f"/api/v1/decisions/{COIN_ID}")
    assert r.status_code == 200
    body = r.json()
    for key in ("coin_id", "symbol", "decision", "status", "decision_score", "confidence", "confidence_status", "risk_score",
                "risk_level", "risk", "signals", "positive_factors", "negative_factors", "data_quality", "generated_at",
                "expires_at", "engine_version", "risk_config_version", "disclaimer", "kind"):
        assert key in body
    assert body["decision"] == "BUY" and body["risk_level"] == "LOW" and body["disclaimer"] == DISCLAIMER
    assert body["kind"] == "model_based_decision"
    svc.return_value.get_decision.assert_awaited_once_with(COIN_ID, force_refresh=False)


def test_force_refresh_is_passed_through(client):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(return_value=_decision())
        client.get(f"/api/v1/decisions/{COIN_ID}?force_refresh=true")
    svc.return_value.get_decision.assert_awaited_once_with(COIN_ID, force_refresh=True)


def test_latest_endpoint_never_calculates(client):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_decision(is_stale=True))
        svc.return_value.get_decision = AsyncMock()
        r = client.get(f"/api/v1/decisions/{COIN_ID}/latest")
    assert r.status_code == 200 and r.json()["is_stale"] is True
    svc.return_value.get_decision.assert_not_awaited()


def test_risk_endpoint(client):
    risk = RiskResponse(coin_id=COIN_ID, symbol="BTC", risk=_risk(), risk_score=34.0, risk_level="LOW", data_quality=_quality(),
                        generated_at=NOW, expires_at=NOW + timedelta(minutes=5), engine_version="1.0", risk_config_version="1.0")
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_risk = AsyncMock(return_value=risk)
        r = client.get(f"/api/v1/decisions/{COIN_ID}/risk")
    assert r.status_code == 200
    assert r.json()["risk_score"] == 34.0 and r.json()["risk_level"] == "LOW"


def test_insufficient_data_returns_a_null_decision_with_a_status(client):
    d = _decision(decision=None, status="INSUFFICIENT_DATA", status_reason="Only 1 of the 4 analysis modules have usable data.",
                  decision_score=None, raw_score=None, risk_adjustment=None, confidence=None, confidence_status="unavailable",
                  risk_score=None, risk_level=None, positive_factors=[], negative_factors=[])
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(return_value=d)
        body = client.get(f"/api/v1/decisions/{COIN_ID}").json()
    assert body["decision"] is None and body["status"] == "INSUFFICIENT_DATA"
    assert body["confidence"] is None and body["confidence_status"] == "unavailable"
    assert body["decision_score"] is None and body["risk_score"] is None


def test_missing_prediction_is_reported_in_data_quality(client):
    d = _decision(data_quality=_quality(prediction_available=False), signals=SignalsSchema(
        technical="BULLISH", fundamental="STRONG", sentiment="POSITIVE", prediction="UNAVAILABLE", risk="LOW"),
        warnings=["ML prediction unavailable (x). Decision calculated using the remaining available signals."])
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(return_value=d)
        body = client.get(f"/api/v1/decisions/{COIN_ID}").json()
    assert body["data_quality"]["prediction"]["available"] is False
    assert body["signals"]["prediction"] == "UNAVAILABLE" and body["decision"] == "BUY"


@pytest.mark.parametrize("code,status", [("INVALID_COIN_ID", 400), ("COIN_NOT_FOUND", 404), ("DECISION_NOT_FOUND", 404), ("DATABASE_UNAVAILABLE", 503)])
def test_service_errors_use_the_standard_error_shape(client, code, status):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(side_effect=AppError(status, code, "msg"))
        svc.return_value.get_latest = AsyncMock(side_effect=AppError(status, code, "msg"))
        r1 = client.get(f"/api/v1/decisions/{COIN_ID}")
        r2 = client.get(f"/api/v1/decisions/{COIN_ID}/latest")
    for r in (r1, r2):
        assert r.status_code == status and r.json() == {"error": {"code": code, "message": "msg"}}


def test_latest_is_not_captured_as_a_coin_id(client):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_decision())
        svc.return_value.get_decision = AsyncMock()
        client.get(f"/api/v1/decisions/{COIN_ID}/latest")
    svc.return_value.get_decision.assert_not_awaited()


def test_decision_response_carries_no_llm_or_trading_fields(client):
    with patch("app.api.v1.decisions.DecisionService") as svc:
        svc.return_value.get_decision = AsyncMock(return_value=_decision())
        body = client.get(f"/api/v1/decisions/{COIN_ID}").json()
    for forbidden in ("gemini", "ai_explanation", "order", "trade", "execute", "wallet"):
        assert forbidden not in " ".join(body.keys()).lower()
