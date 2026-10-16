"""Backtest runs (Phase 17): validation, background execution and user-scoped storage.

A run replays the STORED Phase 14 decisions over REAL exchange candles with the pure engine in
`ml.evaluation.backtest`. It is a simulation: no order is ever placed. The owner is always the authenticated
user (from the JWT); the request body cannot name a user. Runs execute as background tasks (the same
`asyncio.create_task` approach the schedulers use) so the request returns immediately with status `queued`.
"""

import asyncio
import logging
import sys
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId

from app.config.backtest_config import (
    MAX_BACKTEST_DAYS,
    MAX_BARS_PER_COIN,
    MAX_CAPITAL,
    MAX_CONCURRENT_RUNS_PER_USER,
    MAX_COINS_PER_BACKTEST,
    MAX_STORED_EQUITY_POINTS,
    MAX_STORED_TRADES,
    MIN_BACKTEST_DAYS,
    RUN_STALE_AFTER_SECONDS,
)
from app.core.exceptions import AppError
from app.providers.errors import ProviderError
from app.repositories.backtest_run_repository import BacktestRunRepository
from app.repositories.coin_repository import CoinRepository
from app.repositories.decision_repository import DecisionRepository
from app.schemas.backtesting import BacktestRunCreate
from app.services.market_history import MarketHistory
from app.services.user_feature_common import parse_coin_id

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from ml.evaluation.backtest import BacktestConfig, Signal, run_backtest  # noqa: E402
from ml.evaluation.backtest_metrics import downsample  # noqa: E402
from ml.evaluation.constants import BACKTEST_ENGINE_VERSION, INTERVAL_SECONDS, STRATEGY_PHASE14  # noqa: E402
from ml.evaluation.series import PriceSeries  # noqa: E402
from ml.evaluation.timestamps import to_utc  # noqa: E402

logger = logging.getLogger(__name__)

DISCLAIMER = ("Simulated results on historical data under the stated assumptions. They are not a forecast and not a "
              "guarantee of future performance. No real orders are placed.")
_VALID_DECISIONS = ("BUY", "HOLD", "SELL")
_background: set[asyncio.Task] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return to_utc(value)  # type: ignore[return-value]


def aware_deep(value: Any) -> Any:
    """MongoDB returns naive UTC datetimes; make every one explicit UTC so JSON carries a `Z`/offset
    (a naive ISO string would be parsed as LOCAL time by browsers)."""
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, dict):
        return {k: aware_deep(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [aware_deep(v) for v in value]
    return value


def _pt(points: list[tuple[datetime, float]]) -> list[dict[str, Any]]:
    return [{"time": t, "value": v} for t, v in downsample(points, MAX_STORED_EQUITY_POINTS)]


class BacktestService:
    def __init__(
        self,
        runs: Optional[BacktestRunRepository] = None,
        coins: Optional[CoinRepository] = None,
        decisions: Optional[DecisionRepository] = None,
        history: Optional[MarketHistory] = None,
    ) -> None:
        self._runs = runs or BacktestRunRepository()
        self._coins = coins or CoinRepository()
        self._decisions = decisions or DecisionRepository()
        self._history = history or MarketHistory()

    # ------------------------------------------------------------------ create
    async def create_run(self, user_id: ObjectId, payload: BacktestRunCreate, *, run_in_background: bool = True) -> dict[str, Any]:
        config, coin_oids = self._validate(payload)
        if await self._runs.count_active_for_user(user_id) >= MAX_CONCURRENT_RUNS_PER_USER:
            raise AppError(429, "BACKTEST_LIMIT", f"You can have at most {MAX_CONCURRENT_RUNS_PER_USER} backtests running at once.")
        coin_docs: dict[str, dict[str, Any]] = {}
        for cid, oid in zip(payload.coin_ids, coin_oids):
            doc = await self._coins.find_by_internal_id(cid)
            if doc is None:
                raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{cid}'.")
            coin_docs[cid] = doc
        now = _utcnow()
        run_id = uuid.uuid4().hex
        document = {
            "run_id": run_id, "user_id": user_id, "status": "queued", "result_status": None,
            "created_at": now, "updated_at": now, "started_at": None, "finished_at": None,
            "engine_version": BACKTEST_ENGINE_VERSION, "strategy": STRATEGY_PHASE14,
            "coin_ids": list(payload.coin_ids), "symbols": [coin_docs[c].get("symbol") or "" for c in payload.coin_ids],
            "period_start": config.start, "period_end": config.end, "starting_capital": config.starting_capital,
            "assumptions": config.assumptions(), "summary": None, "equity_curve": [], "benchmark_curve": [], "trades": [],
            "trades_truncated": False, "warnings": [], "data_summary": [], "reason": None, "error": None,
        }
        await self._runs.insert(document)
        if run_in_background:
            task = asyncio.create_task(self._execute(user_id, run_id, config, coin_docs))
            _background.add(task)
            task.add_done_callback(_background.discard)
        return self.to_summary(document)

    def _validate(self, payload: BacktestRunCreate) -> tuple[BacktestConfig, list[ObjectId]]:
        start, end = _aware(payload.start), _aware(payload.end)
        now = _utcnow()
        if start >= end:
            raise AppError(422, "INVALID_DATE_RANGE", "start must be before end.")
        if end > now + timedelta(minutes=1):
            raise AppError(422, "INVALID_DATE_RANGE", "end cannot be in the future: backtests use historical data only.")
        days = (end - start).total_seconds() / 86400
        if days < MIN_BACKTEST_DAYS:
            raise AppError(422, "INVALID_DATE_RANGE", f"The period must be at least {MIN_BACKTEST_DAYS} day(s).")
        if days > MAX_BACKTEST_DAYS:
            raise AppError(422, "INVALID_DATE_RANGE", f"The period cannot exceed {MAX_BACKTEST_DAYS} days.")
        bars = (end - start).total_seconds() / INTERVAL_SECONDS[payload.bar_interval]
        if bars > MAX_BARS_PER_COIN:
            raise AppError(422, "TOO_MANY_BARS", f"{int(bars)} bars per coin exceeds the limit of {MAX_BARS_PER_COIN}; use a coarser bar interval or a shorter period.")
        if len(set(payload.coin_ids)) != len(payload.coin_ids):
            raise AppError(422, "DUPLICATE_COINS", "coin_ids must not contain duplicates.")
        if len(payload.coin_ids) > MAX_COINS_PER_BACKTEST:
            raise AppError(422, "TOO_MANY_COINS", f"At most {MAX_COINS_PER_BACKTEST} coins per backtest.")
        oids = [parse_coin_id(c) for c in payload.coin_ids]
        if payload.starting_capital > MAX_CAPITAL:
            raise AppError(422, "INVALID_CAPITAL", "starting_capital is too large.")
        if payload.sizing_mode == "fixed_fraction" and payload.position_size > 1:
            raise AppError(422, "INVALID_POSITION_SIZE", "position_size must be between 0 and 1 for fixed_fraction sizing.")
        if payload.sizing_mode == "fixed_amount" and payload.position_size > payload.starting_capital:
            raise AppError(422, "INVALID_POSITION_SIZE", "position_size (amount) cannot exceed starting_capital.")
        config = BacktestConfig(
            coin_ids=tuple(payload.coin_ids), start=start, end=end, starting_capital=payload.starting_capital,
            bar_interval=payload.bar_interval, sizing_mode=payload.sizing_mode, position_size=payload.position_size,
            max_allocation_pct=payload.max_allocation_pct, fee_rate=payload.fee_rate, slippage_rate=payload.slippage_rate,
            close_open_positions_at_end=payload.close_open_positions_at_end,
        )
        try:
            config.validate()
        except ValueError as exc:
            raise AppError(422, "INVALID_BACKTEST_CONFIG", str(exc)) from exc
        return config, oids

    # ------------------------------------------------------------------ execute (background)
    async def _execute(self, user_id: ObjectId, run_id: str, config: BacktestConfig, coin_docs: dict[str, dict[str, Any]]) -> None:
        try:
            await self._runs.update_for_user(user_id, run_id, {"status": "running", "started_at": _utcnow(), "updated_at": _utcnow()})
            now = _utcnow()
            series: dict[str, PriceSeries] = {}
            signals: dict[str, list[Signal]] = {}
            data_summary: list[dict[str, Any]] = []
            for cid in config.coin_ids:
                doc = coin_docs[cid]
                symbol = ((doc.get("providers") or {}).get("binance") or {}).get("symbol")
                entry = {"coin_id": cid, "symbol": doc.get("symbol"), "bars": 0, "decisions": 0, "note": None}
                if not symbol:
                    entry["note"] = "No Binance market mapping: excluded because no real price history is available."
                    data_summary.append(entry)
                    continue
                s = await self._history.series(symbol, config.bar_interval, config.start, config.end, as_of=min(now, config.end),
                                               max_candles=MAX_BARS_PER_COIN + 5)
                series[cid] = s
                entry["bars"] = len([c for c in s.candles if config.start <= c.open_time < config.end])
                docs = await self._decisions.list_between(ObjectId(cid), config.start, config.end)
                signals[cid] = [Signal(_aware(d["generated_at"]), d["decision"].upper(), str(d["_id"]))
                                for d in docs if isinstance(d.get("decision"), str) and d["decision"].upper() in _VALID_DECISIONS and d.get("generated_at")]
                entry["decisions"] = len(signals[cid])
                if entry["bars"] == 0:
                    entry["note"] = "No candles were returned for this coin and period."
                data_summary.append(entry)

            usable = tuple(c for c in config.coin_ids if c in series and entry_bars(data_summary, c) > 0)
            if not usable:
                await self._finish(user_id, run_id, result_status="insufficient_data", data_summary=data_summary,
                                   reason="No real historical candles were available for the selected coins and period.")
                return
            run_config = replace(config, coin_ids=usable)
            result = await asyncio.to_thread(run_backtest, run_config, series, signals)
            if result.status != "ok":
                await self._finish(user_id, run_id, result_status="insufficient_data", data_summary=data_summary, reason=result.reason)
                return
            symbols = {c: coin_docs[c].get("symbol") for c in usable}
            trades = [{**t, "symbol": symbols.get(t["coin_id"])} for t in result.trades]
            truncated = len(trades) > MAX_STORED_TRADES
            warnings = list(result.warnings)
            skipped = [e["coin_id"] for e in data_summary if e["coin_id"] not in usable]
            if skipped:
                warnings.append(f"{len(skipped)} selected coin(s) had no usable price history and were excluded.")
            if result.summary["decisions_in_period"] == 0:
                reason, rstatus = "No stored Phase 14 decisions exist for the selected coins in this period, so the strategy made no trades. Decisions are only stored when they are generated.", "insufficient_data"
            else:
                reason, rstatus = None, "ok"
                if result.summary["number_of_trades"] < 30:
                    warnings.append(f"Only {result.summary['number_of_trades']} closed trade(s): win rate and average returns are statistically unreliable.")
            await self._finish(
                user_id, run_id, result_status=rstatus, reason=reason, data_summary=data_summary, warnings=warnings,
                summary=result.summary,
                equity_curve=_pt(result.equity_curve), benchmark_curve=_pt(result.benchmark_curve),
                trades=trades[:MAX_STORED_TRADES], trades_truncated=truncated,
            )
        except ProviderError as exc:
            await self._fail(user_id, run_id, f"Market data provider error: {exc}")
        except Exception as exc:  # never leave a run stuck in "running"
            logger.warning("Backtest %s failed", run_id, exc_info=True)
            await self._fail(user_id, run_id, f"{type(exc).__name__}: {exc}")

    async def _finish(self, user_id: ObjectId, run_id: str, *, result_status: str, data_summary: list[dict[str, Any]],
                      reason: Optional[str] = None, warnings: Optional[list[str]] = None, summary: Optional[dict[str, Any]] = None,
                      equity_curve: Optional[list[dict[str, Any]]] = None, benchmark_curve: Optional[list[dict[str, Any]]] = None,
                      trades: Optional[list[dict[str, Any]]] = None, trades_truncated: bool = False) -> None:
        now = _utcnow()
        await self._runs.update_for_user(user_id, run_id, {
            "status": "completed", "result_status": result_status, "reason": reason, "finished_at": now, "updated_at": now,
            "summary": summary, "equity_curve": equity_curve or [], "benchmark_curve": benchmark_curve or [],
            "trades": trades or [], "trades_truncated": trades_truncated, "warnings": warnings or [], "data_summary": data_summary,
        })

    async def _fail(self, user_id: ObjectId, run_id: str, message: str) -> None:
        now = _utcnow()
        await self._runs.update_for_user(user_id, run_id, {"status": "failed", "error": message[:500], "finished_at": now, "updated_at": now})

    async def fail_interrupted_runs(self) -> int:
        """Startup hygiene: runs left queued/running by a previous process can never finish."""
        now = _utcnow()
        return await self._runs.fail_stale(now - timedelta(seconds=RUN_STALE_AFTER_SECONDS), now, "The run was interrupted before it finished (server restart).")

    # ------------------------------------------------------------------ read (always scoped by the authenticated user)
    async def get_run(self, user_id: ObjectId, run_id: str) -> dict[str, Any]:
        doc = await self._runs.get_for_user(user_id, run_id)
        if doc is None:  # same 404 whether the run does not exist or belongs to someone else
            raise AppError(404, "BACKTEST_NOT_FOUND", "Backtest run not found.")
        await self._expire_if_stale(user_id, doc)
        return self.to_detail(doc)

    async def list_runs(self, user_id: ObjectId, page: int, limit: int) -> dict[str, Any]:
        docs = await self._runs.list_for_user(user_id, skip=(page - 1) * limit, limit=limit)
        for d in docs:
            await self._expire_if_stale(user_id, d)
        return {"items": [self.to_summary(d) for d in docs], "total": await self._runs.count_for_user(user_id), "page": page, "limit": limit}

    async def list_trades(self, user_id: ObjectId, run_id: str, page: int, limit: int) -> dict[str, Any]:
        doc = await self._runs.get_for_user(user_id, run_id)
        if doc is None:
            raise AppError(404, "BACKTEST_NOT_FOUND", "Backtest run not found.")
        trades = doc.get("trades") or []
        start = (page - 1) * limit
        return {"items": aware_deep(trades[start:start + limit]), "total": len(trades), "page": page, "limit": limit}

    async def _expire_if_stale(self, user_id: ObjectId, doc: dict[str, Any]) -> None:
        if doc.get("status") in ("queued", "running") and doc.get("updated_at"):
            if (_utcnow() - _aware(doc["updated_at"])).total_seconds() > RUN_STALE_AFTER_SECONDS:
                doc["status"], doc["error"] = "failed", "The run was interrupted before it finished."
                await self._fail(user_id, doc["run_id"], doc["error"])

    # ------------------------------------------------------------------ mapping
    @staticmethod
    def to_summary(doc: dict[str, Any]) -> dict[str, Any]:
        summary = doc.get("summary") or {}
        return aware_deep({
            "run_id": doc["run_id"], "status": doc["status"], "result_status": doc.get("result_status"),
            "created_at": doc["created_at"], "started_at": doc.get("started_at"), "finished_at": doc.get("finished_at"),
            "engine_version": doc["engine_version"], "strategy": doc["strategy"], "coin_ids": doc["coin_ids"],
            "symbols": doc.get("symbols", []), "period_start": doc["period_start"], "period_end": doc["period_end"],
            "starting_capital": doc["starting_capital"], "total_return": summary.get("total_return"),
            "max_drawdown": summary.get("max_drawdown"), "number_of_trades": summary.get("number_of_trades"), "error": doc.get("error"),
        })

    @classmethod
    def to_detail(cls, doc: dict[str, Any]) -> dict[str, Any]:
        return aware_deep({
            **cls.to_summary(doc), "reason": doc.get("reason"), "assumptions": doc["assumptions"], "summary": doc.get("summary"),
            "equity_curve": doc.get("equity_curve") or [], "benchmark_curve": doc.get("benchmark_curve") or [],
            "trade_count": len(doc.get("trades") or []), "trades_truncated": bool(doc.get("trades_truncated")),
            "warnings": doc.get("warnings") or [], "data_summary": doc.get("data_summary") or [], "disclaimer": DISCLAIMER,
        })


def entry_bars(data_summary: list[dict[str, Any]], coin_id: str) -> int:
    return next((e["bars"] for e in data_summary if e["coin_id"] == coin_id), 0)
