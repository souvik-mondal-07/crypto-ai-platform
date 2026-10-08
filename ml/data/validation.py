"""Dataset-level validation: is this series usable for training / prediction at all?"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from ml.data.preprocessing import CleaningReport


@dataclass
class CandleValidation:
    #: ok | insufficient_data | invalid
    status: str
    reason: Optional[str] = None
    rows: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def validate_candles(
    df: pd.DataFrame,
    *,
    interval_seconds: int,
    min_rows: int,
    max_gap_ratio: float = 0.02,
    max_staleness_candles: Optional[int] = None,
    report: Optional[CleaningReport] = None,
    now: Optional[datetime] = None,
) -> CandleValidation:
    """Judge a *cleaned* candle frame.

    * ``insufficient_data`` — fewer than ``min_rows`` usable candles;
    * ``invalid``          — chronology broken or too many missing candles;
    * ``ok``               — good enough (warnings are informational).
    """
    n = len(df)
    if n < min_rows:
        return CandleValidation("insufficient_data", f"Only {n} usable candles; at least {min_rows} are required.", n)
    if not df["timestamp"].is_monotonic_increasing or df["timestamp"].duplicated().any():
        return CandleValidation("invalid", "Candles are not strictly chronological.", n)

    warnings: list[str] = []
    if report is not None:
        gap_slots = report.gap_count
        if n and gap_slots / n > max_gap_ratio:
            return CandleValidation(
                "invalid", f"{gap_slots} gaps in {n} candles exceeds the allowed gap ratio.", n
            )
        if report.dropped_invalid_values or report.dropped_duplicates:
            warnings.append(
                f"dropped {report.dropped_invalid_values} invalid and {report.dropped_duplicates} duplicate rows"
            )
    if max_staleness_candles is not None:
        now = now or datetime.now(timezone.utc)
        age = (pd.Timestamp(now) - df["timestamp"].iloc[-1]).total_seconds() / interval_seconds
        if age > max_staleness_candles:
            return CandleValidation("invalid", f"Most recent candle is {age:.0f} candles old.", n, warnings)
    return CandleValidation("ok", None, n, warnings)
