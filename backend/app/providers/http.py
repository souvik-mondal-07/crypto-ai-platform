"""
Shared async HTTP helper for provider clients.

Centralizes timeout configuration, bounded retry behavior, and
consistent translation of transport/HTTP failures into the
`ProviderError` hierarchy — provider clients call `request_json()`
instead of using `httpx` directly, so this behavior isn't duplicated
per-provider.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.providers.errors import (
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger("crypto_ai_platform.providers")

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    provider_name: str = "unknown",
) -> Any:
    """
    Issue a request and return its parsed JSON body.

    Retries up to `MAX_RETRIES` times on timeouts and 5xx responses
    only (never on 429 — a rate limit needs backoff the caller/service
    controls, not an immediate hammering retry, and never on 4xx other
    than 429 since retrying a bad request won't fix it). Raises a
    `ProviderError` subclass on any failure that survives retries —
    never lets a raw httpx exception escape to the service layer.
    """
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.request(
                method, url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
            )
        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning(
                "%s request timed out (attempt %d/%d): %s",
                provider_name, attempt + 1, MAX_RETRIES + 1, url,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise ProviderTimeoutError(f"{provider_name} request timed out: {url}") from exc
        except httpx.HTTPError as exc:
            # Connection errors, DNS failures, etc.
            raise ProviderUnavailableError(f"{provider_name} is unreachable: {exc.__class__.__name__}") from exc

        if response.status_code == 429:
            # Never auto-retry a 429 in a loop — surface it so the
            # caller can decide (skip this sync run, back off, etc.)
            # rather than hammering an already-throttled provider.
            logger.warning("%s rate limit hit (429): %s", provider_name, url)
            raise ProviderRateLimitError(f"{provider_name} rate limit exceeded")

        if response.status_code >= 500:
            last_error = ProviderUnavailableError(
                f"{provider_name} returned {response.status_code}"
            )
            logger.warning(
                "%s returned %d (attempt %d/%d): %s",
                provider_name, response.status_code, attempt + 1, MAX_RETRIES + 1, url,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise last_error

        if response.status_code == 404:
            raise ProviderNotFoundError(f"{provider_name} returned 404 for {url}")

        if response.status_code >= 400:
            raise ProviderResponseError(
                f"{provider_name} returned {response.status_code} for {url}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError(f"{provider_name} returned malformed JSON") from exc

    # Unreachable, but keeps type-checkers happy.
    raise ProviderUnavailableError(f"{provider_name} request failed: {last_error}")
