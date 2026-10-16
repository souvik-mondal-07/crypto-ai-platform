"""Match matured predictions to the ACTUAL market outcome.

Timing contract
---------------
* ``reference_time`` is the CLOSE time of the last completed candle the forecast started from and
  ``reference_price`` that candle's close (Phase 13 stores them as ``reference_time`` / ``current_price``).
* ``target_time = reference_time + horizon``. A prediction is MATURED only when ``now >= target_time``.
* The actual price is the CLOSE of the candle whose close time is nearest ``target_time``, accepted only
  within ``MATCH_TOLERANCE_FRACTION * interval`` (a half interval). The candle must already be closed at ``now``.
* ``actual_return = actual_price / reference_price - 1`` using the RECORDED reference price.

Every non-matched status explains why; none of them is ever counted as a correct or incorrect prediction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Literal, Mapping, Optional

from ml.evaluation.constants import (
    HORIZON_INTERVAL,
    HORIZON_SECONDS,
    INTERVAL_SECONDS,
    MATCH_TOLERANCE_FRACTION,
)
from ml.evaluation.series import PriceSeries
from ml.evaluation.timestamps import to_utc

OutcomeStatus = Literal[
    "matched",
    "not_matured",
    "missing_reference_price",
    "missing_future_price",
    "stale_market_data",
    "unsupported_horizon",
    "invalid_record",
]

DIRECTIONS = ("up", "down", "flat")


def tolerance_seconds(horizon: str) -> float:
    return MATCH_TOLERANCE_FRACTION * INTERVAL_SECONDS[HORIZON_INTERVAL[horizon]]


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


@dataclass(frozen=True)
class PredictionRecord:
    """The fields of a stored prediction that evaluation needs (all optional-safe)."""

    source_id: str
    coin_id: str
    symbol: Optional[str]
    horizon: str
    reference_time: Optional[datetime]
    target_time: Optional[datetime]
    reference_price: Optional[float]
    predicted_return: Optional[float]
    direction: Optional[str]
    model: Optional[str]
    model_version: Optional[str]
    feature_version: Optional[str]
    generated_at: Optional[datetime]
    return_lower: Optional[float] = None
    return_upper: Optional[float] = None
    price_lower: Optional[float] = None
    price_upper: Optional[float] = None
    nominal_coverage: Optional[float] = None
    confidence: Optional[float] = None

    @classmethod
    def from_document(cls, doc: Mapping[str, Any]) -> "PredictionRecord":
        """Map a `predictions` document (Phase 13 schema) to a record. Never raises."""
        rng = doc.get("range") or {}
        pred = doc.get("prediction") or {}
        return cls(
            source_id=str(doc.get("_id")),
            coin_id=str(doc.get("coin_id")),
            symbol=doc.get("symbol"),
            horizon=str(doc.get("horizon", "")).lower(),
            reference_time=to_utc(doc.get("reference_time")),
            target_time=to_utc(doc.get("target_time")),
            reference_price=_num(doc.get("current_price")),
            predicted_return=_num(pred.get("predicted_return")),
            direction=doc.get("direction") if doc.get("direction") in DIRECTIONS else None,
            model=doc.get("model"),
            model_version=doc.get("model_version"),
            feature_version=doc.get("feature_version"),
            generated_at=to_utc(doc.get("generated_at")),
            return_lower=_num(rng.get("return_lower")),
            return_upper=_num(rng.get("return_upper")),
            price_lower=_num(rng.get("price_lower")),
            price_upper=_num(rng.get("price_upper")),
            nominal_coverage=_num(rng.get("nominal_coverage")),
            confidence=_num(doc.get("confidence")),
        )

    @property
    def dedupe_key(self) -> tuple:
        return (self.coin_id, self.horizon, self.model, self.model_version, self.reference_time)


@dataclass(frozen=True)
class Outcome:
    record: PredictionRecord
    status: OutcomeStatus
    reason: Optional[str] = None
    target_time: Optional[datetime] = None
    actual_price: Optional[float] = None
    actual_return: Optional[float] = None
    matched_close_time: Optional[datetime] = None
    match_gap_seconds: Optional[float] = None

    @property
    def matched(self) -> bool:
        return self.status == "matched"

    @property
    def actual_direction(self) -> Optional[str]:
        """up / down for non-zero actual returns, ``flat`` only for an exactly-zero return."""
        if self.actual_return is None:
            return None
        return "up" if self.actual_return > 0 else "down" if self.actual_return < 0 else "flat"


_MIN = datetime.min.replace(tzinfo=timezone.utc)
_MAX = datetime.max.replace(tzinfo=timezone.utc)


def _gen(record: PredictionRecord) -> datetime:
    return record.generated_at or _MIN


def dedupe_predictions(records: Iterable[PredictionRecord]) -> tuple[list[PredictionRecord], int]:
    """Collapse duplicate predictions (same coin/horizon/model/version/reference time).

    The most recently GENERATED copy is kept (ties: the later one in input order). Returns
    ``(kept, number_of_duplicates_dropped)`` with a deterministic order (reference time, then id).
    """
    best: dict[tuple, PredictionRecord] = {}
    dropped = 0
    for rec in records:
        key = rec.dedupe_key
        cur = best.get(key)
        if cur is None:
            best[key] = rec
            continue
        dropped += 1

        if _gen(rec) >= _gen(cur):
            best[key] = rec
    kept = sorted(best.values(), key=lambda r: (r.reference_time or _MAX, r.source_id))
    return kept, dropped


def match_prediction(record: PredictionRecord, series: Optional[PriceSeries], now: datetime) -> Outcome:
    """Evaluate ONE prediction at time ``now`` against ``series`` (real candles of the horizon's interval)."""
    now = to_utc(now)  # type: ignore[assignment]
    if record.horizon not in HORIZON_SECONDS:
        return Outcome(record, "unsupported_horizon", f"Horizon {record.horizon!r} is not supported.")
    if record.reference_time is None or record.predicted_return is None or record.direction is None:
        return Outcome(record, "invalid_record", "Prediction is missing its reference time, predicted return or direction.")

    horizon_seconds = HORIZON_SECONDS[record.horizon]
    tol = tolerance_seconds(record.horizon)
    target = record.reference_time + timedelta(seconds=horizon_seconds)
    # A stored target that disagrees with reference_time + horizon would make the evaluation ambiguous.
    if record.target_time is not None and abs((record.target_time - target).total_seconds()) > tol:
        return Outcome(record, "invalid_record", "Stored target_time is inconsistent with reference_time + horizon.", target)

    if now < target:
        return Outcome(record, "not_matured", "The prediction horizon has not elapsed yet.", target)

    if record.reference_price is None or record.reference_price <= 0:
        return Outcome(record, "missing_reference_price", "The prediction has no valid recorded reference price.", target)

    if series is None or len(series) == 0:
        return Outcome(record, "missing_future_price", "No historical candles are available for this coin/horizon.", target)

    visible = series if (series.as_of is not None and series.as_of <= now) else series.truncated(now)
    candle = visible.nearest_close(target, tol)
    if candle is None:
        last = visible.last_close_time
        if last is None or last < target - timedelta(seconds=tol):
            return Outcome(record, "stale_market_data",
                           "Available market data ends before the target time (data is stale or not yet synced).", target)
        return Outcome(record, "missing_future_price", "No completed candle exists near the target time (gap in market data).", target)

    actual_price = candle.close
    return Outcome(
        record, "matched", None, target,
        actual_price=actual_price,
        actual_return=actual_price / record.reference_price - 1.0,
        matched_close_time=candle.close_time,
        match_gap_seconds=abs((candle.close_time - target).total_seconds()),
    )
