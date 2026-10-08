"""Phase 15 must not change or depend on the core engines: Gemini explains, it never decides."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config.risk_config import DEFAULT_ENGINE_CONFIG
from app.core.exceptions import AppError
from app.main import app
from app.services.decision_engine import evaluate
from tests.ai_fixtures import COIN_ID, decision_response
from tests.decision_fixtures import bearish_inputs, bullish_inputs

APP = Path(__file__).resolve().parents[1] / "app"


def test_decision_engine_works_with_no_gemini_key_and_is_deterministic(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    buy = evaluate(bullish_inputs(), DEFAULT_ENGINE_CONFIG)
    sell = evaluate(bearish_inputs(), DEFAULT_ENGINE_CONFIG)
    assert buy.decision == "BUY" and sell.decision == "SELL"
    assert evaluate(bullish_inputs(), DEFAULT_ENGINE_CONFIG).decision_score == buy.decision_score


def test_core_engines_do_not_import_the_ai_layer():
    core = ["decision_engine.py", "risk_service.py", "decision_service.py", "decision_inputs.py", "scoring.py",
            "technical_analysis_service.py", "fundamental_analysis_service.py", "prediction_service.py", "sentiment_service.py"]
    for name in core:
        text = (APP / "services" / name).read_text(encoding="utf-8").lower()
        for word in ("gemini", "app.ai", "ai_analysis", "genai"):
            assert word not in text, (name, word)
    assert "gemini" not in (APP / "config" / "risk_config.py").read_text(encoding="utf-8").lower()


def test_decisions_endpoint_still_works_when_the_ai_service_is_down():
    with patch("app.api.v1.decisions.DecisionService") as decisions, \
         patch("app.api.v1.ai_analysis.AIAnalysisService") as ai:
        decisions.return_value.get_decision = AsyncMock(return_value=decision_response())
        ai.return_value.get_latest = AsyncMock(side_effect=AppError(503, "AI_UNAVAILABLE", "The AI service is temporarily unavailable."))
        with TestClient(app) as c:
            ai_resp = c.get(f"/api/v1/ai-analysis/{COIN_ID}")
            decision_resp = c.get(f"/api/v1/decisions/{COIN_ID}")
    assert ai_resp.status_code == 503
    assert decision_resp.status_code == 200 and decision_resp.json()["decision"] == "BUY"


def test_ai_layer_has_no_write_path_to_the_decision_collection():
    for p in list((APP / "ai").rglob("*.py")) + [APP / "services" / "ai_analysis_service.py", APP / "services" / "gemini_service.py"]:
        text = p.read_text(encoding="utf-8")
        assert "DecisionRepository" not in text and "decisions.insert" not in text, p.name
