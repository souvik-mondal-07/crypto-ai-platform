"""
Unit tests for MarketRefreshScheduler — the asyncio background loop
that replaces the old "always fetch pages 1..4, forever" behavior.

Uses a fake MarketSyncService (no real HTTP/Mongo) and a lightweight
fake settings object, so these run anywhere with no external services.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.market_refresh_state import MarketRefreshState
from app.services.market_refresh_scheduler import MarketRefreshScheduler


def _settings(**overrides) -> SimpleNamespace:
    defaults = dict(
        MARKET_REFRESH_ENABLED=True,
        MARKET_REFRESH_INTERVAL_SECONDS=0.01,
        MARKET_REFRESH_MAX_PAGES=4,
        MARKET_REFRESH_HOT_PAGES=2,
        MARKET_REFRESH_PER_PAGE=250,
        MARKET_REFRESH_REQUEST_DELAY_SECONDS=0.0,
        MARKET_REFRESH_INCLUDE_BINANCE=True,
        MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS=999_999,  # effectively "never, during this test"
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@dataclass
class _FakeBinanceResult:
    mapped_coins: int = 0
    tickers_fetched: int = 0
    market_data_matched: int = 0
    market_data_upserted: int = 0
    errors: list = field(default_factory=list)


@dataclass
class _FakeCoinGeckoPagesResult:
    pages_completed: int = 0
    market_data_upserted: int = 0
    reached_end: bool = False
    errors: list = field(default_factory=list)


@dataclass
class _FakeUniverseResult:
    errors: list = field(default_factory=list)


class FakeSyncService:
    def __init__(self):
        self.binance_calls = 0
        self.market_pages_calls: list[list[int]] = []
        self.universe_calls = 0
        # Test can override these per-call via a queue if needed; kept
        # simple (constant results) for the scheduler-logic tests below.
        self.next_pages_result = _FakeCoinGeckoPagesResult(pages_completed=2)

    async def sync_binance_market_prices(self):
        self.binance_calls += 1
        return _FakeBinanceResult(mapped_coins=3, tickers_fetched=3, market_data_matched=3)

    async def sync_market_pages(self, pages, *, per_page, request_delay_seconds):
        self.market_pages_calls.append(list(pages))
        result = self.next_pages_result
        result.pages_completed = len(pages) if not result.reached_end else result.pages_completed
        return result

    async def sync_full_universe_and_mapping(self):
        self.universe_calls += 1
        return _FakeUniverseResult()


@pytest.mark.asyncio
async def test_cycle_hits_hot_pages_every_time_and_rotates_cold_window():
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(
        sync_service=sync, state=MarketRefreshState(), settings=_settings(),
    )

    await scheduler.run_cycle_once()
    await scheduler.run_cycle_once()
    await scheduler.run_cycle_once()

    # hot pages = [1, 2] every cycle; cold budget = 4-2 = 2 pages,
    # starting at page 3 and advancing by 2 each successful cycle.
    assert sync.market_pages_calls[0] == [1, 2, 3, 4]
    assert sync.market_pages_calls[1] == [1, 2, 5, 6]
    assert sync.market_pages_calls[2] == [1, 2, 7, 8]


@pytest.mark.asyncio
async def test_cold_cursor_wraps_around_on_reaching_the_end():
    sync = FakeSyncService()
    sync.next_pages_result = _FakeCoinGeckoPagesResult(pages_completed=0, reached_end=True)
    scheduler = MarketRefreshScheduler(
        sync_service=sync, state=MarketRefreshState(), settings=_settings(),
    )

    await scheduler.run_cycle_once()
    await scheduler.run_cycle_once()

    # Every cycle requests the same starting cold window (page 3+)
    # once the provider signals it has reached the end of its ranked
    # data — the cursor must not keep climbing past that point.
    assert sync.market_pages_calls[0][2:] == [3, 4]
    assert sync.market_pages_calls[1][2:] == [3, 4]


@pytest.mark.asyncio
async def test_max_pages_less_than_or_equal_hot_pages_skips_cold_range():
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(
        sync_service=sync, state=MarketRefreshState(),
        settings=_settings(MARKET_REFRESH_MAX_PAGES=2, MARKET_REFRESH_HOT_PAGES=2),
    )

    await scheduler.run_cycle_once()

    assert sync.market_pages_calls[0] == [1, 2]


@pytest.mark.asyncio
async def test_binance_refresh_skipped_when_disabled():
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(
        sync_service=sync, state=MarketRefreshState(),
        settings=_settings(MARKET_REFRESH_INCLUDE_BINANCE=False),
    )

    await scheduler.run_cycle_once()

    assert sync.binance_calls == 0


@pytest.mark.asyncio
async def test_universe_sync_runs_on_first_cycle_then_waits_for_interval():
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(
        sync_service=sync, state=MarketRefreshState(),
        settings=_settings(MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS=999_999),
    )

    await scheduler.run_cycle_once()
    await scheduler.run_cycle_once()

    # First cycle ever must trigger a universe sync (no prior timestamp);
    # the second, immediately after, must not (interval hasn't elapsed).
    assert sync.universe_calls == 1


@pytest.mark.asyncio
async def test_state_reflects_last_cycle_results():
    sync = FakeSyncService()
    state = MarketRefreshState()
    scheduler = MarketRefreshScheduler(sync_service=sync, state=state, settings=_settings())

    await scheduler.run_cycle_once()

    assert state.total_cycles == 1
    assert state.is_running is False
    assert state.last_error is None
    assert state.last_cycle.binance_updated == 3
    assert state.last_cycle.coingecko_pages_completed == 4


@pytest.mark.asyncio
async def test_state_surfaces_errors_from_a_cycle():
    sync = FakeSyncService()
    sync.next_pages_result = _FakeCoinGeckoPagesResult(pages_completed=1, errors=["market_page_3: boom"])
    state = MarketRefreshState()
    scheduler = MarketRefreshScheduler(sync_service=sync, state=state, settings=_settings())

    await scheduler.run_cycle_once()

    assert state.last_error is not None
    assert "market_page_3" in state.last_error


@pytest.mark.asyncio
async def test_overlapping_cycle_is_skipped_not_run_concurrently():
    """
    Part 15: a second cycle must never run while one is still in
    flight. Simulated here by holding the scheduler's own lock before
    calling run_cycle_once() — exactly the state the loop itself would
    be in if a previous cycle were still executing.
    """
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(sync_service=sync, state=MarketRefreshState(), settings=_settings())

    async with scheduler._lock:  # simulate "a cycle is already running"
        await scheduler.run_cycle_once()

    assert sync.market_pages_calls == []
    assert sync.binance_calls == 0


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_cleans_up_the_task():
    sync = FakeSyncService()
    scheduler = MarketRefreshScheduler(sync_service=sync, state=MarketRefreshState(), settings=_settings())

    scheduler.start()
    first_task = scheduler._task
    scheduler.start()  # must not create a second loop
    assert scheduler._task is first_task

    # Let at least one cycle run.
    for _ in range(50):
        await asyncio.sleep(0.01)
        if sync.market_pages_calls:
            break

    await scheduler.stop()
    assert scheduler._task is None
    assert sync.market_pages_calls  # at least one cycle actually ran


@pytest.mark.asyncio
async def test_disabled_scheduler_never_starts_a_task():
    scheduler = MarketRefreshScheduler(
        sync_service=FakeSyncService(), state=MarketRefreshState(),
        settings=_settings(MARKET_REFRESH_ENABLED=False),
    )
    scheduler.start()
    assert scheduler.is_started is False


@pytest.mark.asyncio
async def test_stop_before_start_is_a_safe_noop():
    scheduler = MarketRefreshScheduler(
        sync_service=FakeSyncService(), state=MarketRefreshState(), settings=_settings(),
    )
    await scheduler.stop()  # must not raise
    assert scheduler.is_started is False
