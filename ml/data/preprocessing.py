"""Candle cleaning: chronological order, valid values, no duplicates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from ml.data.loaders import CANDLE_COLUMNS

_PRICE_COLS = ["open", "high", "low", "close"]


@dataclass
class CleaningReport:
    rows_in: int = 0
    rows_out: int = 0
    dropped_unparseable: int = 0
    dropped_invalid_values: int = 0
    dropped_duplicates: int = 0
    reordered: bool = False
    #: Count of missing candle slots inside the series (gaps are reported, never filled).
    gap_count: int = 0
    max_gap_candles: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def clean_candles(df: pd.DataFrame, interval_seconds: Optional[int] = None) -> tuple[pd.DataFrame, CleaningReport]:
    """Return (clean frame, report).

    * rows with unparseable timestamps / non-finite or non-positive prices, negative
      volume, or inconsistent high/low are dropped (never repaired or interpolated);
    * duplicate timestamps keep the LAST occurrence (a later fetch of a candle is
      the more complete one);
    * rows are sorted chronologically;
    * missing candle slots are *reported* (``gap_count``) but NOT filled — filling
      would invent prices.
    """
    report = CleaningReport(rows_in=len(df))
    missing = [c for c in CANDLE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Candle frame is missing columns: {missing}")

    out = df[CANDLE_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    for col in CANDLE_COLUMNS[1:]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    before = len(out)
    out = out.dropna(subset=["timestamp"] + _PRICE_COLS)
    report.dropped_unparseable = before - len(out)

    before = len(out)
    finite = np.isfinite(out[_PRICE_COLS].to_numpy(dtype="float64")).all(axis=1)
    out = out[finite]
    positive = (out[_PRICE_COLS] > 0).all(axis=1)
    consistent = (
        (out["high"] >= out["low"])
        & (out["high"] >= out[["open", "close"]].max(axis=1))
        & (out["low"] <= out[["open", "close"]].min(axis=1))
    )
    # Volume is optional per row, but when present it must be finite and non-negative.
    volume_ok = out["volume"].isna() | (np.isfinite(out["volume"]) & (out["volume"] >= 0))
    out = out[positive & consistent & volume_ok]
    report.dropped_invalid_values = before - len(out)

    report.reordered = not out["timestamp"].is_monotonic_increasing
    out = out.sort_values("timestamp", kind="mergesort")

    before = len(out)
    out = out.drop_duplicates(subset="timestamp", keep="last")
    report.dropped_duplicates = before - len(out)

    out = out.reset_index(drop=True)
    report.rows_out = len(out)

    if interval_seconds and len(out) > 1:
        deltas = out["timestamp"].diff().dropna().dt.total_seconds().to_numpy()
        missing_slots = np.maximum(np.round(deltas / interval_seconds) - 1, 0)
        report.gap_count = int((missing_slots > 0).sum())
        report.max_gap_candles = int(missing_slots.max()) if missing_slots.size else 0
    return out, report


def drop_incomplete_last_candle(
    df: pd.DataFrame, interval_seconds: int, now: Optional[datetime] = None
) -> pd.DataFrame:
    """Remove the final candle if it has not closed yet.

    An open candle's close/high/low/volume are still changing, so using it as a
    feature row (or as a target) would mix not-yet-known information into the data.
    """
    if df.empty:
        return df
    now = now or datetime.now(timezone.utc)
    last_close_time = df["timestamp"].iloc[-1] + pd.Timedelta(seconds=interval_seconds)
    if last_close_time > pd.Timestamp(now):
        return df.iloc[:-1].reset_index(drop=True)
    return df
