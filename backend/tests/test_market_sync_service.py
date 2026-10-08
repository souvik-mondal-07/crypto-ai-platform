"""
Unit tests for MarketSyncService's control flow, using fake
repositories and fake providers — no MongoDB, no live HTTP. Exercises
duplicate-prevention (upsert semantics via the fake), pagination
stopping conditions, and provider-failure resilience.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.providers.errors import ProviderUnavailableError
from app.providers.normalized import NormalizedCoin, NormalizedExchangeTicker, NormalizedMarketData
from app.services.market_sync_service import MarketSyncService


class FakeCoinRepository:
    def __init__(self):
        self.by_coingecko_id: dict[str, dict] = {}
        self.deactivate_calls = 0

    async def bulk_upsert_from_coingecko(self, coins):
        matched = 0
        upserted = 0
        for coin in coins:
            existing = self.by_coingecko_id.get(coin.coingecko_id)
            if existing:
                matched += 1
                existing["name"] = coin.name
                existing["market_cap_rank"] = coin.market_cap_rank
            else:
                upserted += 1
                self.by_coingecko_id[coin.coingecko_id] = {
                    "_id": ObjectId(),
                    "name": coin.name,
                    "symbol": coin.symbol,
                    "market_cap_rank": coin.market_cap_rank,
                    "providers": {"coingecko": {"id": coin.coingecko_id, "available": True}},
                }
        return {"matched": matched, "upserted": upserted}

    async def find_by_coingecko_id(self, coingecko_id):
        return self.by_coingecko_id.get(coingecko_id)

    async def deactivate_stale(self, seen_before):
        self.deactivate_calls += 1
        return 0

    async def set_binance_mapping(self, coingecko_id, binance_symbol):
        return coingecko_id in self.by_coingecko_id

    async def list_binance_mapped(self):
        return list(self._binance_mapped) if hasattr(self, "_binance_mapped") else []

    def seed_binance_mapping(self, coin_object_id, symbol):
        """Test helper — not part of the real repository's interface."""
        if not hasattr(self, "_binance_mapped"):
            self._binance_mapped = []
        self._binance_mapped.append((coin_object_id, symbol))

    class _FakeCollection:
        async def find_one(self, *_args, **_kwargs):
            return None

    @property
    def collection(self):
        return self._FakeCollection()


class FakeMarketDataRepository:
    def __init__(self):
        self.upserted_entries = []
        self.binance_upserted_entries = []

    async def bulk_upsert(self, entries, data_source):
        self.upserted_entries.extend(entries)
        return {"matched": 0, "upserted": len(entries)}

    async def bulk_upsert_binance_prices(self, entries, data_source="binance"):
        self.binance_upserted_entries.extend(entries)
        return {"matched": 0, "upserted": len(entries)}


class FakeCoinGeckoProvider:
    """Returns two coins on page 1, empty on page 2 (end of data)."""

    def __init__(self, universe=None, pages=None, fail_on_page=None):
        self._universe = universe or []
        self._pages = pages or {}
        self._fail_on_page = fail_on_page

    async def list_full_universe(self, http_client):
        return self._universe

    async def list_coins_with_market_data(self, http_client, page, per_page):
        if self._fail_on_page == page:
            raise ProviderUnavailableError("simulated failure")
        return self._pages.get(page, [])


class FakeBinanceProvider:
    def __init__(self, tickers=None, fail=False):
        self._tickers = tickers or []
        self._fail = fail

    async def list_trading_pairs(self):
        return []

    async def get_exchange_tickers(self):
        if self._fail:
            raise ProviderUnavailableError("simulated Binance outage")
        return self._tickers


def _pair(coingecko_id: str, name: str) -> tuple:
    coin = NormalizedCoin(coingecko_id=coingecko_id, symbol=coingecko_id.upper(), name=name)
    market = NormalizedMarketData(coingecko_id=coingecko_id, price_usd=100.0, percent_change_24h=1.0)
    return coin, market


@pytest.mark.asyncio
async def test_sync_stops_pagination_on_empty_page():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    provider = FakeCoinGeckoProvider(pages={1: [_pair("bitcoin", "Bitcoin")], 2: []})

    service = MarketSyncService(
        coin_repository=coins_repo,
        market_data_repository=market_repo,
        coingecko_provider=provider,
        binance_provider=FakeBinanceProvider(),
    )
    result = await service.sync(max_market_pages=5, include_full_universe=False, include_binance_mapping=False)

    assert result.market_pages_fetched == 1  # stopped after the empty page 2
    assert result.coins_upserted == 1
    assert result.market_data_upserted == 1
    assert result.errors == []


@pytest.mark.asyncio
async def test_sync_does_not_create_duplicate_coins_on_repeat_id():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    # Same coingecko_id appears on two "pages" — the fake repo's
    # upsert-by-coingecko_id semantics must treat the second as a
    # match, not a new insert.
    provider = FakeCoinGeckoProvider(
        pages={1: [_pair("bitcoin", "Bitcoin")], 2: [_pair("bitcoin", "Bitcoin (renamed)")], 3: []}
    )
    service = MarketSyncService(
        coin_repository=coins_repo,
        market_data_repository=market_repo,
        coingecko_provider=provider,
        binance_provider=FakeBinanceProvider(),
    )
    result = await service.sync(max_market_pages=5, include_full_universe=False, include_binance_mapping=False)

    assert result.coins_upserted == 1
    assert result.coins_matched == 1
    assert len(coins_repo.by_coingecko_id) == 1


@pytest.mark.asyncio
async def test_sync_records_provider_error_without_crashing():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    provider = FakeCoinGeckoProvider(pages={1: [_pair("bitcoin", "Bitcoin")]}, fail_on_page=2)

    service = MarketSyncService(
        coin_repository=coins_repo,
        market_data_repository=market_repo,
        coingecko_provider=provider,
        binance_provider=FakeBinanceProvider(),
    )
    result = await service.sync(max_market_pages=5, include_full_universe=False, include_binance_mapping=False)

    assert result.market_pages_fetched == 1
    assert len(result.errors) == 1
    assert "market_page_2" in result.errors[0]


@pytest.mark.asyncio
async def test_sync_full_universe_step_upserts_and_deactivates():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    universe = [
        NormalizedCoin(coingecko_id="bitcoin", symbol="BTC", name="Bitcoin"),
        NormalizedCoin(coingecko_id="ethereum", symbol="ETH", name="Ethereum"),
    ]
    provider = FakeCoinGeckoProvider(universe=universe, pages={1: []})

    service = MarketSyncService(
        coin_repository=coins_repo,
        market_data_repository=market_repo,
        coingecko_provider=provider,
        binance_provider=FakeBinanceProvider(),
    )
    result = await service.sync(max_market_pages=1, include_full_universe=True, include_binance_mapping=False)

    assert result.full_universe_count == 2
    assert result.coins_upserted == 2
    assert coins_repo.deactivate_calls == 1


# ---------------------------------------------------------------------------
# Real-time refresh upgrade: rotating pagination, Binance fast prices,
# universe-resync delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_market_pages_fetches_a_non_contiguous_page_list():
    """
    The old sync() always started at page 1. The background scheduler
    needs to fetch an arbitrary set (e.g. hot pages 1-2 plus a cold
    page 40) in one call — this is exactly what let coins beyond the
    old hardcoded page-4 cutoff (like the reported "Visa xStock" case)
    stay stale forever.
    """
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    provider = FakeCoinGeckoProvider(
        pages={1: [_pair("bitcoin", "Bitcoin")], 40: [_pair("some-tail-coin", "Tail Coin")]}
    )
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=provider, binance_provider=FakeBinanceProvider(),
    )

    result = await service.sync_market_pages([1, 40], per_page=250)

    assert result.pages_requested == [1, 40]
    assert result.pages_completed == 2
    assert result.coins_upserted == 2
    assert result.reached_end is False


@pytest.mark.asyncio
async def test_sync_market_pages_detects_reaching_the_end():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    provider = FakeCoinGeckoProvider(pages={5: []})
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=provider, binance_provider=FakeBinanceProvider(),
    )

    result = await service.sync_market_pages([5, 6, 7])

    assert result.reached_end is True
    assert result.pages_completed == 0
    # Pages after the empty one are never attempted this cycle.
    assert result.pages_attempted == 1


@pytest.mark.asyncio
async def test_sync_market_pages_stops_after_a_provider_failure():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    provider = FakeCoinGeckoProvider(pages={3: [_pair("bitcoin", "Bitcoin")]}, fail_on_page=10)
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=provider, binance_provider=FakeBinanceProvider(),
    )

    result = await service.sync_market_pages([3, 10, 11])

    assert result.pages_completed == 1
    assert len(result.errors) == 1
    assert "market_page_10" in result.errors[0]
    # Page 11 must never be attempted after page 10's failure.
    assert result.pages_attempted == 2


@pytest.mark.asyncio
async def test_sync_full_universe_and_mapping_fetches_no_market_pages():
    coins_repo = FakeCoinRepository()
    market_repo = FakeMarketDataRepository()
    universe = [NormalizedCoin(coingecko_id="bitcoin", symbol="BTC", name="Bitcoin")]
    # Any market page fetch here would be a bug — sync_full_universe_and_mapping
    # is documented as NOT fetching price pages, so give it a page-1
    # provider response that would fail the test if it were ever requested.
    provider = FakeCoinGeckoProvider(universe=universe, pages={1: [_pair("btc-imposter", "Imposter")]})
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=provider, binance_provider=FakeBinanceProvider(),
    )

    result = await service.sync_full_universe_and_mapping()

    assert result.full_universe_count == 1
    assert result.market_pages_fetched == 0
    assert result.market_data_upserted == 0


@pytest.mark.asyncio
async def test_sync_binance_market_prices_updates_only_mapped_coins():
    coin_id = ObjectId()
    coins_repo = FakeCoinRepository()
    coins_repo.seed_binance_mapping(coin_id, "BTCUSDT")
    market_repo = FakeMarketDataRepository()
    ticker = NormalizedExchangeTicker(
        symbol="BTCUSDT", base_asset="BTC", quote_asset="USDT",
        last_price=65000.0, price_change_percent_24h=2.5,
        high_24h=66000.0, low_24h=64000.0, quote_volume_24h=1_000_000.0,
    )
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=FakeCoinGeckoProvider(),
        binance_provider=FakeBinanceProvider(tickers=[ticker]),
    )

    result = await service.sync_binance_market_prices()

    assert result.mapped_coins == 1
    assert result.coins_matched == 1
    assert result.errors == []
    assert len(market_repo.binance_upserted_entries) == 1
    entry_coin_id, entry_ticker = market_repo.binance_upserted_entries[0]
    assert entry_coin_id == coin_id
    assert entry_ticker.last_price == 65000.0


@pytest.mark.asyncio
async def test_sync_binance_market_prices_skips_unmatched_mapping():
    """A coin mapped to a symbol Binance no longer returns a ticker for must be skipped, not fabricated."""
    coin_id = ObjectId()
    coins_repo = FakeCoinRepository()
    coins_repo.seed_binance_mapping(coin_id, "DELISTEDUSDT")
    market_repo = FakeMarketDataRepository()
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=FakeCoinGeckoProvider(),
        binance_provider=FakeBinanceProvider(tickers=[]),
    )

    result = await service.sync_binance_market_prices()

    assert result.mapped_coins == 1
    assert result.coins_matched == 0
    assert market_repo.binance_upserted_entries == []


@pytest.mark.asyncio
async def test_sync_binance_market_prices_records_provider_error_without_crashing():
    coin_id = ObjectId()
    coins_repo = FakeCoinRepository()
    coins_repo.seed_binance_mapping(coin_id, "BTCUSDT")
    market_repo = FakeMarketDataRepository()
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=FakeCoinGeckoProvider(),
        binance_provider=FakeBinanceProvider(fail=True),
    )

    result = await service.sync_binance_market_prices()

    assert len(result.errors) == 1
    assert "binance_prices" in result.errors[0]
    assert market_repo.binance_upserted_entries == []


@pytest.mark.asyncio
async def test_sync_binance_market_prices_noop_when_nothing_mapped():
    coins_repo = FakeCoinRepository()  # nothing seeded
    market_repo = FakeMarketDataRepository()
    binance = FakeBinanceProvider(tickers=[])
    service = MarketSyncService(
        coin_repository=coins_repo, market_data_repository=market_repo,
        coingecko_provider=FakeCoinGeckoProvider(), binance_provider=binance,
    )

    result = await service.sync_binance_market_prices()

    assert result.mapped_coins == 0
    # Must not even call Binance's ticker endpoint when nothing is mapped.
    assert result.tickers_fetched == 0
