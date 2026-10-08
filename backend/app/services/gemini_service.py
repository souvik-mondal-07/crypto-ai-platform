"""Gemini client wrapper (Phase 15) — the ONLY module that talks to the Gemini API.

Responsibilities: client initialisation, request construction (system instruction + structured
output schema), the API call, response parsing/validation, timeout, retries, error classification,
logging and model metadata. Route handlers and the orchestration service never touch the SDK.

Errors are translated into `GeminiError` subclasses with a stable `code` and a USER-SAFE message;
the raw SDK exception (which may echo request details) is only ever logged by class name and status.
Auth and rate-limit errors are never retried; timeouts, 5xx and malformed output are, with backoff.

The official `google-genai` SDK is imported lazily so the application (and its tests) work without
it installed — Gemini is an enhancement layer, never a dependency of the core app.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import ValidationError

from app.ai.prompts.market_analysis_prompt import SYSTEM_INSTRUCTION, build_market_analysis_prompt
from app.ai.schemas.ai_analysis import GeminiAnalysisOutput
from app.ai.validation import AnalysisValidationError, validate_analysis
from app.config.gemini_config import GeminiConfig, get_gemini_config

logger = logging.getLogger("crypto_ai_platform.services.gemini")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GeminiError(Exception):
    """Base class. `code` is machine-readable, `message` is safe to show to a user."""

    code = "AI_ERROR"
    http_status = 502
    retryable = False

    def __init__(self, message: str, *, retry_after_seconds: Optional[float] = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


class GeminiNotConfiguredError(GeminiError):
    code, http_status = "AI_NOT_CONFIGURED", 503

    def __init__(self) -> None:
        super().__init__("AI analysis is not configured on the server.")


class GeminiAuthError(GeminiError):
    code, http_status = "AI_AUTH_FAILED", 503

    def __init__(self) -> None:
        super().__init__("AI analysis is temporarily unavailable (the server's AI credentials were rejected).")


class GeminiRateLimitedError(GeminiError):
    code, http_status = "AI_RATE_LIMITED", 429

    def __init__(self, retry_after_seconds: Optional[float] = None) -> None:
        super().__init__("The AI service is rate limited right now. Please try again shortly.", retry_after_seconds=retry_after_seconds)


class GeminiTimeoutError(GeminiError):
    code, http_status, retryable = "AI_TIMEOUT", 504, True

    def __init__(self) -> None:
        super().__init__("The AI service did not respond in time.")


class GeminiUnavailableError(GeminiError):
    code, http_status, retryable = "AI_UNAVAILABLE", 503, True

    def __init__(self) -> None:
        super().__init__("The AI service is temporarily unavailable.")


class GeminiRequestRejectedError(GeminiError):
    """The API rejected the request itself (4xx other than auth/rate limit): a bug, so never retried."""

    code, http_status = "AI_REQUEST_REJECTED", 502

    def __init__(self) -> None:
        super().__init__("The AI service rejected the analysis request.")


class GeminiInvalidResponseError(GeminiError):
    code, http_status, retryable = "AI_INVALID_RESPONSE", 502, True

    def __init__(self) -> None:
        super().__init__("The AI service returned an unusable response.")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeminiResult:
    output: GeminiAnalysisOutput
    model: str
    model_version: Optional[str]
    latency_ms: int
    attempts: int
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


ClientFactory = Callable[[GeminiConfig], Any]


def _default_client_factory(config: GeminiConfig) -> Any:
    from google import genai  # lazy: only needed when a real call is made

    return genai.Client(api_key=config.api_key)


# ---------------------------------------------------------------------------
# Error classification (SDK-agnostic: looks at the exception's `code` / class name)
# ---------------------------------------------------------------------------


def classify_exception(exc: BaseException) -> GeminiError:
    """Map any exception from the SDK / transport to a GeminiError (never leaks its text)."""
    if isinstance(exc, GeminiError):
        return exc
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return GeminiTimeoutError()
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return GeminiTimeoutError()

    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    text = str(exc).lower()
    if isinstance(code, int):
        if code in (401, 403) or (code == 400 and ("api key" in text or "api_key" in text)):
            return GeminiAuthError()
        if code == 429:
            return GeminiRateLimitedError(_retry_after(exc))
        if code in (408, 504):
            return GeminiTimeoutError()
        if code >= 500 or code in (404,):  # 404 = model id not available to this key
            return GeminiUnavailableError()
        if 400 <= code < 500:
            return GeminiRequestRejectedError()
    if isinstance(status, str) and status.upper() in {"RESOURCE_EXHAUSTED"}:
        return GeminiRateLimitedError(_retry_after(exc))
    if any(k in name for k in ("connect", "network", "transport", "connection", "ssl", "remoteprotocol")):
        return GeminiUnavailableError()
    if isinstance(exc, (ConnectionError, OSError)):
        return GeminiUnavailableError()
    return GeminiUnavailableError()


def _retry_after(exc: BaseException) -> Optional[float]:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    try:
        value = headers.get("retry-after") if headers is not None else None
        return float(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GeminiService:
    def __init__(self, config: Optional[GeminiConfig] = None, client_factory: Optional[ClientFactory] = None) -> None:
        self._config = config or get_gemini_config()
        self._client_factory = client_factory or _default_client_factory
        self._client: Any = None

    # ---- metadata -----------------------------------------------------------------------------

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def is_configured(self) -> bool:
        return self._config.is_configured

    # ---- public API ---------------------------------------------------------------------------

    async def generate_analysis(self, payload: dict[str, Any]) -> GeminiResult:
        """Explain `payload` (see app.ai.payload). Raises GeminiError; never returns unvalidated output."""
        if not self._config.is_configured:
            raise GeminiNotConfiguredError()

        prompt = build_market_analysis_prompt(payload)
        attempts = self._config.max_retries + 1
        started = time.monotonic()
        last_error: GeminiError = GeminiUnavailableError()

        for attempt in range(1, attempts + 1):
            try:
                text, version, usage = await self._call(prompt)
                output = self._parse(text)
                output = validate_analysis(output, payload)
            except AnalysisValidationError as exc:
                # Logged by reason (our own message, no model text) — the prompt/response are not logged.
                logger.warning("Gemini output rejected (attempt %d/%d): %s", attempt, attempts, exc)
                last_error = GeminiInvalidResponseError()
            except GeminiError as exc:
                last_error = exc
            except Exception as exc:  # SDK / transport failures
                last_error = classify_exception(exc)
                logger.warning(
                    "Gemini request failed (attempt %d/%d): type=%s code=%s",
                    attempt, attempts, type(exc).__name__, getattr(exc, "code", None),
                )
            else:
                latency_ms = int((time.monotonic() - started) * 1000)
                logger.info("Gemini analysis generated: model=%s latency_ms=%d attempts=%d", self.model, latency_ms, attempt)
                return GeminiResult(
                    output=output, model=self.model, model_version=version, latency_ms=latency_ms, attempts=attempt,
                    prompt_tokens=usage.get("prompt"), output_tokens=usage.get("output"),
                )

            if not last_error.retryable or attempt == attempts:
                break
            await asyncio.sleep(self._config.retry_backoff_seconds * (2 ** (attempt - 1)))

        logger.error(
            "Gemini analysis failed: model=%s failure=%s attempts=%d latency_ms=%d",
            self.model, last_error.code, attempt, int((time.monotonic() - started) * 1000),
        )
        raise last_error

    # ---- internals ----------------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(self._config)
        return self._client

    async def _call(self, prompt: str) -> tuple[str, Optional[str], dict[str, Optional[int]]]:
        """One API call -> (response text, reported model version, token usage)."""
        from google.genai import types  # lazy import (see module docstring)

        cfg = self._config
        generation_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
            response_mime_type="application/json",
            response_schema=GeminiAnalysisOutput,
            http_options=types.HttpOptions(timeout=int(cfg.timeout_seconds * 1000)),
        )
        client = self._get_client()
        # The SDK timeout covers the HTTP call; wait_for is the hard backstop.
        response = await asyncio.wait_for(
            client.aio.models.generate_content(model=cfg.model, contents=prompt, config=generation_config),
            timeout=cfg.timeout_seconds + 5,
        )
        text = getattr(response, "text", None)
        if not text or not str(text).strip():
            raise GeminiInvalidResponseError()
        usage_meta = getattr(response, "usage_metadata", None)
        usage = {
            "prompt": getattr(usage_meta, "prompt_token_count", None),
            "output": getattr(usage_meta, "candidates_token_count", None),
        }
        return str(text), getattr(response, "model_version", None), usage

    @staticmethod
    def _parse(text: str) -> GeminiAnalysisOutput:
        cleaned = text.strip()
        if cleaned.startswith("```"):  # tolerate a fenced block even though JSON mode should prevent it
            cleaned = cleaned.strip("`")
            cleaned = cleaned[4:] if cleaned.lower().startswith("json") else cleaned
        try:
            return GeminiAnalysisOutput.model_validate(json.loads(cleaned))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Gemini returned malformed structured output: %s", type(exc).__name__)
            raise GeminiInvalidResponseError() from exc


__all__ = [
    "GeminiService", "GeminiResult", "GeminiError", "GeminiNotConfiguredError", "GeminiAuthError",
    "GeminiRateLimitedError", "GeminiTimeoutError", "GeminiUnavailableError", "GeminiInvalidResponseError",
    "GeminiRequestRejectedError",
    "classify_exception",
]
