"""Equity-curve statistics for the backtest engine. Formulas (all on the FULL, un-downsampled curve):

total_return         final / initial - 1
annualized_return    (1 + total_return) ** (365.25 / days) - 1 — only when the period is at least
                     ``MIN_DAYS_FOR_ANNUALISATION`` days and the final value is positive, else None
max_drawdown         largest peak-to-trough fall as a POSITIVE fraction (0.12 == -12% from the prior peak);
                     the starting capital counts as the first peak; 0.0 for a curve that never falls
win_rate             winning closed round trips / closed round trips (None with no closed trades);
                     a trade wins when its NET profit after fees and slippage is > 0
avg_win_return       mean net return of winning trades; avg_loss_return likewise for losing trades (negative)
sharpe_ratio         mean(excess per-bar return) / sample std(per-bar return) * sqrt(bars per year), with the
                     configured annual risk-free rate (default 0). Reported only with at least
                     ``MIN_RETURN_OBSERVATIONS_FOR_SHARPE`` return observations and a non-zero std,
                     otherwise None with an explanatory note. Crypto trades 24/7, so 365.25 days/year.

All of these describe a SIMULATION on historical data under the stated assumptions; they are not a forecast.
"""

from __future__ import annotations

import math
from datetime import datetime
from statistics import fmean, stdev
from typing import Optional, Sequence

from ml.evaluation.constants import MIN_DAYS_FOR_ANNUALISATION, MIN_RETURN_OBSERVATIONS_FOR_SHARPE

SECONDS_PER_YEAR = 365.25 * 86400


def total_return(initial: float, final: float) -> Optional[float]:
    return (final / initial - 1.0) if initial > 0 else None


def annualized_return(initial: float, final: float, start: datetime, end: datetime) -> Optional[float]:
    days = (end - start).total_seconds() / 86400.0
    if initial <= 0 or final <= 0 or days < MIN_DAYS_FOR_ANNUALISATION:
        return None
    return (final / initial) ** (365.25 / days) - 1.0


def max_drawdown(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


def bar_returns(values: Sequence[float]) -> list[float]:
    return [values[i] / values[i - 1] - 1.0 for i in range(1, len(values)) if values[i - 1] > 0]


def sharpe_ratio(values: Sequence[float], interval_seconds: int, risk_free_annual: float = 0.0) -> tuple[Optional[float], Optional[str]]:
    rets = bar_returns(values)
    if len(rets) < MIN_RETURN_OBSERVATIONS_FOR_SHARPE:
        return None, f"Needs at least {MIN_RETURN_OBSERVATIONS_FOR_SHARPE} return observations (have {len(rets)})."
    per_year = SECONDS_PER_YEAR / interval_seconds
    rf_bar = (1.0 + risk_free_annual) ** (1.0 / per_year) - 1.0
    sd = stdev(rets)
    if not math.isfinite(sd) or sd < 1e-12:  # float noise on a constant-growth curve is not volatility
        return None, "Return volatility is zero, so the ratio is undefined."
    return (fmean(rets) - rf_bar) / sd * math.sqrt(per_year), None


def downsample(points: Sequence, max_points: int) -> list:
    """Evenly thin a curve for storage/display while always keeping the first and last point."""
    n = len(points)
    if max_points < 2 or n <= max_points:
        return list(points)
    step = (n - 1) / (max_points - 1)
    idx = sorted({round(i * step) for i in range(max_points)} | {0, n - 1})
    return [points[i] for i in idx]
