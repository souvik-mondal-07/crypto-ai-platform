"""Loading REAL historical candles.

Candle frame contract used everywhere in ``ml``:

    columns: timestamp (tz-aware UTC, candle OPEN time), open, high, low, close, volume

The only source today is Binance spot klines (public REST API) because it is the
one provider in this project that returns volume and sub-daily candles with enough
depth to train on. CoinGecko's OHLC endpoint has no volume and coarse granularity,
and ``historical_prices`` is not populated by any sync job, so neither is used.
Coins without a Binance mapping therefore get ``insufficient_data`` — never a
synthetic series.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

import pandas as pd

logger = logging.getLogger("crypto_ai_platform.ml.data")

CANDLE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
BINANCE_MAX_PER_REQUEST = 1000

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}


def interval_to_seconds(interval: str) -> int:
    try:
        return INTERVAL_SECONDS[interval]
    except KeyError:
        raise ValueError(f"Unsupported kline interval {interval!r}") from None


def empty_candles() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="float64") for c in CANDLE_COLUMNS}).astype(
        {"timestamp": "datetime64[ns, UTC]"}
    )


def candles_from_klines(rows: Iterable[Iterable[Any]]) -> pd.DataFrame:
    """Binance kline rows -> candle frame.

    Row layout: [open_time_ms, open, high, low, close, volume, close_time_ms, ...].
    Unparseable rows are skipped here; value-level validation happens in
    ``preprocessing.clean_candles``.
    """
    records: list[dict[str, Any]] = []
    for row in rows:
        try:
            records.append(
                {
                    "timestamp": datetime.fromtimestamp(float(row[0]) / 1000.0, tz=timezone.utc),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
    return candles_from_records(records)


def candles_from_records(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Dict records (timestamp/open/high/low/close/volume) -> candle frame."""
    df = pd.DataFrame(list(records))
    if df.empty:
        return empty_candles()
    missing = [c for c in CANDLE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Candle records are missing columns: {missing}")
    df = df[CANDLE_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for col in CANDLE_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


class BinanceKlineLoader:
    """Synchronous paged kline loader (used by the training CLI; the API wraps the
    async provider instead). Pages backwards with ``endTime`` until ``limit`` candles
    are collected or the exchange runs out of history.
    """

    def __init__(self, base_url: str = "https://api.binance.com", request_delay: float = 0.25, timeout: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._delay = request_delay
        self._timeout = timeout

    def fetch(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        import httpx  # backend dependency; imported lazily so `import ml` stays light

        interval_to_seconds(interval)
        collected: list[list[Any]] = []
        end_time: Optional[int] = None
        with httpx.Client(timeout=self._timeout) as client:
            while len(collected) < limit:
                params: dict[str, Any] = {
                    "symbol": symbol,
                    "interval": interval,
                    "limit": min(BINANCE_MAX_PER_REQUEST, limit - len(collected)),
                }
                if end_time is not None:
                    params["endTime"] = end_time
                response = client.get(f"{self._base_url}/api/v3/klines", params=params)
                response.raise_for_status()
                page = response.json()
                if not page:
                    break
                collected = page + collected
                oldest_open = int(page[0][0])
                if end_time is not None and oldest_open - 1 >= end_time:
                    break  # no progress; avoid an infinite loop
                end_time = oldest_open - 1
                if len(page) < params["limit"]:
                    break  # reached the start of the symbol's history
                time.sleep(self._delay)
        logger.info("Loaded %d raw %s klines for %s", len(collected), interval, symbol)
        return candles_from_klines(collected)
