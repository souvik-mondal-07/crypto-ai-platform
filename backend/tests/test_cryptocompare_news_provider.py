"""HTTP behaviour of the CryptoCompare news provider (respx-mocked; no network)."""

from datetime import timedelta

import httpx
import pytest
import respx

from app.providers.errors import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.news.cryptocompare import CryptoCompareNewsProvider
from tests.news_fixtures import NOW, raw_article

URL = "https://min-api.cryptocompare.com/data/v2/news/"


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    async def instant(_):  # keep retry tests fast
        return None

    monkeypatch.setattr("app.providers.http.asyncio.sleep", instant)


@respx.mock
async def test_fetches_and_normalizes():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"Data": [raw_article()]}))
    result = await CryptoCompareNewsProvider().fetch_latest()
    assert len(result.articles) == 1
    params = route.calls.last.request.url.params
    assert params["lang"] == "EN" and params["sortOrder"] == "latest" and "lTs" not in params


@respx.mock
async def test_pages_backwards_with_lts():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"Data": []}))
    await CryptoCompareNewsProvider().fetch_latest(before=NOW - timedelta(hours=1))
    assert route.calls.last.request.url.params["lTs"] == str(int((NOW - timedelta(hours=1)).timestamp()))


@respx.mock
async def test_api_key_is_sent_as_header_only_when_configured(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "CRYPTOCOMPARE_API_KEY", "")
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"Data": []}))
    await CryptoCompareNewsProvider().fetch_latest()
    assert "authorization" not in route.calls.last.request.headers

    monkeypatch.setattr(get_settings(), "CRYPTOCOMPARE_API_KEY", "test-key")
    await CryptoCompareNewsProvider().fetch_latest()
    request = route.calls.last.request
    assert request.headers["authorization"] == "Apikey test-key"
    assert "test-key" not in str(request.url)  # never in the URL


@respx.mock
async def test_http_429_is_a_rate_limit_error():
    respx.get(URL).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        await CryptoCompareNewsProvider().fetch_latest()


@respx.mock
async def test_5xx_is_unavailable_and_malformed_json_is_bad_response():
    respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ProviderUnavailableError):
        await CryptoCompareNewsProvider().fetch_latest()
    respx.get(URL).mock(return_value=httpx.Response(200, content=b"<html>not json"))
    with pytest.raises(ProviderResponseError):
        await CryptoCompareNewsProvider().fetch_latest()
