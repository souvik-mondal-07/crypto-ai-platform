"""Timestamp normalisation. Everything is converted to timezone-aware UTC datetimes."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

_MS_THRESHOLD = 1e11  # epoch values above this are milliseconds (1e11 s is year 5138)


def to_utc(value: Any) -> Optional[datetime]:
    """Best-effort parse of a datetime / ISO-8601 string / epoch seconds or milliseconds -> aware UTC.

    * naive datetimes are assumed to already be UTC (MongoDB returns naive UTC datetimes);
    * aware datetimes in any zone are converted to UTC;
    * strings accept a trailing ``Z`` and date-only values;
    * numbers are epoch seconds, or milliseconds when larger than 1e11 (Binance klines use ms);
    * anything unparseable (including NaN/inf, bool, None) returns ``None`` — never a guess.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        seconds = value / 1000.0 if abs(value) >= _MS_THRESHOLD else float(value)
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            return to_utc(datetime.fromisoformat(text))
        except ValueError:
            try:
                return to_utc(float(text))
            except ValueError:
                return None
    return None


def seconds_between(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds()


def add_seconds(value: datetime, seconds: float) -> datetime:
    return value + timedelta(seconds=seconds)
