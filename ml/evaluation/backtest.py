"""Chronological, cost-aware backtest of the stored Phase 14 decisions (engine 1.0.0).

Strategy (``phase14_decisions``) — a *simulation only*; nothing here can place an order:
  BUY   and flat in that coin  -> open a long position
  SELL  and long in that coin  -> close the whole position
  HOLD / repeated BUY / SELL while flat -> no action (long-only; no shorting, no leverage, no pyramiding)

Timing / look-ahead rules
  * A decision generated at time t is known from t onward. It is executed at the OPEN of the first bar whose
    open time is >= t ("next-bar open"). The bar that contained t is never used to price the entry.
  * Only decisions with ``start <= generated_at <= bar open`` are visible at a bar; later decisions cannot
    influence earlier bars, and several decisions between two bars collapse to the most recent one.
  * Position sizing uses equity valued at prices known at that bar's open (other coins use their last close).
  * Equity is marked at each bar's close. Missing bars carry the last known close forward (never a future one).

Costs (explicit in every result): ``fee_rate`` per side on notional, ``slippage_rate`` adverse to the trade
(buys fill at open*(1+s), sells at open*(1-s)). Zero costs are accepted only when configured explicitly.

End of period: open positions are closed at the final bar's close (adverse slippage + fee) when
``close_open_positions_at_end`` is true, so realised and final equity agree. Benchmark: equal-weight buy-and-hold
of the same coins with the same costs, entered at each coin's first bar open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any, Optional

from ml.evaluation import backtest_metrics as bm
from ml.evaluation.constants import BACKTEST_ENGINE_VERSION, INTERVAL_SECONDS, STRATEGY_PHASE14, STRATEGY_VERSION
from ml.evaluation.series import PriceSeries
from ml.evaluation.timestamps import to_utc

SIZING_MODES = ("fixed_fraction", "fixed_amount")
MIN_NOTIONAL = 1e-6


@dataclass(frozen=True)
class Signal:
    time: datetime
    decision: str  # BUY / HOLD / SELL
    decision_id: Optional[str] = None


@dataclass(frozen=True)
class BacktestConfig:
    coin_ids: tuple[str, ...]
    start: datetime
    end: datetime
    starting_capital: float
    bar_interval: str = "1h"
    sizing_mode: str = "fixed_fraction"
    #: fraction of equity per entry (fixed_fraction) or currency amount (fixed_amount)
    position_size: float = 0.25
    #: hard cap on one asset's value as a fraction of equity at entry
    max_allocation_pct: float = 0.5
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    close_open_positions_at_end: bool = True
    risk_free_rate_annual: float = 0.0
    strategy: str = STRATEGY_PHASE14

    def validate(self) -> None:
        errs = []
        if not self.coin_ids or len(set(self.coin_ids)) != len(self.coin_ids):
            errs.append("coin_ids must be a non-empty list without duplicates")
        if self.start >= self.end:
            errs.append("start must be before end")
        if not (self.starting_capital > 0):
            errs.append("starting_capital must be > 0")
        if self.bar_interval not in INTERVAL_SECONDS:
            errs.append(f"bar_interval must be one of {sorted(INTERVAL_SECONDS)}")
        if self.sizing_mode not in SIZING_MODES:
            errs.append(f"sizing_mode must be one of {SIZING_MODES}")
        elif self.sizing_mode == "fixed_fraction" and not (0 < self.position_size <= 1):
            errs.append("position_size must be in (0, 1] for fixed_fraction")
        elif self.sizing_mode == "fixed_amount" and not (self.position_size > 0):
            errs.append("position_size must be > 0 for fixed_amount")
        if not (0 < self.max_allocation_pct <= 1):
            errs.append("max_allocation_pct must be in (0, 1]")
        if not (0 <= self.fee_rate < 0.1):
            errs.append("fee_rate must be in [0, 0.1)")
        if not (0 <= self.slippage_rate < 0.1):
            errs.append("slippage_rate must be in [0, 0.1)")
        if self.strategy != STRATEGY_PHASE14:
            errs.append(f"strategy must be {STRATEGY_PHASE14!r}")
        if errs:
            raise ValueError("; ".join(errs))

    def assumptions(self) -> dict[str, Any]:
        return {
            "engine_version": BACKTEST_ENGINE_VERSION, "strategy": self.strategy, "strategy_version": STRATEGY_VERSION,
            "bar_interval": self.bar_interval, "sizing_mode": self.sizing_mode, "position_size": self.position_size,
            "max_allocation_pct": self.max_allocation_pct, "fee_rate": self.fee_rate, "slippage_rate": self.slippage_rate,
            "execution": "next_bar_open", "long_only": True, "leverage": 1.0,
            "close_open_positions_at_end": self.close_open_positions_at_end,
            "risk_free_rate_annual": self.risk_free_rate_annual,
            "benchmark": "equal_weight_buy_and_hold", "benchmark_costs": "same fee and slippage",
        }


@dataclass
class BacktestResult:
    status: str  # ok | insufficient_data
    reason: Optional[str]
    summary: dict[str, Any]
    equity_curve: list[tuple[datetime, float]]
    benchmark_curve: list[tuple[datetime, float]]
    trades: list[dict[str, Any]]
    closed_trades: list[dict[str, Any]]
    assumptions: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class _Position:
    __slots__ = ("qty", "entry_cost", "entry_time", "entry_price", "entry_fee", "entry_slippage", "decision_id")

    def __init__(self, qty, entry_cost, entry_time, entry_price, entry_fee, entry_slippage, decision_id):
        self.qty, self.entry_cost, self.entry_time = qty, entry_cost, entry_time
        self.entry_price, self.entry_fee, self.entry_slippage, self.decision_id = entry_price, entry_fee, entry_slippage, decision_id


def run_backtest(config: BacktestConfig, series: dict[str, PriceSeries], signals: dict[str, list[Signal]]) -> BacktestResult:
    config.validate()
    start, end = to_utc(config.start), to_utc(config.end)
    assumptions = config.assumptions()
    coins = sorted(config.coin_ids)
    interval_s = INTERVAL_SECONDS[config.bar_interval]

    bars: dict[str, dict[datetime, Any]] = {}
    for c in coins:
        s = series.get(c)
        bars[c] = {k.open_time: k for k in (s.candles if s else []) if start <= k.open_time < end}
    timeline = sorted({t for b in bars.values() for t in b})
    if not timeline:
        return BacktestResult("insufficient_data", "No historical candles exist for the selected coins and period.",
                              {}, [], [], [], [], assumptions)

    sig = {c: sorted((s for s in signals.get(c, []) if s.time is not None and s.time >= start and s.time < end),
                     key=lambda x: x.time) for c in coins}
    ptr = {c: 0 for c in coins}
    acted: dict[str, Optional[Signal]] = {c: None for c in coins}
    cash = float(config.starting_capital)
    positions: dict[str, _Position] = {}
    last_close: dict[str, float] = {}
    trades: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    total_fees = total_slip = 0.0
    carried = 0
    equity: list[tuple[datetime, float]] = [(timeline[0], float(config.starting_capital))]
    bench = _Benchmark(config, coins)

    def mark(prices: dict[str, float]) -> float:
        return cash + sum(p.qty * prices.get(c, last_close.get(c, p.entry_price)) for c, p in positions.items())

    for T in timeline:
        opens = {c: bars[c][T].open for c in coins if T in bars[c]}
        # 1) execute decisions known at T at this bar's open
        for c in coins:
            if c not in opens:
                continue
            ss = sig[c]
            while ptr[c] < len(ss) and ss[ptr[c]].time <= T:
                ptr[c] += 1
            latest = ss[ptr[c] - 1] if ptr[c] > 0 else None
            if latest is None or latest is acted[c]:
                continue
            acted[c] = latest
            if latest.decision == "BUY":
                if c in positions:
                    skipped["buy_while_in_position"] = skipped.get("buy_while_in_position", 0) + 1
                    continue
                prices_now = {**last_close, **opens}
                eq = mark(prices_now)
                target = config.position_size * eq if config.sizing_mode == "fixed_fraction" else config.position_size
                notional = min(target, config.max_allocation_pct * eq, cash / (1.0 + config.fee_rate))
                if notional < MIN_NOTIONAL:
                    skipped["insufficient_cash"] = skipped.get("insufficient_cash", 0) + 1
                    continue
                px = opens[c] * (1.0 + config.slippage_rate)
                qty = notional / px
                fee = notional * config.fee_rate
                slip = (px - opens[c]) * qty
                cash -= notional + fee
                total_fees += fee
                total_slip += slip
                positions[c] = _Position(qty, notional + fee, T, px, fee, slip, latest.decision_id)
                trades.append(_trade(c, "BUY", latest, T, px, opens[c], qty, notional, fee, slip, cash))
            elif latest.decision == "SELL":
                pos = positions.get(c)
                if pos is None:
                    skipped["sell_while_flat"] = skipped.get("sell_while_flat", 0) + 1
                    continue
                cash, fee, slip = _close(c, pos, opens[c], T, latest, "decision", config, cash, positions, trades, closed)
                total_fees += fee
                total_slip += slip
        # 2) mark to market at the bar close (carry the last known close for coins without a bar)
        closes = {c: bars[c][T].close for c in coins if T in bars[c]}
        carried += sum(1 for c in positions if c not in closes)
        last_close.update(closes)
        bench.step(T, opens, closes)
        equity.append((T + timedelta(seconds=interval_s), mark(closes)))

    end_time = equity[-1][0]
    if config.close_open_positions_at_end:
        for c in sorted(list(positions)):
            pos = positions[c]
            px_ref = last_close.get(c, pos.entry_price)
            cash, fee, slip = _close(c, pos, px_ref, end_time, None, "end_of_backtest", config, cash, positions, trades, closed)
            total_fees += fee
            total_slip += slip
        equity[-1] = (end_time, cash)
    bench_curve, bench_final = bench.finish(timeline, end_time, interval_s)

    values = [v for _, v in equity]
    initial, final = float(config.starting_capital), values[-1]
    wins = [t["net_return"] for t in closed if t["net_pnl"] > 0]
    losses = [t["net_return"] for t in closed if t["net_pnl"] < 0]
    sharpe, sharpe_note = bm.sharpe_ratio(values, interval_s, config.risk_free_rate_annual)
    warnings: list[str] = []
    if not any(sig.values()):
        warnings.append("No stored decisions fall inside the selected period, so the strategy never traded.")
    if carried:
        warnings.append(f"{carried} position-bars used a carried-forward close because that coin had no candle in the bar.")
    summary = {
        "initial_value": initial, "final_value": final,
        "total_return": bm.total_return(initial, final),
        "annualized_return": bm.annualized_return(initial, final, equity[0][0], end_time),
        "max_drawdown": bm.max_drawdown(values),
        "number_of_trades": len(closed), "number_of_fills": len(trades),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "average_win_return": fmean(wins) if wins else None,
        "average_loss_return": fmean(losses) if losses else None,
        "total_fees": total_fees, "estimated_slippage": total_slip, "total_costs": total_fees + total_slip,
        "benchmark_initial_value": initial, "benchmark_final_value": bench_final,
        "benchmark_return": bm.total_return(initial, bench_final) if bench_final is not None else None,
        "sharpe_ratio": sharpe, "sharpe_note": sharpe_note,
        "skipped_signals": skipped, "period_start": equity[0][0], "period_end": end_time,
        "bars": len(timeline), "decisions_in_period": sum(len(v) for v in sig.values()),
    }
    return BacktestResult("ok", None, summary, equity, bench_curve, trades, closed, assumptions, warnings)


def _trade(coin, side, signal, T, px, ref_open, qty, notional, fee, slip, cash_after, reason="decision"):
    return {
        "coin_id": coin, "side": side, "reason": reason,
        "decision_id": signal.decision_id if signal else None,
        "decision_time": signal.time if signal else None, "execution_time": T,
        "price": px, "reference_price": ref_open, "quantity": qty, "notional": notional,
        "fee": fee, "slippage_cost": slip, "cash_after": cash_after,
    }


def _close(coin, pos, ref_px, T, signal, reason, config, cash, positions, trades, closed):
    px = ref_px * (1.0 - config.slippage_rate)
    proceeds = pos.qty * px
    fee = proceeds * config.fee_rate
    slip = (ref_px - px) * pos.qty
    cash += proceeds - fee
    del positions[coin]
    trades.append(_trade(coin, "SELL", signal, T, px, ref_px, pos.qty, proceeds, fee, slip, cash, reason))
    net_pnl = (proceeds - fee) - pos.entry_cost
    closed.append({
        "coin_id": coin, "entry_time": pos.entry_time, "exit_time": T, "entry_price": pos.entry_price, "exit_price": px,
        "quantity": pos.qty, "net_pnl": net_pnl, "net_return": net_pnl / pos.entry_cost,
        "fees": pos.entry_fee + fee, "slippage_cost": pos.entry_slippage + slip, "exit_reason": reason,
    })
    return cash, fee, slip


class _Benchmark:
    """Equal-weight buy-and-hold with the same costs; coins enter at their first bar open."""

    def __init__(self, config: BacktestConfig, coins: list[str]) -> None:
        self.cfg, self.coins = config, coins
        self.alloc = config.starting_capital / len(coins)
        self.cash = {c: self.alloc for c in coins}   # unallocated capital per coin slot
        self.qty: dict[str, float] = {}
        self.points: list[tuple[datetime, float]] = []
        self.last: dict[str, float] = {}

    def step(self, T, opens, closes):
        for c, o in opens.items():
            if c not in self.qty:
                notional = self.cash[c] / (1.0 + self.cfg.fee_rate)
                self.qty[c] = notional / (o * (1.0 + self.cfg.slippage_rate))
                self.cash[c] = 0.0
        self.last.update(closes)
        value = sum(self.cash.values()) + sum(q * self.last.get(c, 0.0) for c, q in self.qty.items())
        self.points.append((T, value))

    def finish(self, timeline, end_time, interval_s):
        if not self.points:
            return [], None
        curve = [(timeline[0], float(self.cfg.starting_capital))]
        for T, v in self.points:
            curve.append((T + timedelta(seconds=interval_s), v))
        if self.cfg.close_open_positions_at_end:
            liquid = sum(self.cash.values()) + sum(
                q * self.last.get(c, 0.0) * (1.0 - self.cfg.slippage_rate) * (1.0 - self.cfg.fee_rate) for c, q in self.qty.items())
            curve[-1] = (end_time, liquid)
        return curve, curve[-1][1]
