"""
In-memory market-refresh status tracking (Parts 17-18).

A process-local, best-effort snapshot of the background scheduler's
health — used by the lightweight `/market/refresh-status` endpoint so
a developer can see why a particular coin is stale without digging
through logs. This is intentionally NOT persisted: no new datastore or
collection is introduced for it (see Part 3's "no Celery/Redis/Docker"
constraint). A process restart, or in a multi-worker deployment each
worker individually, starts this fresh — an accepted trade-off for a
cheap status view rather than real infrastructure.

Never stores secrets or provider keys — only counts, timestamps, and
short error strings already safe for logs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class RefreshCycleSnapshot:
    """One completed background-refresh cycle's outcome."""

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    binance_enabled: bool = False
    binance_mapped_coins: int = 0
    binance_tickers_fetched: int = 0
    binance_updated: int = 0

    coingecko_pages_requested: list[int] = field(default_factory=list)
    coingecko_pages_completed: int = 0
    coingecko_records_upserted: int = 0
    coingecko_reached_end: bool = False

    errors: list[str] = field(default_factory=list)


class MarketRefreshState:
    """
    Not safe for concurrent cross-process access (a plain in-process
    object, no locking beyond what the scheduler itself already
    guarantees by only ever calling this from within its own single
    background task) — see module docstring for why that's fine here.
    """

    def __init__(self) -> None:
        self.is_running: bool = False
        self.last_cycle: Optional[RefreshCycleSnapshot] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.total_cycles: int = 0
        self.last_universe_sync_at: Optional[datetime] = None
        self.enabled: bool = True

    def mark_started(self) -> None:
        self.is_running = True

    def record_cycle(self, snapshot: RefreshCycleSnapshot) -> None:
        self.is_running = False
        self.last_cycle = snapshot
        self.total_cycles += 1
        self.last_error = "; ".join(snapshot.errors) if snapshot.errors else None
        if snapshot.finished_at is not None:
            self.last_success_at = snapshot.finished_at

    def record_universe_sync(self, when: Optional[datetime] = None) -> None:
        self.last_universe_sync_at = when or datetime.now(timezone.utc)

    def as_dict(self) -> dict[str, Any]:
        cycle = self.last_cycle
        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "total_cycles": self.total_cycles,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "last_universe_sync_at": self.last_universe_sync_at,
            "last_cycle": None
            if cycle is None
            else {
                "started_at": cycle.started_at,
                "finished_at": cycle.finished_at,
                "duration_seconds": cycle.duration_seconds,
                "binance_enabled": cycle.binance_enabled,
                "binance_mapped_coins": cycle.binance_mapped_coins,
                "binance_tickers_fetched": cycle.binance_tickers_fetched,
                "binance_updated": cycle.binance_updated,
                "coingecko_pages_requested": cycle.coingecko_pages_requested,
                "coingecko_pages_completed": cycle.coingecko_pages_completed,
                "coingecko_records_upserted": cycle.coingecko_records_upserted,
                "coingecko_reached_end": cycle.coingecko_reached_end,
                "errors": cycle.errors,
            },
        }


_state: Optional[MarketRefreshState] = None


def get_refresh_state() -> MarketRefreshState:
    """Process-wide singleton — one state object per backend process."""
    global _state
    if _state is None:
        _state = MarketRefreshState()
    return _state
