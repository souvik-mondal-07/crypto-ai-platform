"""
Background market-data refresh scheduler (Parts 2-3, 15).

A lightweight `asyncio.create_task` loop — deliberately NOT Celery,
Redis, or any other new infrastructure dependency, per the project's
constraints. Started/stopped from `app/main.py`'s FastAPI lifespan.

Runs two cadences from a single task:

  * a "fast cycle" every `MARKET_REFRESH_INTERVAL_SECONDS`:
      - a Binance 24hr-ticker price refresh for every Binance-mapped
        coin (one bulk call; near-real-time for those assets), if
        `MARKET_REFRESH_INCLUDE_BINANCE` is on;
      - a bounded CoinGecko `/coins/markets` page fetch: the top
        `MARKET_REFRESH_HOT_PAGES` pages (by market cap — what the
        Dashboard/Markets overview, gainers and losers read) EVERY
        cycle, plus a slowly-rotating "cold" window covering the rest
        of the ranked universe using the remaining page budget, so
        pages beyond the old hardcoded cutoff of 4 eventually get
        refreshed too instead of staying stale forever.

  * a much less frequent "universe cycle" every
    `MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS`: a full CoinGecko
    coin-list resync plus a Binance trading-pair mapping refresh, to
    pick up newly listed/delisted coins and new Binance pairs.

An `asyncio.Lock` guarantees at most one cycle body runs at a time.
Since the loop only ever schedules its own next cycle after the
current one finishes (`asyncio.sleep` after the `async with` block
exits), overlap should be structurally impossible in normal operation
— the lock is a defensive backstop, e.g. against a future change that
calls `_run_cycle` from more than one place.

Honest limitation (see Part 26/final report): CoinGecko's public tier
rate limit means the full ~21k-coin universe cannot be refreshed every
cycle — only a bounded, rotating slice of it is. Binance-mapped coins
are the ones that get genuinely near-real-time prices; everything else
gets "eventually refreshed, on a rotation measured in cycles, not
seconds."
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.core.market_refresh_state import MarketRefreshState, RefreshCycleSnapshot, get_refresh_state
from app.services.market_sync_service import MarketSyncService

logger = logging.getLogger("crypto_ai_platform.services.market_refresh_scheduler")


class MarketRefreshScheduler:
    def __init__(
        self,
        sync_service: Optional[MarketSyncService] = None,
        state: Optional[MarketRefreshState] = None,
        settings=None,
    ) -> None:
        self._settings = settings or get_settings()
        self._sync = sync_service or MarketSyncService()
        self.state = state or get_refresh_state()
        self.state.enabled = self._settings.MARKET_REFRESH_ENABLED

        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        hot = max(0, self._settings.MARKET_REFRESH_HOT_PAGES)
        self._cold_start_page = hot + 1
        self._cold_page_cursor = self._cold_start_page
        self._last_universe_sync_monotonic: Optional[float] = None

    @property
    def is_started(self) -> bool:
        return self._task is not None

    def start(self) -> None:
        if self._task is not None:
            logger.warning("Market refresh scheduler already started — ignoring duplicate start().")
            return
        if not self._settings.MARKET_REFRESH_ENABLED:
            logger.info("Market refresh disabled (MARKET_REFRESH_ENABLED=false); background loop not started.")
            return
        self._task = asyncio.create_task(self._run_forever(), name="market-refresh-scheduler")
        logger.info(
            "Market refresh scheduler started (interval=%ss, max_pages=%s, hot_pages=%s, binance=%s).",
            self._settings.MARKET_REFRESH_INTERVAL_SECONDS,
            self._settings.MARKET_REFRESH_MAX_PAGES,
            self._settings.MARKET_REFRESH_HOT_PAGES,
            self._settings.MARKET_REFRESH_INCLUDE_BINANCE,
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Market refresh scheduler stopped.")

    async def _run_forever(self) -> None:
        while True:
            try:
                await self.run_cycle_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — one bad cycle must never kill the loop
                logger.exception("Unhandled error in market refresh cycle.")
            await asyncio.sleep(self._settings.MARKET_REFRESH_INTERVAL_SECONDS)

    async def run_cycle_once(self) -> None:
        """Run a single refresh cycle now. Exposed separately from the loop for tests and manual triggers."""
        if self._lock.locked():
            logger.warning("Previous market refresh cycle still running — skipping this tick.")
            return
        async with self._lock:
            await self._run_cycle()

    async def _run_cycle(self) -> None:
        start_perf = time.perf_counter()
        self.state.mark_started()
        snapshot = RefreshCycleSnapshot(binance_enabled=self._settings.MARKET_REFRESH_INCLUDE_BINANCE)
        snapshot.started_at = datetime.now(timezone.utc)

        if self._settings.MARKET_REFRESH_INCLUDE_BINANCE:
            binance_result = await self._sync.sync_binance_market_prices()
            snapshot.binance_mapped_coins = binance_result.mapped_coins
            snapshot.binance_tickers_fetched = binance_result.tickers_fetched
            snapshot.binance_updated = binance_result.market_data_matched + binance_result.market_data_upserted
            snapshot.errors.extend(binance_result.errors)

        pages = self._pages_for_cycle()
        cg_result = await self._sync.sync_market_pages(
            pages,
            per_page=self._settings.MARKET_REFRESH_PER_PAGE,
            request_delay_seconds=self._settings.MARKET_REFRESH_REQUEST_DELAY_SECONDS,
        )
        snapshot.coingecko_pages_requested = pages
        snapshot.coingecko_pages_completed = cg_result.pages_completed
        snapshot.coingecko_records_upserted = cg_result.market_data_upserted
        snapshot.coingecko_reached_end = cg_result.reached_end
        snapshot.errors.extend(cg_result.errors)
        self._advance_cold_cursor(cg_result.pages_completed, cg_result.reached_end)

        if self._universe_sync_due():
            universe_result = await self._sync.sync_full_universe_and_mapping()
            self._last_universe_sync_monotonic = time.monotonic()
            self.state.record_universe_sync()
            snapshot.errors.extend(universe_result.errors)

        snapshot.finished_at = datetime.now(timezone.utc)
        snapshot.duration_seconds = time.perf_counter() - start_perf
        self.state.record_cycle(snapshot)
        logger.info(
            "Market refresh cycle finished in %.2fs (coingecko_pages=%d, binance_updated=%d, errors=%d).",
            snapshot.duration_seconds,
            snapshot.coingecko_pages_completed,
            snapshot.binance_updated,
            len(snapshot.errors),
        )

    def _pages_for_cycle(self) -> list[int]:
        hot = list(range(1, self._settings.MARKET_REFRESH_HOT_PAGES + 1))
        remaining_budget = max(0, self._settings.MARKET_REFRESH_MAX_PAGES - len(hot))
        if remaining_budget <= 0:
            return hot
        cold = list(range(self._cold_page_cursor, self._cold_page_cursor + remaining_budget))
        return hot + cold

    def _advance_cold_cursor(self, pages_completed: int, reached_end: bool) -> None:
        if reached_end:
            # Walked past the end of the provider's ranked universe —
            # wrap back around so the tail keeps getting re-refreshed
            # rather than the cursor climbing past it forever.
            self._cold_page_cursor = self._cold_start_page
            return
        cold_completed = max(0, pages_completed - self._settings.MARKET_REFRESH_HOT_PAGES)
        self._cold_page_cursor += cold_completed

    def _universe_sync_due(self) -> bool:
        if self._last_universe_sync_monotonic is None:
            return True
        elapsed = time.monotonic() - self._last_universe_sync_monotonic
        return elapsed >= self._settings.MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS


_scheduler: Optional[MarketRefreshScheduler] = None


def get_scheduler() -> MarketRefreshScheduler:
    """Process-wide singleton, so app/main.py and the status API share the same instance/state."""
    global _scheduler
    if _scheduler is None:
        _scheduler = MarketRefreshScheduler()
    return _scheduler
