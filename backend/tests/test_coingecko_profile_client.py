"""
HTTP-level tests for the Phase 11 CoinGecko profile request and the
404 -> ProviderNotFoundError distinction. External calls mocked with
respx — no live network.
"""

import asyncio

import httpx
import pytest
import respx

from app.providers.coingecko.client import CoinGeckoClient
from app.providers.coingecko.provider import CoinGeckoProvider
from app.providers.errors import ProviderNotFoundError, ProviderResponseError, ProviderUnavailableError
from app.providers.http import request_json

URL = "https://example-provider.test/v1/things"


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


@respx.mock
async def test_404_raises_not_found_which_is_still_a_response_error():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderNotFoundError) as exc:
            await request_json(client, "GET", URL, provider_name="test")
    assert isinstance(exc.value, ProviderResponseError)  # existing handlers/tests keep working
    assert route.call_count == 1  # not retried


@respx.mock
async def test_other_4xx_is_not_reported_as_not_found():
    respx.get(URL).mock(return_value=httpx.Response(400))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderResponseError) as exc:
            await request_json(client, "GET", URL, provider_name="test")
    assert not isinstance(exc.value, ProviderNotFoundError)


@respx.mock
async def test_profile_request_disables_market_data_and_tickers():
    client = CoinGeckoClient()
    base = client._base_url
    route = respx.get(f"{base}/coins/examplecoin").mock(
        return_value=httpx.Response(200, json={"id": "examplecoin"})
    )
    async with httpx.AsyncClient() as http_client:
        data = await client.get_coin_detail(http_client, "examplecoin")

    assert data == {"id": "examplecoin"}
    params = route.calls.last.request.url.params
    assert params["market_data"] == "false"
    assert params["tickers"] == "false"
    assert params["developer_data"] == "true" and params["community_data"] == "true"


@respx.mock
async def test_provider_returns_mapped_profile():
    base = CoinGeckoClient()._base_url
    respx.get(f"{base}/coins/examplecoin").mock(return_value=httpx.Response(200, json={
        "id": "examplecoin", "categories": ["Layer 1 (L1)"], "genesis_date": "2015-01-01",
        "links": {"repos_url": {"github": ["https://github.com/example/core"]}},
    }))
    profile = await CoinGeckoProvider().get_coin_profile("examplecoin")
    assert profile.coingecko_id == "examplecoin"
    assert profile.github_repos == ["https://github.com/example/core"]
    assert profile.genesis_date == "2015-01-01"


@respx.mock
async def test_provider_returns_none_for_an_empty_payload():
    base = CoinGeckoClient()._base_url
    respx.get(f"{base}/coins/ghost").mock(return_value=httpx.Response(200, json={}))
    assert await CoinGeckoProvider().get_coin_profile("ghost") is None


@respx.mock
async def test_provider_failure_propagates_as_provider_error():
    base = CoinGeckoClient()._base_url
    respx.get(f"{base}/coins/examplecoin").mock(return_value=httpx.Response(500))
    with pytest.raises(ProviderUnavailableError):
        await CoinGeckoProvider().get_coin_profile("examplecoin")


def test_provider_declares_profile_support_and_other_providers_do_not():
    from app.providers.binance.provider import BinanceProvider

    assert CoinGeckoProvider.supports_coin_profile is True
    assert BinanceProvider.supports_coin_profile is False
