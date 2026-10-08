"""AIAnalysisService (Phase 15): caching, cooldown, dedupe, backoff, failures, insufficient data.

Every collaborator is an in-memory fake: no MongoDB, no providers, no Gemini, no network.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

import app.services.ai_analysis_service as svc_mod
from app.ai.payload import unavailable
from app.ai.prompts.market_analysis_prompt import PROMPT_VERSION
from app.config.settings import Settings
from app.core.exceptions import AppError
from app.services.ai_analysis_service import AIAnalysisService, decision_changed_materially
from app.services.gemini_service import (
    GeminiRateLimitedError, GeminiResult, GeminiTimeoutError, GeminiUnavailableError,
)
from tests.ai_fixtures import COIN_ID, available_payload, decision_response, good_output


class FakeRepo:
    def __init__(self):
        self.docs: list[dict] = []

    async def insert(self, doc):
        self.docs.append(doc)

    async def get_latest(self, coin_id, *, prompt_version=None, model=None):
        docs = [d for d in self.docs if d["coin_id"] == coin_id
                and (prompt_version is None or d["prompt_version"] == prompt_version)
                and (model is None or d["model"] == model)]
        return max(docs, key=lambda d: d["generated_at"]) if docs else None


class FakeCoins:
    async def find_by_internal_id(self, coin_id):
        return {"symbol": "BTC", "name": "Bitcoin"} if coin_id == COIN_ID else None


class FakeDecisions:
    def __init__(self, decision):
        self.decision = decision
        self.stored = decision
        self.calls = 0

    async def get_decision(self, coin_id, force_refresh=False):
        self.calls += 1
        return self.decision

    async def get_latest(self, coin_id):
        if self.stored is None:
            raise AppError(404, "DECISION_NOT_FOUND", "none")
        return self.stored


class FakeGemini:
    model = "gemini-3.1-flash-lite"

    def __init__(self, configured=True):
        self.is_configured = configured
        self.calls = 0
        self.error = None
        self.payloads = []

    async def generate_analysis(self, payload):
        self.calls += 1
        self.payloads.append(payload)
        await asyncio.sleep(0.01)
        if self.error:
            raise self.error
        return GeminiResult(output=good_output(), model=self.model, model_version="v1", latency_ms=12, attempts=1,
                            prompt_tokens=10, output_tokens=20)


class Boom:
    """A module service whose every method fails (-> that input is reported unavailable)."""

    def __getattr__(self, name):
        async def fail(*a, **k):
            raise AppError(503, "X", "That module is temporarily unavailable.")
        return fail


class NoMarket:
    async def get_by_coin_id(self, coin_oid):
        return None


@pytest.fixture(autouse=True)
def reset_module_state():
    svc_mod._locks.clear()
    svc_mod._failures.clear()
    svc_mod._semaphore = None
    yield
    svc_mod._locks.clear()
    svc_mod._failures.clear()


def build(decision=None, gemini=None, with_payload=True, **settings):
    decisions = FakeDecisions(decision if decision is not None else decision_response())
    gemini = gemini or FakeGemini()
    repo = FakeRepo()
    service = AIAnalysisService(
        repository=repo, coin_repository=FakeCoins(), market_data_repository=NoMarket(), decision_service=decisions,
        technical_service=Boom(), fundamental_service=Boom(), sentiment_service=Boom(), news_service=Boom(),
        prediction_service=Boom(), gemini_service=gemini, settings=Settings(**settings),
    )
    if with_payload:
        service._gather_payload = AsyncMock(return_value=available_payload())  # type: ignore[method-assign]
    return service, repo, decisions, gemini


def age(repo, seconds):
    """Pretend the stored analysis was generated `seconds` ago (and expires accordingly)."""
    doc = repo.docs[-1]
    doc["generated_at"] = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    doc["expires_at"] = doc["generated_at"] + timedelta(seconds=1800)


async def test_generates_stores_and_explains_the_official_decision():
    service, repo, _, gemini = build()
    out = await service.generate(COIN_ID)

    assert gemini.calls == 1 and len(repo.docs) == 1 and out.cached is False
    assert out.model == "gemini-3.1-flash-lite" and out.prompt_version == PROMPT_VERSION
    # The official decision comes from the Phase 14 result, not from Gemini.
    assert out.decision_snapshot.decision == "BUY" and out.decision_snapshot.risk_level == "LOW"
    assert out.decision_snapshot.confidence == 78.0 and out.decision_snapshot.decision_score == 68.0
    assert out.analysis.summary and out.analysis.disclaimer.startswith("AI-generated analysis")
    doc = repo.docs[0]
    for key in ("coin_id", "model", "model_version", "prompt_version", "analysis", "source_data_timestamp",
                "generated_at", "expires_at", "status"):
        assert key in doc
    assert doc["status"] == "ready" and doc["expires_at"] > doc["generated_at"]


async def test_second_request_is_served_from_cache_without_calling_gemini():
    service, repo, _, gemini = build()
    await service.generate(COIN_ID)
    again = await service.generate(COIN_ID)
    assert gemini.calls == 1 and again.cached is True and len(repo.docs) == 1


async def test_get_latest_never_calls_gemini():
    service, repo, _, gemini = build()
    with pytest.raises(AppError) as exc:
        await service.get_latest(COIN_ID)
    assert exc.value.status_code == 404 and exc.value.code == "AI_ANALYSIS_NOT_FOUND"
    await service.generate(COIN_ID)
    got = await service.get_latest(COIN_ID)
    assert got.cached is True and gemini.calls == 1


async def test_concurrent_requests_share_one_gemini_call():
    service, _, _, gemini = build()
    results = await asyncio.gather(*(service.generate(COIN_ID) for _ in range(4)))
    assert gemini.calls == 1 and len(results) == 4


async def test_forced_regeneration_inside_cooldown_is_refused():
    service, _, _, gemini = build()
    await service.generate(COIN_ID)
    with pytest.raises(AppError) as exc:
        await service.generate(COIN_ID, force=True)
    assert exc.value.status_code == 429 and exc.value.code == "AI_ANALYSIS_COOLDOWN" and gemini.calls == 1


async def test_forced_regeneration_after_cooldown_calls_gemini_again():
    service, repo, _, gemini = build()
    await service.generate(COIN_ID)
    age(repo, 120)
    out = await service.generate(COIN_ID, force=True)
    assert gemini.calls == 2 and out.cached is False and len(repo.docs) == 2


async def test_concurrent_forced_regenerations_after_cooldown_share_one_new_call():
    service, repo, _, gemini = build()
    await service.generate(COIN_ID)
    age(repo, 120)
    results = await asyncio.gather(*(service.generate(COIN_ID, force=True) for _ in range(3)))
    assert gemini.calls == 2 and len(repo.docs) == 2 and len(results) == 3


async def test_expired_analysis_is_regenerated_after_cooldown():
    service, repo, _, gemini = build()
    await service.generate(COIN_ID)
    age(repo, 4000)
    out = await service.generate(COIN_ID)
    assert gemini.calls == 2 and out.cached is False


async def test_decision_change_marks_the_stored_analysis_outdated_and_regenerates():
    service, repo, decisions, gemini = build()
    await service.generate(COIN_ID)                       # explains BUY
    decisions.stored = decisions.decision = decision_response(decision="SELL", decision_score=-50.0, risk_level="HIGH", risk_score=70.0)

    latest = await service.get_latest(COIN_ID)
    assert latest.is_outdated is True and latest.decision_snapshot.decision == "BUY"   # still says what it explained

    within_cooldown = await service.generate(COIN_ID)       # too recent to spend another call
    assert gemini.calls == 1 and within_cooldown.is_outdated is True

    age(repo, 120)
    fresh = await service.generate(COIN_ID)
    assert gemini.calls == 2 and fresh.decision_snapshot.decision == "SELL" and fresh.is_outdated is False


def test_material_change_rules():
    base = decision_response()
    snap = {"decision": "BUY", "status": "VALID", "risk_level": "LOW", "decision_score": 68.0, "confidence": 78.0}
    assert decision_changed_materially(snap, base) is False
    assert decision_changed_materially(snap, None) is False
    assert decision_changed_materially(snap, decision_response(decision="HOLD")) is True
    assert decision_changed_materially(snap, decision_response(risk_level="HIGH")) is True
    assert decision_changed_materially(snap, decision_response(decision_score=60.0)) is False      # small drift
    assert decision_changed_materially(snap, decision_response(decision_score=40.0)) is True       # large drift


async def test_missing_api_key_is_a_clean_error_but_stored_analysis_stays_readable():
    service, repo, _, gemini = build()
    await service.generate(COIN_ID)
    gemini.is_configured = False
    age(repo, 4000)
    with pytest.raises(AppError) as exc:
        await service.generate(COIN_ID)
    assert exc.value.status_code == 503 and exc.value.code == "AI_NOT_CONFIGURED"
    assert (await service.get_latest(COIN_ID)).is_stale is True


async def test_never_configured_and_nothing_stored():
    service, repo, _, gemini = build(gemini=FakeGemini(configured=False))
    with pytest.raises(AppError) as exc:
        await service.generate(COIN_ID)
    assert exc.value.code == "AI_NOT_CONFIGURED" and gemini.calls == 0 and repo.docs == []


@pytest.mark.parametrize("error,status,code", [
    (GeminiUnavailableError(), 503, "AI_UNAVAILABLE"),
    (GeminiTimeoutError(), 504, "AI_TIMEOUT"),
])
async def test_gemini_failures_become_app_errors_and_store_nothing(error, status, code):
    gemini = FakeGemini()
    gemini.error = error
    service, repo, _, _ = build(gemini=gemini)
    with pytest.raises(AppError) as exc:
        await service.generate(COIN_ID)
    assert exc.value.status_code == status and exc.value.code == code and repo.docs == []


async def test_rate_limit_is_respected_with_a_backoff_that_prevents_more_calls():
    gemini = FakeGemini()
    gemini.error = GeminiRateLimitedError(retry_after_seconds=30)
    service, repo, _, _ = build(gemini=gemini)
    with pytest.raises(AppError) as first:
        await service.generate(COIN_ID)
    assert first.value.status_code == 429 and first.value.code == "AI_RATE_LIMITED"
    with pytest.raises(AppError) as second:
        await service.generate(COIN_ID)
    assert second.value.status_code == 429 and gemini.calls == 1 and repo.docs == []


async def test_failure_backoff_is_per_coin_and_short():
    gemini = FakeGemini()
    gemini.error = GeminiUnavailableError()
    service, _, _, _ = build(gemini=gemini)
    with pytest.raises(AppError):
        await service.generate(COIN_ID)
    with pytest.raises(AppError):
        await service.generate(COIN_ID)
    assert gemini.calls == 1                       # the second request did not hit Gemini again
    svc_mod._failures[COIN_ID] = (0.0, GeminiUnavailableError())   # backoff elapsed
    gemini.error = None
    assert (await service.generate(COIN_ID)).cached is False


async def test_insufficient_data_is_reported_without_calling_gemini():
    service, repo, _, gemini = build(with_payload=False)   # real loaders: everything fails / no market snapshot
    with pytest.raises(AppError) as exc:
        await service.generate(COIN_ID)
    assert exc.value.status_code == 422 and exc.value.code == "AI_INSUFFICIENT_DATA"
    assert "Unavailable" in exc.value.message and gemini.calls == 0 and repo.docs == []


async def test_unavailable_inputs_are_passed_to_gemini_as_unavailable_not_as_defaults():
    service, _, _, gemini = build()
    payload = available_payload()
    payload["prediction"] = unavailable("Prediction engine unavailable")
    service._gather_payload = AsyncMock(return_value=payload)  # type: ignore[method-assign]
    out = await service.generate(COIN_ID)
    assert gemini.payloads[0]["prediction"] == {"available": False, "reason": "Prediction engine unavailable"}
    assert out.data_availability["prediction"].available is False
    assert out.data_availability["prediction"].reason == "Prediction engine unavailable"
    assert out.data_availability["market"].available is True


async def test_invalid_coin_ids_are_rejected_before_any_work():
    service, _, decisions, gemini = build()
    with pytest.raises(AppError) as bad:
        await service.generate("not-an-id")
    assert bad.value.status_code == 400
    with pytest.raises(AppError) as missing:
        await service.generate("507f1f77bcf86cd799439099")
    assert missing.value.status_code == 404 and gemini.calls == 0 and decisions.calls == 0


async def test_a_decision_with_no_result_is_explained_as_unavailable_not_invented():
    d = decision_response(decision=None, status="INSUFFICIENT_DATA", status_reason="Only 1 of 4 modules usable.",
                          decision_score=None, raw_score=None, risk_adjustment=None, confidence=None,
                          confidence_status="unavailable", risk_score=None, risk_level=None)
    service, _, _, _ = build(decision=d)
    out = await service.generate(COIN_ID)
    assert out.decision_snapshot.decision is None and out.decision_snapshot.status == "INSUFFICIENT_DATA"
