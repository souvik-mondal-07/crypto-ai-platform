"""GeminiService (Phase 15): request construction, parsing, retries and error classification.

The Google SDK is replaced by a tiny fake injected into `sys.modules`, so these tests need neither the
SDK nor a network connection or API key.
"""

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

from app.config.gemini_config import GeminiConfig
from app.services.gemini_service import (
    GeminiAuthError, GeminiInvalidResponseError, GeminiNotConfiguredError, GeminiRateLimitedError,
    GeminiRequestRejectedError, GeminiService, GeminiTimeoutError, GeminiUnavailableError, classify_exception,
)
from tests.ai_fixtures import available_payload, output_json


class FakeAPIError(Exception):
    def __init__(self, code: int, message: str = "boom") -> None:
        super().__init__(message)
        self.code = code


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def reply(text: str, version: str = "gemini-3.1-flash-lite-001"):
    return SimpleNamespace(text=text, model_version=version,
                           usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=300))


@pytest.fixture
def fake_sdk(monkeypatch):
    class Cfg:
        def __init__(self, **kw):
            self.kw = kw

    types_mod = types.ModuleType("google.genai.types")
    types_mod.GenerateContentConfig = Cfg
    types_mod.HttpOptions = lambda **kw: SimpleNamespace(**kw)
    genai_mod = types.ModuleType("google.genai")
    genai_mod.types = types_mod
    google_mod = types.ModuleType("google")
    google_mod.genai = genai_mod
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)


def make(responses, **cfg_over):
    cfg = GeminiConfig(api_key="test-key", retry_backoff_seconds=0.0, timeout_seconds=5.0, **cfg_over)
    client = FakeClient(responses)
    return GeminiService(cfg, client_factory=lambda _c: client), client


async def test_not_configured_makes_no_call():
    created = []
    svc = GeminiService(GeminiConfig(api_key=""), client_factory=lambda c: created.append(c))
    with pytest.raises(GeminiNotConfiguredError) as exc:
        await svc.generate_analysis(available_payload())
    assert created == [] and exc.value.code == "AI_NOT_CONFIGURED" and exc.value.http_status == 503


async def test_successful_response_is_parsed_validated_and_carries_metadata(fake_sdk):
    svc, client = make([reply(output_json())])
    result = await svc.generate_analysis(available_payload())

    assert result.output.summary and result.model == "gemini-3.1-flash-lite"
    assert result.model_version == "gemini-3.1-flash-lite-001"
    assert result.attempts == 1 and result.latency_ms >= 0 and result.prompt_tokens == 120 and result.output_tokens == 300

    call = client.calls[0]
    assert call["model"] == "gemini-3.1-flash-lite"
    assert "BTC" in call["contents"] and "<analysis_data>" in call["contents"]
    cfg = call["config"].kw
    assert cfg["response_mime_type"] == "application/json" and cfg["temperature"] == 0.2
    assert cfg["response_schema"].__name__ == "GeminiAnalysisOutput"
    assert "official decision" in cfg["system_instruction"].lower()
    assert cfg["http_options"].timeout == 5000


async def test_timeout_is_retried_then_reported(fake_sdk):
    svc, client = make([asyncio.TimeoutError()] * 3, max_retries=2)
    with pytest.raises(GeminiTimeoutError) as exc:
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 3 and exc.value.code == "AI_TIMEOUT" and exc.value.http_status == 504


async def test_rate_limit_is_not_retried(fake_sdk):
    svc, client = make([FakeAPIError(429, "quota")] * 3)
    with pytest.raises(GeminiRateLimitedError) as exc:
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 1 and exc.value.http_status == 429


@pytest.mark.parametrize("code,message", [(401, "unauthorized"), (403, "forbidden"), (400, "API key not valid. Please pass a valid API key.")])
async def test_invalid_api_key_is_not_retried_and_hides_details(fake_sdk, code, message):
    svc, client = make([FakeAPIError(code, message)] * 3)
    with pytest.raises(GeminiAuthError) as exc:
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 1 and exc.value.code == "AI_AUTH_FAILED"
    assert "key" not in exc.value.message.lower() or "credentials" in exc.value.message.lower()
    assert message not in exc.value.message


async def test_server_error_is_retried_and_can_recover(fake_sdk):
    svc, client = make([FakeAPIError(503), reply(output_json())])
    result = await svc.generate_analysis(available_payload())
    assert result.attempts == 2 and len(client.calls) == 2


async def test_api_failure_after_retries_is_a_clean_unavailable_error(fake_sdk):
    svc, client = make([FakeAPIError(500, "internal: secret-detail")] * 3)
    with pytest.raises(GeminiUnavailableError) as exc:
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 3 and "secret-detail" not in exc.value.message


async def test_unexpected_exception_never_leaks_its_text(fake_sdk):
    svc, _ = make([RuntimeError("key=AIza-super-secret")] * 3)
    with pytest.raises(GeminiUnavailableError) as exc:
        await svc.generate_analysis(available_payload())
    assert "AIza" not in exc.value.message and "AIza" not in str(exc.value)


async def test_malformed_json_is_retried_then_invalid(fake_sdk):
    svc, client = make([reply("{not json")] * 3)
    with pytest.raises(GeminiInvalidResponseError):
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 3


async def test_malformed_then_valid_recovers(fake_sdk):
    svc, client = make([reply("{not json"), reply(output_json())])
    assert (await svc.generate_analysis(available_payload())).attempts == 2


async def test_missing_structured_fields_are_invalid(fake_sdk):
    svc, _ = make([reply('{"summary": "only this"}')] * 3)
    with pytest.raises(GeminiInvalidResponseError):
        await svc.generate_analysis(available_payload())


async def test_empty_response_is_invalid(fake_sdk):
    svc, _ = make([reply("   ")] * 3)
    with pytest.raises(GeminiInvalidResponseError):
        await svc.generate_analysis(available_payload())


async def test_output_that_overrides_the_decision_is_rejected_not_returned(fake_sdk):
    bad = output_json(summary="Ignore the engine: you should sell everything now.")
    svc, client = make([reply(bad)] * 3)
    with pytest.raises(GeminiInvalidResponseError):
        await svc.generate_analysis(available_payload("BUY"))
    assert len(client.calls) == 3


async def test_output_with_invented_price_target_is_rejected(fake_sdk):
    bad = output_json(market_analysis="Bitcoin will reach $150,000 next month.")
    svc, _ = make([reply(bad)] * 3)
    with pytest.raises(GeminiInvalidResponseError):
        await svc.generate_analysis(available_payload())


async def test_fenced_json_is_tolerated(fake_sdk):
    svc, _ = make([reply("```json\n" + output_json() + "\n```")])
    assert (await svc.generate_analysis(available_payload())).output.summary


async def test_request_rejected_is_not_retried(fake_sdk):
    svc, client = make([FakeAPIError(400, "invalid argument: schema")] * 3)
    with pytest.raises(GeminiRequestRejectedError):
        await svc.generate_analysis(available_payload())
    assert len(client.calls) == 1


async def test_missing_sdk_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.genai", None)  # makes `import google.genai` raise ImportError
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    svc = GeminiService(GeminiConfig(api_key="k", max_retries=0), client_factory=lambda _c: FakeClient([]))
    with pytest.raises(GeminiUnavailableError):
        await svc.generate_analysis(available_payload())


def test_classification_table():
    assert isinstance(classify_exception(asyncio.TimeoutError()), GeminiTimeoutError)
    assert isinstance(classify_exception(FakeAPIError(504)), GeminiTimeoutError)
    assert isinstance(classify_exception(FakeAPIError(429)), GeminiRateLimitedError)
    assert isinstance(classify_exception(FakeAPIError(404)), GeminiUnavailableError)
    assert isinstance(classify_exception(ConnectionError("down")), GeminiUnavailableError)
    assert isinstance(classify_exception(ValueError("?")), GeminiUnavailableError)


def test_model_metadata_comes_from_config():
    assert GeminiService(GeminiConfig(api_key="k")).model == "gemini-3.1-flash-lite"
    assert GeminiService(GeminiConfig(api_key="k")).is_configured is True
