"""Static checks for Phase 14 wiring: existing `decisions` collection, indexes, settings, env examples, no Gemini."""

from pathlib import Path

from app.config.settings import Settings

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"


def test_decisions_use_the_existing_collection_and_indexes_are_declared():
    from app.database.collections import CollectionName

    assert CollectionName.DECISIONS.value == "decisions"
    src = (APP / "database" / "indexes.py").read_text(encoding="utf-8")
    assert "idx_decisions_coin_generatedat" in src and "idx_decisions_engineversion_generatedat" in src
    assert "expireAfterSeconds" not in src                       # decisions are kept for history
    assert not [c for c in CollectionName if "DECISION" in c.name and c is not CollectionName.DECISIONS]   # no duplicate collection


def test_decision_settings_default_and_are_documented():
    assert Settings().DECISION_PREDICTION_TIMEOUT_SECONDS > 0
    for path in (REPO / ".env.example", REPO / "backend" / ".env.example"):
        assert "DECISION_PREDICTION_TIMEOUT_SECONDS=" in path.read_text(encoding="utf-8")


def test_router_is_registered_under_the_api_version():
    from app.api.v1 import api_router

    paths = {r.path for r in api_router.routes}
    assert {"/decisions/{coin_id}", "/decisions/{coin_id}/latest", "/decisions/{coin_id}/risk"} <= paths


def test_phase_14_adds_no_gemini_llm_or_trading_code():
    files = [APP / "services" / n for n in ("decision_engine.py", "risk_service.py", "decision_service.py", "decision_inputs.py", "scoring.py")]
    files += [APP / "config" / "risk_config.py", APP / "api" / "v1" / "decisions.py", APP / "schemas" / "decisions.py",
              APP / "repositories" / "decision_repository.py"]
    for f in files:
        text = f.read_text(encoding="utf-8").lower()
        for forbidden in ("gemini", "google.generativeai", "genai", "openai", "binance.client", "create_order", "place_order", "import random"):
            assert forbidden not in text, (f.name, forbidden)
    # Phase 15 adds the Gemini SDK to requirements.txt (only the AI layer uses it), so this guard stays
    # on the Phase 14 source files above: the decision/risk engines must remain LLM-free.
    req_text = (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8").lower()
    # Only real requirement lines count: a comment explaining "not the legacy google-generativeai package" is fine.
    requirements = [line.split("#")[0].strip() for line in req_text.splitlines()]
    assert not any(line.startswith("google-generativeai") for line in requirements)  # the legacy SDK is never used