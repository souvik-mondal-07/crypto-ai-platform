"""Model-accuracy and decision evaluation (Phase 17). Historical evaluation only — nothing here trades.

    stored predictions / decisions  +  real exchange candles  ->  outcome matching (ml.evaluation)
        -> `prediction_results` (one document per record+horizon, idempotent) -> metrics (cached) -> API

`refresh_outcomes` is the only place that downloads market data; the read endpoints only read stored results,
so opening the page never triggers an external call. Missing data is reported, never defaulted.
"""

import asyncio
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId

from app.config.backtest_config import (
    MAX_RESULTS_FOR_METRICS,
    METRICS_CACHE_TTL_SECONDS,
    REFRESH_MAX_RECORDS,
    REFRESH_MAX_SCAN,
    REFRESH_MIN_INTERVAL_SECONDS,
)
from app.core.exceptions import AppError
from app.providers.errors import ProviderError
from app.repositories.coin_repository import CoinRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.evaluation_result_repository import DECISION, PREDICTION, EvaluationResultRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.market_history import MarketHistory, cluster_windows
from app.services.user_feature_common import parse_coin_id

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from ml.evaluation.constants import (  # noqa: E402
    DECISION_HORIZONS,
    HORIZON_INTERVAL,
    HORIZON_SECONDS,
    INTERVAL_SECONDS,
    METHODOLOGY_VERSION,
    MIN_DECISION_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
    SUPPORTED_HORIZONS,
)
from ml.evaluation.decision_eval import DecisionOutcome, DecisionRecord, decision_metrics, evaluate_decision  # noqa: E402
from ml.evaluation.matching import Outcome, PredictionRecord, dedupe_predictions, match_prediction  # noqa: E402
from ml.evaluation.metrics import accuracy_metrics, group_metrics  # noqa: E402
from ml.evaluation.series import PriceSeries  # noqa: E402
from ml.evaluation.timestamps import to_utc  # noqa: E402

logger = logging.getLogger(__name__)

# Statuses that will not change when retried -> stored. Transient ones (stale data, provider failures) are retried.
_PERMANENT = {"matched", "missing_reference_price", "missing_future_price", "unsupported_horizon", "invalid_record"}

#: Process-wide state of the (single) outcome refresh. Public market data, so one refresh serves all users.
_refresh_lock = asyncio.Lock()
_refresh_state: dict[str, Any] = {"running": False, "last_started_at": None, "last_finished_at": None, "last_report": None, "last_error": None}
_metrics_cache: dict[tuple, tuple[float, Any]] = {}
_background: set[asyncio.Task] = set()


def reset_state_for_tests() -> None:
    _metrics_cache.clear()
    _refresh_state.update({"running": False, "last_started_at": None, "last_finished_at": None, "last_report": None, "last_error": None})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _combine(series_list: list[PriceSeries], interval: str, now: datetime) -> PriceSeries:
    """One series from several fetch windows (duplicates across windows collapse inside PriceSeries)."""
    return PriceSeries([c for s in series_list for c in s.candles], INTERVAL_SECONDS[interval], as_of=now)


def _row(row: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """A metrics row without the internal grouping `key`, plus named fields derived from it."""
    return {**{k: v for k, v in row.items() if k != "key"}, **extra}


# ---------------------------------------------------------------- stored result <-> pure objects
def prediction_result_to_doc(source: dict[str, Any], rec: PredictionRecord, out: Outcome, now: datetime) -> dict[str, Any]:
    return {
        "record_type": PREDICTION, "source_id": source["_id"], "coin_id": source.get("coin_id"), "symbol": rec.symbol,
        "horizon": rec.horizon, "model": rec.model, "model_version": rec.model_version, "feature_version": rec.feature_version,
        "direction": rec.direction, "predicted_return": rec.predicted_return, "confidence": rec.confidence,
        "reference_price": rec.reference_price, "reference_time": rec.reference_time, "target_time": out.target_time,
        "generated_at": rec.generated_at,
        "return_lower": rec.return_lower, "return_upper": rec.return_upper, "price_lower": rec.price_lower,
        "price_upper": rec.price_upper, "nominal_coverage": rec.nominal_coverage,
        "status": out.status, "reason": out.reason, "actual_price": out.actual_price, "actual_return": out.actual_return,
        "actual_direction": out.actual_direction, "matched_close_time": out.matched_close_time,
        "match_gap_seconds": out.match_gap_seconds, "methodology_version": METHODOLOGY_VERSION, "evaluated_at": now,
        # Fields of the schema planned in Step 2 for this collection, kept populated for compatibility:
        "prediction_id": source["_id"],
        "error": (rec.predicted_return - out.actual_return) if out.matched and rec.predicted_return is not None else None,
        "direction_correct": (rec.direction == out.actual_direction) if out.matched and rec.direction in ("up", "down") else None,
    }


def doc_to_outcome(doc: dict[str, Any]) -> Outcome:
    rec = PredictionRecord(
        source_id=str(doc.get("source_id")), coin_id=str(doc.get("coin_id")), symbol=doc.get("symbol"), horizon=doc.get("horizon", ""),
        reference_time=to_utc(doc.get("reference_time")), target_time=to_utc(doc.get("target_time")),
        reference_price=doc.get("reference_price"), predicted_return=doc.get("predicted_return"), direction=doc.get("direction"),
        model=doc.get("model"), model_version=doc.get("model_version"), feature_version=doc.get("feature_version"),
        generated_at=to_utc(doc.get("generated_at")), return_lower=doc.get("return_lower"), return_upper=doc.get("return_upper"),
        price_lower=doc.get("price_lower"), price_upper=doc.get("price_upper"), nominal_coverage=doc.get("nominal_coverage"),
        confidence=doc.get("confidence"),
    )
    return Outcome(rec, doc.get("status", "invalid_record"), doc.get("reason"), to_utc(doc.get("target_time")),
                   doc.get("actual_price"), doc.get("actual_return"), to_utc(doc.get("matched_close_time")), doc.get("match_gap_seconds"))


def decision_result_to_doc(source: dict[str, Any], out: DecisionOutcome, now: datetime) -> dict[str, Any]:
    rec = out.record
    return {
        "record_type": DECISION, "source_id": source["_id"], "coin_id": source.get("coin_id"), "symbol": rec.symbol,
        "horizon": out.horizon, "decision": rec.decision, "engine_version": rec.engine_version, "confidence": rec.confidence,
        "generated_at": rec.generated_at, "reference_price": out.reference_price, "reference_source": out.reference_source,
        "forward_return": out.forward_return, "target_time": out.target_time, "status": out.status, "reason": out.reason,
        "methodology_version": METHODOLOGY_VERSION, "evaluated_at": now,
    }


def doc_to_decision_outcome(doc: dict[str, Any]) -> DecisionOutcome:
    rec = DecisionRecord(str(doc.get("source_id")), str(doc.get("coin_id")), doc.get("symbol"), doc.get("decision"),
                         to_utc(doc.get("generated_at")), doc.get("reference_price"), doc.get("engine_version"), doc.get("confidence"))
    return DecisionOutcome(rec, doc.get("horizon", ""), doc.get("status", "invalid_record"), doc.get("reason"),
                           doc.get("reference_price"), doc.get("reference_source"), doc.get("forward_return"), to_utc(doc.get("target_time")))


class EvaluationService:
    def __init__(
        self,
        predictions: Optional[PredictionRepository] = None,
        decisions: Optional[DecisionRepository] = None,
        results: Optional[EvaluationResultRepository] = None,
        coins: Optional[CoinRepository] = None,
        history: Optional[MarketHistory] = None,
    ) -> None:
        self._predictions = predictions or PredictionRepository()
        self._decisions = decisions or DecisionRepository()
        self._results = results or EvaluationResultRepository()
        self._coins = coins or CoinRepository()
        self._history = history or MarketHistory()

    # ------------------------------------------------------------------ refresh (the only place that downloads candles)
    @staticmethod
    def refresh_state() -> dict[str, Any]:
        return dict(_refresh_state)

    async def start_refresh(self) -> dict[str, Any]:
        """Kick off outcome matching in the background and return immediately (never blocks the request)."""
        if _refresh_lock.locked() or _refresh_state["running"]:
            return {**self.refresh_state(), "accepted": False, "message": "An outcome refresh is already running."}
        finished = _refresh_state["last_finished_at"]
        if finished and (_utcnow() - finished).total_seconds() < REFRESH_MIN_INTERVAL_SECONDS:
            return {**self.refresh_state(), "accepted": False, "message": "Outcomes were refreshed moments ago."}
        _refresh_state.update({"running": True, "last_started_at": _utcnow(), "last_error": None})
        task = asyncio.create_task(self._run_refresh())
        _background.add(task)
        task.add_done_callback(_background.discard)
        return {**self.refresh_state(), "accepted": True, "message": "Outcome matching started."}

    async def _run_refresh(self) -> None:
        async with _refresh_lock:
            try:
                report = await self.refresh_outcomes()
                _refresh_state.update({"last_report": report, "last_error": None})
            except Exception as exc:  # background task: record, never raise into the event loop
                logger.warning("Outcome refresh failed", exc_info=True)
                _refresh_state["last_error"] = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                _refresh_state.update({"running": False, "last_finished_at": _utcnow()})
                _metrics_cache.clear()

    async def refresh_outcomes(self, now: Optional[datetime] = None) -> dict[str, Any]:
        """Match matured predictions and decisions with real candles and store the results (idempotent)."""
        now = to_utc(now) if now else _utcnow()
        report: dict[str, Any] = {"methodology_version": METHODOLOGY_VERSION, "predictions": await self._refresh_predictions(now),
                                  "decisions": await self._refresh_decisions(now)}
        return report

    async def _binance_symbols(self, coin_ids: set[ObjectId]) -> dict[ObjectId, Optional[str]]:
        docs = await self._coins.find_by_internal_ids(list(coin_ids)) if coin_ids else {}
        return {oid: ((docs.get(oid, {}).get("providers") or {}).get("binance") or {}).get("symbol") for oid in coin_ids}

    async def _refresh_predictions(self, now: datetime) -> dict[str, Any]:
        stats: dict[str, Any] = {"scanned": 0, "pending": 0, "stored": 0, "matched": 0, "by_status": defaultdict(int), "provider_errors": 0, "capped": False}
        pending: list[tuple[dict[str, Any], PredictionRecord]] = []
        skip = 0
        while stats["scanned"] < REFRESH_MAX_SCAN and len(pending) < REFRESH_MAX_RECORDS:
            page = await self._predictions.list_matured(now, skip=skip, limit=500)
            if not page:
                break
            skip += len(page)
            stats["scanned"] += len(page)
            done = await self._results.existing_keys(PREDICTION, [d["_id"] for d in page])
            for d in page:
                rec = PredictionRecord.from_document(d)
                if (d["_id"], rec.horizon) not in done:
                    pending.append((d, rec))
            if len(page) < 500:
                break
        stats["capped"] = len(pending) >= REFRESH_MAX_RECORDS
        pending = pending[:REFRESH_MAX_RECORDS]
        stats["pending"] = len(pending)

        by_coin_interval: dict[tuple[ObjectId, str], list[tuple[dict[str, Any], PredictionRecord]]] = defaultdict(list)
        for d, rec in pending:
            interval = HORIZON_INTERVAL.get(rec.horizon)
            if interval is None or rec.reference_time is None:
                await self._store_prediction(d, rec, match_prediction(rec, None, now), now, stats)
                continue
            by_coin_interval[(d["coin_id"], interval)].append((d, rec))
        symbols = await self._binance_symbols({k[0] for k in by_coin_interval})
        for (coin_oid, interval), items in by_coin_interval.items():
            symbol = symbols.get(coin_oid)
            targets = [to_utc(r.reference_time) + timedelta(seconds=HORIZON_SECONDS[r.horizon]) for _, r in items]  # type: ignore[operator]
            windows = cluster_windows(targets, interval)
            series_list = []
            failed = False
            if symbol:
                for w_start, w_end in windows:
                    s, e = self._history.padded(w_start, w_end, interval)
                    try:
                        series_list.append(await self._history.series(symbol, interval, s, e, as_of=now))
                    except ProviderError:
                        failed = True
                        stats["provider_errors"] += 1
                        break
            if failed:
                continue  # transient: nothing stored, retried on the next refresh
            combined = _combine(series_list, interval, now)
            for (d, rec), target in zip(items, targets):
                if symbol is None:
                    out = Outcome(rec, "missing_future_price", "The coin has no Binance market mapping, so no actual price history is available.", target)
                else:
                    if len(combined) == 0:
                        continue  # empty download is indistinguishable from an outage: retry later, store nothing
                    out = match_prediction(rec, combined, now)
                await self._store_prediction(d, rec, out, now, stats)
        stats["by_status"] = dict(stats["by_status"])
        return stats

    async def _store_prediction(self, source: dict[str, Any], rec: PredictionRecord, out: Outcome, now: datetime, stats: dict[str, Any]) -> None:
        stats["by_status"][out.status] += 1
        if out.status not in _PERMANENT:
            return
        await self._results.upsert(prediction_result_to_doc(source, rec, out, now))
        stats["stored"] += 1
        if out.matched:
            stats["matched"] += 1

    async def _refresh_decisions(self, now: datetime) -> dict[str, Any]:
        stats: dict[str, Any] = {"scanned": 0, "pending": 0, "stored": 0, "matched": 0, "by_status": defaultdict(int), "provider_errors": 0, "capped": False}
        shortest = timedelta(seconds=min(HORIZON_SECONDS[h] for h in DECISION_HORIZONS))
        pending: list[tuple[dict[str, Any], DecisionRecord, str]] = []
        skip = 0
        while stats["scanned"] < REFRESH_MAX_SCAN and len(pending) < REFRESH_MAX_RECORDS:
            page = await self._decisions.list_matured(now - shortest, skip=skip, limit=500)
            if not page:
                break
            skip += len(page)
            stats["scanned"] += len(page)
            done = await self._results.existing_keys(DECISION, [d["_id"] for d in page])
            for d in page:
                rec = DecisionRecord.from_document(d)
                if rec.decision is None or rec.generated_at is None:
                    continue  # no BUY/HOLD/SELL to evaluate (insufficient-data decisions are excluded by rule)
                for h in DECISION_HORIZONS:
                    if now >= rec.generated_at + timedelta(seconds=HORIZON_SECONDS[h]) and (d["_id"], h) not in done:
                        pending.append((d, rec, h))
            if len(page) < 500:
                break
        stats["capped"] = len(pending) >= REFRESH_MAX_RECORDS
        pending = pending[:REFRESH_MAX_RECORDS]
        stats["pending"] = len(pending)

        groups: dict[tuple[ObjectId, str], list[tuple[dict[str, Any], DecisionRecord, str]]] = defaultdict(list)
        for item in pending:
            groups[(item[0]["coin_id"], HORIZON_INTERVAL[item[2]])].append(item)
        symbols = await self._binance_symbols({k[0] for k in groups})
        for (coin_oid, interval), items in groups.items():
            symbol = symbols.get(coin_oid)
            step = timedelta(seconds=INTERVAL_SECONDS[interval])
            if symbol is None:
                for d, rec, h in items:
                    out = DecisionOutcome(rec, h, "missing_future_price", "The coin has no Binance market mapping.", target_time=rec.generated_at + timedelta(seconds=HORIZON_SECONDS[h]))
                    await self._store_decision(d, out, now, stats)
                continue
            times = [rec.generated_at - 2 * step for _, rec, _ in items] + [rec.generated_at + timedelta(seconds=HORIZON_SECONDS[h]) for _, rec, h in items]
            windows = cluster_windows(times, interval)
            series_list = []
            failed = False
            for w_start, w_end in windows:
                s, e = self._history.padded(w_start, w_end, interval)
                try:
                    series_list.append(await self._history.series(symbol, interval, s, e, as_of=now))
                except ProviderError:
                    failed = True
                    stats["provider_errors"] += 1
                    break
            if failed:
                continue
            combined = _combine(series_list, interval, now)
            if len(combined) == 0:
                continue  # nothing downloaded: retry later, store nothing
            for d, rec, h in items:
                await self._store_decision(d, evaluate_decision(rec, h, combined, now), now, stats)
        stats["by_status"] = dict(stats["by_status"])
        return stats

    async def _store_decision(self, source: dict[str, Any], out: DecisionOutcome, now: datetime, stats: dict[str, Any]) -> None:
        stats["by_status"][out.status] += 1
        if out.status not in _PERMANENT:
            return
        await self._results.upsert(decision_result_to_doc(source, out, now))
        stats["stored"] += 1
        if out.matched:
            stats["matched"] += 1

    # ------------------------------------------------------------------ reads
    async def _cached(self, key: tuple, record_type: str, build):  # type: ignore[no-untyped-def]
        fingerprint = (await self._results.count(record_type), await self._results.latest_evaluated_at(record_type))
        hit = _metrics_cache.get(key)
        if hit and time.monotonic() - hit[0] < METRICS_CACHE_TTL_SECONDS and hit[2] == fingerprint:
            return hit[1]
        value = await build()
        _metrics_cache[key] = (time.monotonic(), value, fingerprint)
        return value

    async def accuracy(self, *, coin_id: Optional[str] = None, horizon: Optional[str] = None,
                       model: Optional[str] = None, model_version: Optional[str] = None) -> dict[str, Any]:
        coin_oid = parse_coin_id(coin_id) if coin_id else None
        if horizon is not None and horizon not in SUPPORTED_HORIZONS:
            raise AppError(422, "UNSUPPORTED_HORIZON", f"horizon must be one of {', '.join(SUPPORTED_HORIZONS)}.")
        coin_doc = None
        if coin_oid is not None:
            coin_doc = await self._coins.find_by_internal_id(coin_id)  # type: ignore[arg-type]
            if coin_doc is None:
                raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        key = ("accuracy", coin_id, horizon, model, model_version)
        data = await self._cached(key, PREDICTION, lambda: self._build_accuracy(coin_oid, horizon, model, model_version))
        return {**data, "coin": ({"id": coin_id, "symbol": coin_doc.get("symbol"), "name": coin_doc.get("name")} if coin_doc else None)}

    async def _build_accuracy(self, coin_oid: Optional[ObjectId], horizon: Optional[str], model: Optional[str], model_version: Optional[str]) -> dict[str, Any]:
        now = _utcnow()
        filters = dict(coin_id=coin_oid, horizon=horizon, model=model, model_version=model_version)
        matched_docs = await self._results.find(PREDICTION, limit=MAX_RESULTS_FOR_METRICS, status="matched", **filters)
        outcomes = [doc_to_outcome(d) for d in matched_docs]
        deduped, dup_dropped = dedupe_predictions([o.record for o in outcomes])
        keep = {r.source_id for r in deduped}
        outcomes = [o for o in outcomes if o.record.source_id in keep]
        overall = accuracy_metrics(outcomes, MIN_SAMPLE_SIZE)

        by_status: dict[str, int] = {}
        for status in ("missing_reference_price", "missing_future_price", "unsupported_horizon", "invalid_record"):
            n = await self._results.count(PREDICTION, status=status, **filters)
            if n:
                by_status[status] = n
        total_predictions = await self._predictions.count_total()
        matured = await self._predictions.count_matured(now)
        evaluated_any = await self._results.count(PREDICTION)
        pending = max(matured - evaluated_any, 0)
        by_horizon = group_metrics(outcomes, lambda o: o.record.horizon, MIN_SAMPLE_SIZE)
        by_model = group_metrics(outcomes, lambda o: (o.record.model, o.record.model_version), MIN_SAMPLE_SIZE)
        by_coin = group_metrics(outcomes, lambda o: (o.record.coin_id, o.record.symbol), MIN_SAMPLE_SIZE)
        by_coin.sort(key=lambda r: -r["sample_size"])
        pairs = await self._results.distinct_pairs(PREDICTION)
        options = {
            "horizons": sorted({p["horizon"] for p in pairs}, key=lambda h: HORIZON_SECONDS.get(h, 0)),
            "models": sorted({p["model"] for p in pairs if p.get("model")}),
            "model_versions": sorted({f'{p["model"]}|{p["model_version"]}' for p in pairs if p.get("model")}),
            "coins": sorted({(str(p["coin_id"]), p.get("symbol") or "") for p in pairs}, key=lambda x: x[1]),
        }
        limitations = []
        if total_predictions == 0:
            limitations.append("No predictions have been stored yet, so no accuracy can be evaluated.")
        elif matured == 0:
            limitations.append("Stored predictions have not reached their horizon yet; nothing has matured.")
        if pending:
            limitations.append(f"{pending} matured prediction(s) have not been matched to market outcomes yet; use 'Update outcomes'.")
        if overall["status"] == "insufficient_data":
            limitations.append(f"At least {MIN_SAMPLE_SIZE} matched predictions are needed for reliable metrics.")
        return {
            "methodology_version": METHODOLOGY_VERSION, "generated_at": now,
            "filters": {"coin_id": str(coin_oid) if coin_oid else None, "horizon": horizon, "model": model, "model_version": model_version},
            "overall": overall,
            "by_horizon": [_row(r, horizon=r["key"]) for r in by_horizon],
            "by_model": [_row(r, model=r["key"][0], model_version=r["key"][1]) for r in by_model],
            "by_coin": [_row(r, coin_id=r["key"][0], symbol=r["key"][1]) for r in by_coin[:50]],
            "coverage": {"total_predictions": total_predictions, "matured_predictions": matured, "matched_outcomes": len(outcomes),
                         "pending_outcomes": pending, "duplicates_removed": dup_dropped, "unmatched_by_status": by_status},
            "options": {"horizons": options["horizons"], "models": options["models"],
                        "model_versions": [{"model": m.split("|")[0], "model_version": m.split("|")[1]} for m in options["model_versions"]],
                        "coins": [{"id": c, "symbol": s} for c, s in options["coins"]]},
            "limitations": limitations,
        }

    async def decisions(self, *, coin_id: Optional[str] = None, horizon: Optional[str] = None) -> dict[str, Any]:
        coin_oid = parse_coin_id(coin_id) if coin_id else None
        if horizon is not None and horizon not in DECISION_HORIZONS:
            raise AppError(422, "UNSUPPORTED_HORIZON", f"Decision horizon must be one of {', '.join(DECISION_HORIZONS)}.")
        return await self._cached(("decisions", coin_id, horizon), DECISION, lambda: self._build_decisions(coin_oid, horizon))

    async def _build_decisions(self, coin_oid: Optional[ObjectId], horizon: Optional[str]) -> dict[str, Any]:
        docs = await self._results.find(DECISION, limit=MAX_RESULTS_FOR_METRICS, status="matched", coin_id=coin_oid, horizon=horizon)
        outcomes = [doc_to_decision_outcome(d) for d in docs]
        metrics = decision_metrics(outcomes, MIN_DECISION_SAMPLE_SIZE)
        seen: dict[str, set[str]] = defaultdict(set)
        for o in outcomes:
            seen[o.record.decision or "UNKNOWN"].add(o.record.source_id)
        counts = {k: len(v) for k, v in seen.items()}
        total_decisions = await self._decisions.count_total()
        limitations = []
        if total_decisions == 0:
            limitations.append("No decisions have been stored yet, so none can be evaluated.")
        elif not outcomes:
            limitations.append("No stored decision has reached an evaluation horizon with market data yet.")
        limitations.append("HOLD makes no directional claim: it is reported by forward return and neutral-band rate, not as success or failure.")
        return {"methodology_version": METHODOLOGY_VERSION, "generated_at": _utcnow(),
                "filters": {"coin_id": str(coin_oid) if coin_oid else None, "horizon": horizon},
                "horizons": list(DECISION_HORIZONS), "total_decisions_stored": total_decisions,
                "decision_counts": counts, "metrics": metrics, "limitations": limitations}
