"""
Market synchronization service.

Orchestrates: provider fetch -> normalize -> repository upsert. This
is the only place that calls both a provider and a repository in the
same operation — routes never do this directly.

Designed to be triggered by:
- the dev-only manual sync endpoint (Step 3)
- a Celery periodic task (future step)
- a CLI/script (future step)

...without changing anything in this file — the trigger mechanism is
intentionally decoupled from the sync logic itself.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.providers.binance import BinanceProvider
from app.providers.coingecko import CoinGeckoProvider
from app.providers.errors import ProviderError
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository

logger = logging.getLogger("crypto_ai_platform.services.market_sync")

DATA_SOURCE = "coingecko"
BINANCE_DATA_SOURCE = "binance"

# CoinGecko's public/demo tier is rate-limited; fetching every market
# page on every manual trigger is both slow and easy to get
# rate-limited on. This cap keeps a single sync run well within a
# reasonable request budget. The background scheduler added by the
# real-time refresh upgrade reads
# its own page budget from Settings.MARKET_REFRESH_MAX_PAGES instead of
# this constant — this remains only the default for the dev-only
# manual sync endpoint's query parameter.
DEFAULT_MAX_MARKET_PAGES = 4
DEFAULT_PER_PAGE = 250


@dataclass
class SyncResult:
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    coins_matched: int = 0
    coins_upserted: int = 0
    market_data_matched: int = 0
    market_data_upserted: int = 0
    full_universe_count: int = 0
    market_pages_fetched: int = 0
    binance_pairs_mapped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class MarketPagesResult:
    """Result of fetching a (possibly non-contiguous) set of CoinGecko /coins/markets pages."""

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    pages_requested: list[int] = field(default_factory=list)
    pages_attempted: int = 0
    pages_completed: int = 0
    records_received: int = 0
    coins_matched: int = 0
    coins_upserted: int = 0
    market_data_matched: int = 0
    market_data_upserted: int = 0
    #: True once a fetched page came back empty — i.e. this run walked
    #: past the end of CoinGecko's ranked market-data universe.
    reached_end: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class BinancePriceSyncResult:
    """Result of the fast Binance-ticker price refresh for mapped coins."""

    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    mapped_coins: int = 0
    tickers_fetched: int = 0
    coins_matched: int = 0
    market_data_matched: int = 0
    market_data_upserted: int = 0
    errors: list[str] = field(default_factory=list)


class MarketSyncService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        coingecko_provider: Optional[CoinGeckoProvider] = None,
        binance_provider: Optional[BinanceProvider] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market_data = market_data_repository or MarketDataRepository()
        self._coingecko = coingecko_provider or CoinGeckoProvider()
        self._binance = binance_provider or BinanceProvider()

    async def sync(
        self,
        *,
        max_market_pages: int = DEFAULT_MAX_MARKET_PAGES,
        per_page: int = DEFAULT_PER_PAGE,
        include_full_universe: bool = True,
        include_binance_mapping: bool = True,
    ) -> SyncResult:
        """
        Run a full sync cycle:

        1. (optional) Fetch CoinGecko's complete coin universe
           (id/symbol/name) and upsert every coin — this is what
           guarantees the platform isn't limited to a hard-coded
           subset. Coins not present in *this* fetch ARE deactivated
           (mark-and-sweep), since this step genuinely does cover the
           entire provider universe in one call.
        2. Fetch up to `max_market_pages` pages of ranked market data
           (price, market cap, rank, logo, etc.) from /coins/markets
           and upsert both the coin enrichment fields and the
           market_data snapshot. Bounded by `max_market_pages` — see
           module docstring for why this isn't "fetch everything".
        3. (optional) Fetch Binance's USDT trading pairs and attach a
           `providers.binance` mapping to any coin whose symbol
           matches — best-effort; Binance not listing a coin does not
           deactivate it (Binance is not the broad-universe source).

        Never raises on a single provider hiccup partway through — a
        failed step is recorded in `SyncResult.errors` and the sync
        continues with whatever it already has, rather than losing all
        progress.
        """
        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        result = SyncResult(started_at=started_at, finished_at=started_at, duration_seconds=0.0)

        async with httpx.AsyncClient() as http_client:
            if include_full_universe:
                try:
                    universe = await self._coingecko.list_full_universe(http_client)
                    result.full_universe_count = len(universe)
                    upsert_counts = await self._coins.bulk_upsert_from_coingecko(universe)
                    result.coins_matched += upsert_counts["matched"]
                    result.coins_upserted += upsert_counts["upserted"]

                    deactivated = await self._coins.deactivate_stale(seen_before=started_at)
                    if deactivated:
                        logger.info("Deactivated %d coins no longer present on CoinGecko.", deactivated)
                except ProviderError as exc:
                    logger.error("Full-universe sync step failed: %s", exc)
                    result.errors.append(f"full_universe: {exc}")

            for page in range(1, max_market_pages + 1):
                try:
                    pairs = await self._coingecko.list_coins_with_market_data(
                        http_client, page, per_page
                    )
                except ProviderError as exc:
                    logger.error("Market data page %d failed: %s", page, exc)
                    result.errors.append(f"market_page_{page}: {exc}")
                    break  # stop paginating further on a provider failure

                if not pairs:
                    break  # reached the end of the provider's data

                coins = [pair[0] for pair in pairs]
                coin_upsert_counts = await self._coins.bulk_upsert_from_coingecko(coins)
                result.coins_matched += coin_upsert_counts["matched"]
                result.coins_upserted += coin_upsert_counts["upserted"]

                market_entries = await self._resolve_market_entries(pairs)
                market_upsert_counts = await self._market_data.bulk_upsert(
                    market_entries, data_source=DATA_SOURCE
                )
                result.market_data_matched += market_upsert_counts["matched"]
                result.market_data_upserted += market_upsert_counts["upserted"]
                result.market_pages_fetched += 1

            if include_binance_mapping:
                try:
                    result.binance_pairs_mapped = await self._sync_binance_mapping()
                except ProviderError as exc:
                    logger.warning("Binance mapping step failed (non-fatal): %s", exc)
                    result.errors.append(f"binance_mapping: {exc}")

        finished_at = datetime.now(timezone.utc)
        result.finished_at = finished_at
        result.duration_seconds = time.perf_counter() - start_perf
        return result

    async def sync_market_pages(
        self,
        pages: list[int],
        *,
        per_page: int = DEFAULT_PER_PAGE,
        request_delay_seconds: float = 0.0,
    ) -> MarketPagesResult:
        """
        Fetch a specific, possibly non-contiguous set of CoinGecko
        `/coins/markets` pages and upsert them.

        This is the primitive the background scheduler (added by the
        real-time refresh upgrade) uses
        to cover the full ranked universe over successive cycles
        without exceeding a per-cycle request budget: a "hot" set of
        low page numbers plus a slowly-rotating "cold" window (see
        `MarketRefreshScheduler`), rather than the same fixed
        `range(1, N)` every time — which is what left coins beyond the
        old hardcoded page-4 cutoff permanently stale.

        `request_delay_seconds` spaces out successive page requests so
        a single cycle doesn't burst-fire every page back to back
        against a rate-limited provider. Stops (does not raise) on the
        first provider failure — the remaining requested pages are
        simply not attempted this cycle and will be retried on a later
        one, exactly like the original `sync()` pagination loop.
        """
        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        result = MarketPagesResult(
            started_at=started_at, finished_at=started_at, duration_seconds=0.0,
            pages_requested=list(pages),
        )

        async with httpx.AsyncClient() as http_client:
            for index, page in enumerate(pages):
                result.pages_attempted += 1
                try:
                    pairs = await self._coingecko.list_coins_with_market_data(
                        http_client, page, per_page
                    )
                except ProviderError as exc:
                    logger.error("Market data page %d failed: %s", page, exc)
                    result.errors.append(f"market_page_{page}: {exc}")
                    break  # never hammer subsequent pages after a provider failure

                if not pairs:
                    result.reached_end = True
                    break  # reached the end of the provider's ranked data

                result.records_received += len(pairs)
                coins = [pair[0] for pair in pairs]
                coin_counts = await self._coins.bulk_upsert_from_coingecko(coins)
                result.coins_matched += coin_counts["matched"]
                result.coins_upserted += coin_counts["upserted"]

                market_entries = await self._resolve_market_entries(pairs)
                market_counts = await self._market_data.bulk_upsert(
                    market_entries, data_source=DATA_SOURCE
                )
                result.market_data_matched += market_counts["matched"]
                result.market_data_upserted += market_counts["upserted"]
                result.pages_completed += 1

                is_last = index == len(pages) - 1
                if not is_last and request_delay_seconds:
                    await asyncio.sleep(request_delay_seconds)

        result.finished_at = datetime.now(timezone.utc)
        result.duration_seconds = time.perf_counter() - start_perf
        return result

    async def sync_full_universe_and_mapping(self) -> SyncResult:
        """
        Full CoinGecko coin-universe resync + Binance trading-pair
        mapping refresh, with NO `/coins/markets` price pages fetched
        (that's `sync_market_pages`'s job, run on its own, much more
        frequent cadence). Reuses `sync()` with `max_market_pages=0`
        rather than duplicating its full-universe/mapping logic.
        """
        return await self.sync(
            max_market_pages=0, include_full_universe=True, include_binance_mapping=True
        )

    async def sync_binance_market_prices(self) -> BinancePriceSyncResult:
        """
        Near-real-time price refresh for every coin with a valid
        Binance mapping, using ONE bulk call to Binance's 24hr ticker
        endpoint (no per-coin requests, regardless of how many coins
        are mapped) — this is what makes Binance-listed assets track
        close to live, independent of CoinGecko's tighter rate limits.

        Only the live-tracking fields are updated (see
        `MarketDataRepository.bulk_upsert_binance_prices`) — market
        cap, supply, and ATH/ATL keep whatever the last CoinGecko sync
        set.
        """
        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        result = BinancePriceSyncResult(
            started_at=started_at, finished_at=started_at, duration_seconds=0.0
        )

        try:
            mapped = await self._coins.list_binance_mapped()
            result.mapped_coins = len(mapped)
            if mapped:
                tickers = await self._binance.get_exchange_tickers()
                result.tickers_fetched = len(tickers)
                ticker_by_symbol = {t.symbol: t for t in tickers}

                entries = [
                    (coin_id, ticker_by_symbol[symbol])
                    for coin_id, symbol in mapped
                    if symbol in ticker_by_symbol
                ]
                result.coins_matched = len(entries)
                counts = await self._market_data.bulk_upsert_binance_prices(
                    entries, data_source=BINANCE_DATA_SOURCE
                )
                result.market_data_matched = counts["matched"]
                result.market_data_upserted = counts["upserted"]
        except ProviderError as exc:
            logger.warning("Binance price refresh failed (non-fatal): %s", exc)
            result.errors.append(f"binance_prices: {exc}")

        result.finished_at = datetime.now(timezone.utc)
        result.duration_seconds = time.perf_counter() - start_perf
        return result

    async def _resolve_market_entries(self, pairs):
        """Resolve each pair's CoinGecko ID to its internal ObjectId before upserting market data."""
        entries = []
        for coin, market in pairs:
            coin_doc = await self._coins.find_by_coingecko_id(coin.coingecko_id)
            if coin_doc is None:
                # Shouldn't normally happen (we just upserted this
                # coin), but skip defensively rather than crashing the
                # whole sync over one inconsistent record.
                continue
            entries.append((coin_doc["_id"], market))
        return entries

    async def _sync_binance_mapping(self) -> int:
        pairs = await self._binance.list_trading_pairs()
        mapped = 0
        for pair in pairs:
            # Match Binance's base asset against our coin symbols.
            # Best-effort: symbol collisions mean this can occasionally
            # attach the wrong coin — acceptable for Step 3's
            # enrichment purpose, and documented in docs/market-data.md.
            coin_doc = await self._coins.collection.find_one(
                {"symbol": pair.base_asset, "is_active": True}
            )
            if coin_doc is None:
                continue
            coingecko_id = (coin_doc.get("providers") or {}).get("coingecko", {}).get("id")
            if not coingecko_id:
                continue
            updated = await self._coins.set_binance_mapping(coingecko_id, pair.symbol)
            if updated:
                mapped += 1
        return mapped
