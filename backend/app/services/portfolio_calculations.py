"""Pure portfolio maths (Phase 16) — no I/O, no database, no market access.

    invested value  = quantity × average buy price
    current value   = quantity × current price
    unrealized P&L  = current value − invested value
    unrealized P&L% = P&L / invested value × 100      (None when invested value is 0 / invalid)

A holding without a usable market price has NO current value and NO P&L (None) — it is
never valued at a guessed or zero price. Totals therefore cover only the priced holdings'
current value / P&L, and the summary says so (`is_partial`).
"""

import math
from dataclasses import dataclass
from typing import Optional


def _finite(value: Optional[float]) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def usable_price(price: Optional[float]) -> Optional[float]:
    """A market price is usable only if it is a finite number > 0; otherwise None (= "no price")."""
    return float(price) if _finite(price) and price > 0 else None  # type: ignore[operator]


def invested_value(quantity: float, average_buy_price: float) -> float:
    return quantity * average_buy_price


def current_value(quantity: float, price: Optional[float]) -> Optional[float]:
    price = usable_price(price)
    return None if price is None else quantity * price


def unrealized_pnl(current: Optional[float], invested: float) -> Optional[float]:
    return None if current is None else current - invested


def pnl_percent(pnl: Optional[float], invested: float) -> Optional[float]:
    """P&L as a percentage of the invested value; None for a zero/invalid invested value or missing P&L."""
    if pnl is None or not _finite(invested) or invested <= 0:
        return None
    result = pnl / invested * 100.0
    return result if math.isfinite(result) else None


def weighted_average_price(old_quantity: float, old_average: float, added_quantity: float, added_price: float) -> float:
    """Average buy price after merging another purchase into an existing holding."""
    total_quantity = old_quantity + added_quantity
    if total_quantity <= 0:
        return 0.0
    return (old_quantity * old_average + added_quantity * added_price) / total_quantity


@dataclass(frozen=True)
class Valuation:
    invested: float
    current: Optional[float]
    pnl: Optional[float]
    pnl_pct: Optional[float]


def valuate(quantity: float, average_buy_price: float, price: Optional[float]) -> Valuation:
    invested = invested_value(quantity, average_buy_price)
    current = current_value(quantity, price)
    pnl = unrealized_pnl(current, invested)
    return Valuation(invested=invested, current=current, pnl=pnl, pnl_pct=pnl_percent(pnl, invested))


@dataclass(frozen=True)
class Totals:
    total_current_value: float
    total_invested: float
    priced_invested: float
    total_pnl: Optional[float]
    total_pnl_pct: Optional[float]
    holdings_count: int
    unpriced_count: int

    @property
    def is_partial(self) -> bool:
        return self.unpriced_count > 0


def summarize(valuations: list[Valuation]) -> Totals:
    total_invested = sum(v.invested for v in valuations)
    priced = [v for v in valuations if v.current is not None]
    total_current = sum(v.current for v in priced)  # type: ignore[misc]
    priced_invested = sum(v.invested for v in priced)
    total_pnl = (total_current - priced_invested) if priced else None
    return Totals(
        total_current_value=total_current,
        total_invested=total_invested,
        priced_invested=priced_invested,
        total_pnl=total_pnl,
        total_pnl_pct=pnl_percent(total_pnl, priced_invested),
        holdings_count=len(valuations),
        unpriced_count=len(valuations) - len(priced),
    )


def allocation_percent(current: Optional[float], total_current_value: float) -> Optional[float]:
    """This holding's share of the priced portfolio value; None when it has no value or the total is 0."""
    if current is None or total_current_value <= 0:
        return None
    return current / total_current_value * 100.0
