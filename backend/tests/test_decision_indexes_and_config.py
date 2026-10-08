"""Static checks for Phase 14 wiring: existing `decisions` collection, indexes, settings, env examples, no Gemini."""

import re
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


PHASE_14_FILES = [
    *[APP / "services" / n for n in ("decision_engine.py", "risk_service.py", "decision_service.py", "decision_inputs.py", "scoring.py")],
    APP / "config" / "risk_config.py", APP / "api" / "v1" / "decisions.py", APP / "schemas" / "decisions.py",
    APP / "repositories" / "decision_repository.py",
]
# Never allowed anywhere in the backend (other AI providers, the legacy Gemini SDK, trading/order APIs).
FORBIDDEN_EVERYWHERE = (
    "google.generativeai", "openai", "anthropic", "ollama", "create_order", "place_order",
)
# The third-party Binance trading SDK. (The project's own `app.providers.binance` market-data provider is fine.)
BINANCE_SDK_IMPORT = re.compile(r"^\s*(?:from|import)\s+binance(?:\.|\s|$)", re.MULTILINE)
FORBIDDEN_PACKAGES = ("google-generativeai", "openai", "anthropic", "ollama", "ccxt", "python-binance")


def test_phase_14_engines_stay_llm_free_and_trading_free():
    """The Phase 14 decision/risk code must not contain any AI-provider or trading code.

    Phase 15 legitimately adds Gemini, but only in the separate AI layer (app/ai, gemini_service,
    ai_analysis_service) — the engines that decide BUY/HOLD/SELL must remain free of it.
    """
    for f in PHASE_14_FILES:
        text = f.read_text(encoding="utf-8").lower()
        for forbidden in ("gemini", "genai", "import random", "binance.client", *FORBIDDEN_EVERYWHERE):
            assert forbidden not in text, (f.name, forbidden)


def test_phase_15_gemini_sdk_is_the_only_ai_dependency_and_is_confined_to_the_ai_layer():
    packages = []
    for line in (REPO / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            packages.append(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0])
    # Allowed: the official Google Gen AI SDK required by Phase 15.
    assert "google-genai" in packages
    for forbidden in FORBIDDEN_PACKAGES:
        assert forbidden not in packages, forbidden

    # Only the Gemini service may import the SDK, and no backend file may use a forbidden provider/trading API.
    importers = []
    for f in APP.rglob("*.py"):
        text = f.read_text(encoding="utf-8").lower()
        if "from google import genai" in text or "from google.genai" in text or "import google.genai" in text:
            importers.append(f.name)
        for forbidden in FORBIDDEN_EVERYWHERE:
            assert forbidden not in text, (f.name, forbidden)
        assert not BINANCE_SDK_IMPORT.search(text), f.name
    assert importers == ["gemini_service.py"]
