"""
Application-level exceptions and their FastAPI handlers.

Routes/services raise `AppError` (or let a `ProviderError` bubble up)
instead of returning ad-hoc error shapes — the handlers registered
here guarantee every error response follows the same
`{"error": {"code", "message"}}` shape and never leaks a raw
traceback or internal exception detail to the client.
"""

import logging
import math
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.providers.errors import (
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger("crypto_ai_platform.errors")


class AppError(Exception):
    """Raised by services/routes for any expected, user-facing error."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _json_safe(value: Any) -> Any:
    """
    Make validation-error details strictly JSON-compliant. Pydantic echoes the offending `input` back in
    each error, so a request containing NaN / Infinity / -Infinity would otherwise make the response
    itself unserializable (`ValueError: Out of range float values are not JSON compliant`). Non-finite
    floats are replaced with their text form ("NaN", "Infinity", "-Infinity"); strict JSON stays on.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Same shape as FastAPI's default 422 (`{"detail": [...]}`), just guaranteed JSON-safe.
        return JSONResponse(status_code=422, content={"detail": _json_safe(jsonable_encoder(exc.errors()))})

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(ProviderRateLimitError)
    async def handle_rate_limit(_: Request, exc: ProviderRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=_error_body("PROVIDER_RATE_LIMITED", "Market data provider rate limit exceeded. Try again shortly."),
        )

    @app.exception_handler(ProviderTimeoutError)
    async def handle_timeout(_: Request, exc: ProviderTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=504,
            content=_error_body("PROVIDER_TIMEOUT", "Market data provider did not respond in time."),
        )

    @app.exception_handler(ProviderUnavailableError)
    async def handle_unavailable(_: Request, exc: ProviderUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_body("PROVIDER_UNAVAILABLE", "Market data provider is temporarily unavailable."),
        )

    @app.exception_handler(ProviderResponseError)
    async def handle_bad_response(_: Request, exc: ProviderResponseError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=_error_body("PROVIDER_BAD_RESPONSE", "Market data provider returned an unexpected response."),
        )

    @app.exception_handler(ProviderError)
    async def handle_generic_provider_error(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_error_body("PROVIDER_ERROR", "Market data provider request failed."),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Never leak a raw traceback or exception message to the
        # client — log the real detail server-side only.
        logger.exception("Unhandled exception: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
