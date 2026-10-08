"""
Tests for the shared provider HTTP helper (`app/providers/http.py`).

All external calls are mocked with `respx` — no live network access,
per Step 3's testing requirements. Covers: success, empty response,
malformed JSON, timeout, HTTP 429, HTTP 500.
"""

import asyncio

import httpx
import pytest
import respx

from app.providers.errors import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.http import request_json

URL = "https://example-provider.test/v1/things"


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Keep retry-backoff tests fast — this is a test-speed shim only, never production behavior."""
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


@pytest.mark.asyncio
@respx.mock
async def test_successful_response_returns_json():
    respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as client:
        result = await request_json(client, "GET", URL, provider_name="test")
    assert result == {"ok": True}


@pytest.mark.asyncio
@respx.mock
async def test_empty_json_array_response():
    respx.get(URL).mock(return_value=httpx.Response(200, json=[]))
    async with httpx.AsyncClient() as client:
        result = await request_json(client, "GET", URL, provider_name="test")
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_raises_response_error():
    respx.get(URL).mock(
        return_value=httpx.Response(200, content=b"not json", headers={"content-type": "application/json"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderResponseError):
            await request_json(client, "GET", URL, provider_name="test")


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_provider_timeout_error():
    respx.get(URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderTimeoutError):
            await request_json(client, "GET", URL, provider_name="test")


@pytest.mark.asyncio
@respx.mock
async def test_429_raises_rate_limit_error_without_retry_loop():
    route = respx.get(URL).mock(return_value=httpx.Response(429))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderRateLimitError):
            await request_json(client, "GET", URL, provider_name="test")
    # Must NOT retry a 429 — exactly one request should have been made.
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_500_retries_then_raises_provider_unavailable():
    route = respx.get(URL).mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderUnavailableError):
            await request_json(client, "GET", URL, provider_name="test")
    # Bounded retries — not infinite, and not zero.
    assert 1 < route.call_count <= 3


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_response_error_without_retry():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderResponseError):
            await request_json(client, "GET", URL, provider_name="test")
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_connection_error_raises_provider_unavailable():
    respx.get(URL).mock(side_effect=httpx.ConnectError("connection refused"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderUnavailableError):
            await request_json(client, "GET", URL, provider_name="test")
