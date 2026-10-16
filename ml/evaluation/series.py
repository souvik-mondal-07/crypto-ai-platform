"""A validated candle series with strictly point-in-time lookups.

Rules (document-level contract, see docs/backtesting.md):

* A candle is identified by its OPEN time; its close time is ``open + interval``.
* Candles with non-finite / non-positive prices, inconsistent high/low, or negative volume are dropped
  (never repaired or interpolated).
* Duplicate open times are collapsed (the LAST one supplied wins, e.g. a re-fetched candle).
* Incomplete candles — close time after ``as_of`` — are excluded. ``as_of`` is also the guard against
  look-ahead: a series built with ``as_of=t`` can never reveal a price that was not yet final at ``t``.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional

from ml.evaluation.constants import INTERVAL_SECONDS
from ml.evaluation.timestamps import to_utc


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval_seconds: int

    @property
    def close_time(self) -> datetime:
        return self.open_time + timedelta(seconds=self.interval_seconds)


@dataclass
class SeriesReport:
    received: int = 0
    kept: int = 0
    dropped_unparseable: int = 0
    dropped_invalid_values: int = 0
    dropped_duplicates: int = 0
    dropped_incomplete: int = 0


def _finite_positive(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values)


def candle_from_row(row: Any, interval_seconds: int) -> Optional[Candle]:
    """Binance kline row ``[open_ms, o, h, l, c, v, ...]`` or mapping -> Candle (None if unusable)."""
    try:
        if isinstance(row, Mapping):
            t = to_utc(row.get("timestamp", row.get("open_time")))
            o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            v = float(row.get("volume", 0.0))
        else:
            t = to_utc(row[0])
            o, h, l, c, v = (float(row[i]) for i in range(1, 6))
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    if t is None:
        return None
    return Candle(t, o, h, l, c, v, interval_seconds)


class PriceSeries:
    """Sorted, de-duplicated, validated candles for ONE coin at ONE interval."""

    def __init__(self, candles: Iterable[Candle], interval_seconds: int, *, as_of: Optional[datetime] = None) -> None:
        self.interval_seconds = interval_seconds
        self.as_of = to_utc(as_of) if as_of is not None else None
        self.report = SeriesReport()
        by_open: dict[datetime, Candle] = {}
        for c in candles:
            self.report.received += 1
            if not (_finite_positive(c.open, c.high, c.low, c.close) and math.isfinite(c.volume) and c.volume >= 0
                    and c.high >= c.low and c.high >= max(c.open, c.close) - 1e-12
                    and c.low <= min(c.open, c.close) + 1e-12):
                self.report.dropped_invalid_values += 1
                continue
            if self.as_of is not None and c.close_time > self.as_of:
                self.report.dropped_incomplete += 1
                continue
            if c.open_time in by_open:
                self.report.dropped_duplicates += 1
            by_open[c.open_time] = c
        self.candles: list[Candle] = [by_open[k] for k in sorted(by_open)]
        self.report.kept = len(self.candles)
        self._close_times = [c.close_time for c in self.candles]
        self._open_times = [c.open_time for c in self.candles]

    @classmethod
    def from_rows(cls, rows: Iterable[Any], interval: str, *, as_of: Optional[datetime] = None) -> "PriceSeries":
        seconds = INTERVAL_SECONDS[interval]
        parsed: list[Candle] = []
        bad = 0
        total = 0
        for row in rows:
            total += 1
            c = candle_from_row(row, seconds)
            if c is None:
                bad += 1
            else:
                parsed.append(c)
        series = cls(parsed, seconds, as_of=as_of)
        series.report.received = total
        series.report.dropped_unparseable = bad
        return series

    def __len__(self) -> int:
        return len(self.candles)

    @property
    def first_open_time(self) -> Optional[datetime]:
        return self._open_times[0] if self._open_times else None

    @property
    def last_close_time(self) -> Optional[datetime]:
        return self._close_times[-1] if self._close_times else None

    def last_completed_at(self, when: datetime) -> Optional[Candle]:
        """Latest candle whose close time is <= ``when`` (information available at ``when``)."""
        i = bisect_right(self._close_times, when)
        return self.candles[i - 1] if i else None

    def nearest_close(self, target: datetime, tolerance_seconds: float) -> Optional[Candle]:
        """Candle whose CLOSE time is nearest ``target`` within the tolerance (ties -> earlier)."""
        if not self.candles:
            return None
        i = bisect_left(self._close_times, target)
        options = [self.candles[j] for j in (i - 1, i) if 0 <= j < len(self.candles)]
        best = min(options, key=lambda c: (abs((c.close_time - target).total_seconds()), c.close_time))
        return best if abs((best.close_time - target).total_seconds()) <= tolerance_seconds else None

    def first_opening_at_or_after(self, when: datetime) -> Optional[Candle]:
        i = bisect_left(self._open_times, when)
        return self.candles[i] if i < len(self.candles) else None

    def truncated(self, as_of: datetime) -> "PriceSeries":
        """A new series that only contains candles already closed at ``as_of``."""
        return PriceSeries(self.candles, self.interval_seconds, as_of=as_of)
