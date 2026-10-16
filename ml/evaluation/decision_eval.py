"""Evaluate stored BUY / HOLD / SELL decisions against the price movement that FOLLOWED them.

Rule set (methodology 1.0.0)
----------------------------
* Reference price: the decision's recorded ``reference_price`` when present, otherwise the close of the last
  candle that was COMPLETE at ``generated_at`` (never a later price). It must be at most
  ``REFERENCE_MAX_AGE_INTERVALS`` intervals old, otherwise the decision is ``missing_reference_price``.
* Forward return at horizon H: close of the candle nearest ``generated_at + H`` (same tolerance rule as
  predictions) divided by the reference price, minus 1. Decisions whose horizon has not elapsed are
  ``not_matured`` and are never counted.
* BUY  -> *directionally aligned* when forward return > 0.
* SELL -> *directionally aligned* when forward return < 0.
* HOLD -> makes NO directional claim. It is reported with its mean/median forward return and the share of
  outcomes inside a neutral band (``HOLD_NEUTRAL_BAND[H]``, an explicit assumption), which is not "success".
* A decision with no BUY/HOLD/SELL value (insufficient data upstream) is excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean, median
from typing import Any, Iterable, Mapping, Optional

from ml.evaluation.constants import (
    HOLD_NEUTRAL_BAND,
    HORIZON_INTERVAL,
    HORIZON_SECONDS,
    INTERVAL_SECONDS,
    MIN_DECISION_SAMPLE_SIZE,
    REFERENCE_MAX_AGE_INTERVALS,
)
from ml.evaluation.matching import _num, tolerance_seconds
from ml.evaluation.series import PriceSeries
from ml.evaluation.timestamps import to_utc

DECISIONS = ("BUY", "HOLD", "SELL")


@dataclass(frozen=True)
class DecisionRecord:
    source_id: str
    coin_id: str
    symbol: Optional[str]
    decision: Optional[str]
    generated_at: Optional[datetime]
    reference_price: Optional[float]
    engine_version: Optional[str]
    confidence: Optional[float] = None

    @classmethod
    def from_document(cls, doc: Mapping[str, Any]) -> "DecisionRecord":
        d = doc.get("decision")
        return cls(
            source_id=str(doc.get("_id")), coin_id=str(doc.get("coin_id")), symbol=doc.get("symbol"),
            decision=d.upper() if isinstance(d, str) and d.upper() in DECISIONS else None,
            generated_at=to_utc(doc.get("generated_at")), reference_price=_num(doc.get("reference_price")),
            engine_version=doc.get("engine_version"), confidence=_num(doc.get("confidence")),
        )


@dataclass(frozen=True)
class DecisionOutcome:
    record: DecisionRecord
    horizon: str
    status: str            # matched | not_matured | missing_reference_price | missing_future_price | stale_market_data | invalid_record | unsupported_horizon
    reason: Optional[str] = None
    reference_price: Optional[float] = None
    reference_source: Optional[str] = None   # "recorded" | "candle_close"
    forward_return: Optional[float] = None
    target_time: Optional[datetime] = None

    @property
    def matched(self) -> bool:
        return self.status == "matched"


def evaluate_decision(record: DecisionRecord, horizon: str, series: Optional[PriceSeries], now: datetime) -> DecisionOutcome:
    now = to_utc(now)  # type: ignore[assignment]
    if horizon not in HORIZON_SECONDS:
        return DecisionOutcome(record, horizon, "unsupported_horizon", f"Horizon {horizon!r} is not supported.")
    if record.decision is None or record.generated_at is None:
        return DecisionOutcome(record, horizon, "invalid_record", "Decision has no BUY/HOLD/SELL value or timestamp.")
    target = record.generated_at + timedelta(seconds=HORIZON_SECONDS[horizon])
    if now < target:
        return DecisionOutcome(record, horizon, "not_matured", "The evaluation horizon has not elapsed yet.", target_time=target)

    interval = INTERVAL_SECONDS[HORIZON_INTERVAL[horizon]]
    visible = None
    if series is not None and len(series):
        visible = series if (series.as_of is not None and series.as_of <= now) else series.truncated(now)

    ref_price, ref_source = None, None
    if record.reference_price is not None and record.reference_price > 0:
        ref_price, ref_source = record.reference_price, "recorded"
    elif visible is not None:
        c = visible.last_completed_at(record.generated_at)
        if c is not None and (record.generated_at - c.close_time).total_seconds() <= REFERENCE_MAX_AGE_INTERVALS * interval:
            ref_price, ref_source = c.close, "candle_close"
    if ref_price is None:
        return DecisionOutcome(record, horizon, "missing_reference_price",
                               "No recorded or point-in-time reference price is available for this decision.", target_time=target)

    if visible is None:
        return DecisionOutcome(record, horizon, "missing_future_price", "No historical candles are available.",
                               ref_price, ref_source, target_time=target)
    tol = tolerance_seconds(horizon)
    candle = visible.nearest_close(target, tol)
    if candle is None:
        last = visible.last_close_time
        status = "stale_market_data" if (last is None or last < target - timedelta(seconds=tol)) else "missing_future_price"
        return DecisionOutcome(record, horizon, status, "No completed candle near the evaluation time.",
                               ref_price, ref_source, target_time=target)
    return DecisionOutcome(record, horizon, "matched", None, ref_price, ref_source, candle.close / ref_price - 1.0, target)


def _cell(outcomes: list[DecisionOutcome], decision: str, horizon: str, min_samples: int) -> dict[str, Any]:
    rs = [o.forward_return for o in outcomes if o.forward_return is not None]
    n = len(rs)
    cell: dict[str, Any] = {"decision": decision, "horizon": horizon, "count": n, "status": "ok" if n >= min_samples else ("no_data" if n == 0 else "insufficient_data"),
                            "mean_return": None, "median_return": None, "directional_agreement": None,
                            "within_neutral_band_rate": None}
    if n < min_samples:
        return cell
    cell["mean_return"], cell["median_return"] = fmean(rs), median(rs)
    if decision == "BUY":
        cell["directional_agreement"] = sum(1 for r in rs if r > 0) / n
    elif decision == "SELL":
        cell["directional_agreement"] = sum(1 for r in rs if r < 0) / n
    else:
        band = HOLD_NEUTRAL_BAND.get(horizon)
        cell["within_neutral_band_rate"] = (sum(1 for r in rs if abs(r) <= band) / n) if band else None
    return cell


def decision_metrics(outcomes: Iterable[DecisionOutcome], min_samples: int = MIN_DECISION_SAMPLE_SIZE) -> dict[str, Any]:
    """Per (decision, horizon) cells plus pooled BUY+SELL directional agreement per horizon."""
    all_out = list(outcomes)
    matched = [o for o in all_out if o.matched]
    cells = []
    pooled = []
    horizons = sorted({o.horizon for o in all_out}, key=lambda h: HORIZON_SECONDS.get(h, 0))
    for h in horizons:
        hm = [o for o in matched if o.horizon == h]
        for d in DECISIONS:
            cells.append(_cell([o for o in hm if o.record.decision == d], d, h, min_samples))
        directional = [o for o in hm if o.record.decision in ("BUY", "SELL")]
        n = len(directional)
        agree = sum(1 for o in directional if (o.forward_return > 0) == (o.record.decision == "BUY") and o.forward_return != 0)  # type: ignore[operator]
        pooled.append({"horizon": h, "count": n, "status": "ok" if n >= min_samples else ("no_data" if n == 0 else "insufficient_data"),
                       "directional_agreement": (agree / n) if n >= min_samples else None})
    times = [o.target_time for o in matched if o.target_time]
    return {
        "evaluated_decisions": len({o.record.source_id for o in matched}),
        "evaluations": len(matched),
        "by_decision_horizon": cells,
        "pooled_directional": pooled,
        "period_start": min(times) if times else None, "period_end": max(times) if times else None,
        "min_samples": min_samples,
        "hold_neutral_band": dict(HOLD_NEUTRAL_BAND),
    }
