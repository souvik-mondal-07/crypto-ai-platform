"""API-level tests for /api/v1/ai-analysis (service mocked — no MongoDB, providers or Gemini)."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.schemas.ai_analysis import (
    AI_DISCLAIMER, AIAnalysisContent, AIAnalysisResponse, AIDecisionSnapshot, AIModuleAvailability,
)
from app.core.dependencies import get_current_user
from app.core.exceptions import AppError
from app.main import app
from tests.ai_fixtures import COIN_ID, NOW, good_output

URL = f"/api/v1/ai-analysis/{COIN_ID}"


def _response(**over) -> AIAnalysisResponse:
    base = dict(
        coin_id=COIN_ID, symbol="BTC", analysis=AIAnalysisContent(**good_output().model_dump()),
        decision_snapshot=AIDecisionSnapshot(decision="BUY", status="VALID", risk_level="LOW", risk_score=34.0,
                                             confidence=78.0, decision_score=68.0, engine_version="1.0", generated_at=NOW),
        data_availability={"prediction": AIModuleAvailability(available=False, reason="Prediction engine unavailable")},
        model="gemini-3.1-flash-lite", model_version="gemini-3.1-flash-lite-001", prompt_version="1.0",
        source_data_timestamp=NOW, generated_at=NOW, expires_at=NOW + timedelta(minutes=30), cached=True,
    )
    base.update(over)
    return AIAnalysisResponse(**base)


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"_id": "u1", "is_active": True}
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c


def test_get_returns_the_stored_analysis_shape(client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_response())
        r = client.get(URL)
    assert r.status_code == 200
    body = r.json()
    for key in ("coin_id", "analysis", "decision_snapshot", "data_availability", "model", "model_version", "prompt_version",
                "source_data_timestamp", "generated_at", "expires_at", "is_stale", "is_outdated", "cached", "disclaimer", "kind"):
        assert key in body
    assert body["model"] == "gemini-3.1-flash-lite" and body["decision_snapshot"]["decision"] == "BUY"
    assert body["disclaimer"] == AI_DISCLAIMER and body["kind"] == "ai_explanation"
    for key in ("summary", "market_analysis", "technical_analysis", "fundamental_analysis", "sentiment_analysis",
                "prediction_analysis", "risk_analysis", "decision_explanation", "bullish_factors", "bearish_factors",
                "key_risks", "uncertainties", "data_quality", "disclaimer"):
        assert key in body["analysis"]
    svc.return_value.get_latest.assert_awaited_once_with(COIN_ID)


def test_get_when_nothing_is_stored_is_a_clean_404(client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.get_latest = AsyncMock(side_effect=AppError(404, "AI_ANALYSIS_NOT_FOUND", "No AI analysis has been generated for this coin yet."))
        r = client.get(URL)
    assert r.status_code == 404 and r.json() == {"error": {"code": "AI_ANALYSIS_NOT_FOUND", "message": "No AI analysis has been generated for this coin yet."}}


def test_get_never_generates(client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_response())
        svc.return_value.generate = AsyncMock()
        client.get(URL)
    svc.return_value.generate.assert_not_awaited()


def test_generate_calls_the_service_and_returns_the_analysis(client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.generate = AsyncMock(return_value=_response(cached=False))
        r = client.post(f"{URL}/generate")
    assert r.status_code == 200 and r.json()["cached"] is False
    svc.return_value.generate.assert_awaited_once_with(COIN_ID, force=False)


def test_force_refresh_is_passed_through(client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.generate = AsyncMock(return_value=_response())
        client.post(f"{URL}/generate?force_refresh=true")
    svc.return_value.generate.assert_awaited_once_with(COIN_ID, force=True)


def test_generation_requires_authentication(anon_client):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.generate = AsyncMock(return_value=_response())
        r = anon_client.post(f"{URL}/generate")
    assert r.status_code == 401
    svc.return_value.generate.assert_not_awaited()


@pytest.mark.parametrize("status,code", [
    (503, "AI_NOT_CONFIGURED"), (503, "AI_UNAVAILABLE"), (503, "AI_AUTH_FAILED"), (429, "AI_RATE_LIMITED"),
    (429, "AI_ANALYSIS_COOLDOWN"), (504, "AI_TIMEOUT"), (502, "AI_INVALID_RESPONSE"), (422, "AI_INSUFFICIENT_DATA"),
])
def test_errors_use_the_standard_shape_and_leak_nothing(client, status, code):
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.generate = AsyncMock(side_effect=AppError(status, code, "A safe message."))
        r = client.post(f"{URL}/generate")
    assert r.status_code == status and r.json() == {"error": {"code": code, "message": "A safe message."}}
    assert "GEMINI_API_KEY" not in r.text and "Traceback" not in r.text


def test_unexpected_failure_is_a_generic_500_without_internals():
    app.dependency_overrides[get_current_user] = lambda: {"_id": "u1", "is_active": True}
    try:
        with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
            svc.return_value.generate = AsyncMock(side_effect=RuntimeError("key=AIza-secret at /srv/app.py line 3"))
            with TestClient(app, raise_server_exceptions=False) as c:
                r = c.post(f"{URL}/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "AIza" not in r.text and "/srv/" not in r.text


def test_response_never_contains_the_api_key(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-test-key")
    with patch("app.api.v1.ai_analysis.AIAnalysisService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_response())
        r = client.get(URL)
    assert "super-secret-test-key" not in r.text


def test_router_is_registered_under_the_api_version():
    from app.api.v1 import api_router

    paths = {r.path for r in api_router.routes}
    assert {"/ai-analysis/{coin_id}", "/ai-analysis/{coin_id}/generate"} <= paths
