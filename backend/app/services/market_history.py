"""Real historical candles for Phase 17 (outcome matching and backtests).

Reuses the existing Binance provider (no new data source). Rows are fetched for an explicit window, cached in
memory for a few minutes (so one refresh/backtest does not re-download the same range), and handed to the pure
`ml.evaluation` code as validated `PriceSeries`. Nothing is interpolated or invented: a failed or empty
download is surfaced to the caller as an error / empty series, never as prices.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from app.config.backtest_config import CANDLE_CACHE_MAX_ENTRIES, CANDLE_CACHE_TTL_SECONDS
from app.providers.binance.provider import BinanceProvider

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from ml.evaluation.constants import INTERVAL_SECONDS  # noqa: E402
from ml.evaluation.series import PriceSeries  # noqa: E402

_cache: dict[tuple, tuple[float, list[list[Any]]]] = {}


def clear_cache() -> None:
    _cache.clear()


def cluster_windows(times: list[datetime], interval: str, max_span_candles: int = 900) -> list[tuple[datetime, datetime]]:
    """Group sorted target times into few fetch windows (each spans at most `max_span_candles` candles)."""
    if not times:
        return []
    step = INTERVAL_SECONDS[interval]
    ordered = sorted(times)
    windows: list[tuple[datetime, datetime]] = []
    start = prev = ordered[0]
    for t in ordered[1:]:
        if (t - start).total_seconds() > max_span_candles * step:
            windows.append((start, prev))
            start = t
        prev = t
    windows.append((start, prev))
    return windows


class MarketHistory:
    def __init__(self, provider: Optional[BinanceProvider] = None) -> None:
        self._provider = provider or BinanceProvider()

    async def rows(self, symbol: str, interval: str, start: datetime, end: datetime, max_candles: int = 10_000) -> list[list[Any]]:
        key = (symbol, interval, start.isoformat(), end.isoformat(), max_candles)
        hit = _cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < CANDLE_CACHE_TTL_SECONDS:
            return hit[1]
        rows = await self._provider.get_klines_range(symbol, interval, start, end, max_candles)
        if len(_cache) >= CANDLE_CACHE_MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (now, rows)
        return rows

    async def series(self, symbol: str, interval: str, start: datetime, end: datetime, *, as_of: datetime,
                     max_candles: int = 10_000) -> PriceSeries:
        """Validated series for [start, end] containing only candles already CLOSED at `as_of`."""
        rows = await self.rows(symbol, interval, start, end, max_candles)
        return PriceSeries.from_rows(rows, interval, as_of=as_of)

    @staticmethod
    def padded(start: datetime, end: datetime, interval: str) -> tuple[datetime, datetime]:
        pad = timedelta(seconds=INTERVAL_SECONDS[interval] * 2)
        return start - pad, end + pad
