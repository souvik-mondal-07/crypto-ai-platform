"""
Technical indicator calculations (Phase 10).

Pure functions only — no I/O, no provider/repository access, no
FastAPI imports. `TechnicalAnalysisService` is the only caller; this
module just implements the documented math so the indicator logic is
independently unit-testable and has no hidden dependency on live data.

Deliberately implemented in plain Python rather than pulled in from a
third-party TA library: the formulas below are the standard,
well-documented ones (Wilder's RSI/ATR smoothing, the usual EMA/MACD/
Bollinger definitions), so there is no accuracy trade-off, and it
keeps this service free of a heavy numeric-library dependency for a
handful of straightforward rolling calculations.

Every function takes real historical values already fetched by the
caller (see `TechnicalAnalysisService`) — nothing here ever invents
data. A function returns `None` (or an empty list) rather than a
guessed value when there isn't enough history for a given period.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class Candle:
    """Minimal OHLC candle shape indicators need. Volume is optional
    since not every provider/timeframe combination supplies it."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------


def sma(values: list[float], period: int) -> list[Optional[float]]:
    """
    Simple moving average. Returns one value per input point, `None`
    for the first `period - 1` points where there isn't enough
    history yet — never a fabricated/partial average.
    """
    if period <= 0 or len(values) < period:
        return [None] * len(values)
    out: list[Optional[float]] = [None] * (period - 1)
    window_sum = sum(values[:period])
    out.append(window_sum / period)
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out.append(window_sum / period)
    return out


def ema(values: list[float], period: int) -> list[Optional[float]]:
    """
    Exponential moving average, seeded with a simple moving average
    over the first `period` points (the standard approach), then
    smoothed with factor alpha = 2 / (period + 1).
    """
    if period <= 0 or len(values) < period:
        return [None] * len(values)
    alpha = 2 / (period + 1)
    out: list[Optional[float]] = [None] * (period - 1)
    prev = sum(values[:period]) / period
    out.append(prev)
    for i in range(period, len(values)):
        prev = values[i] * alpha + prev * (1 - alpha)
        out.append(prev)
    return out


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


class RsiZone(str, Enum):
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    NEUTRAL = "neutral"


def rsi(values: list[float], period: int = 14) -> list[Optional[float]]:
    """
    Relative Strength Index using Wilder's smoothing method (the
    standard RSI definition — a plain rolling average of gains/losses
    is a common but non-standard simplification).
    """
    if period <= 0 or len(values) < period + 1:
        return [None] * len(values)

    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    out: list[Optional[float]] = [None] * period  # aligns with `values` (one shorter delta series)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out.append(_rsi_from_averages(avg_gain, avg_loss))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(_rsi_from_averages(avg_gain, avg_loss))

    return out


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def rsi_zone(value: Optional[float], overbought: float = 70.0, oversold: float = 30.0) -> Optional[RsiZone]:
    if value is None:
        return None
    if value >= overbought:
        return RsiZone.OVERBOUGHT
    if value <= oversold:
        return RsiZone.OVERSOLD
    return RsiZone.NEUTRAL


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MacdPoint:
    macd: Optional[float]
    signal: Optional[float]
    histogram: Optional[float]


def macd(
    values: list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
) -> list[MacdPoint]:
    """
    MACD line (fast EMA - slow EMA), its signal line (EMA of the MACD
    line), and the histogram (MACD - signal).
    """
    fast_ema = ema(values, fast_period)
    slow_ema = ema(values, slow_period)

    macd_line: list[Optional[float]] = [
        (f - s) if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)
    ]

    # EMA of just the defined portion of the MACD line, re-aligned
    # back onto the full-length series.
    defined = [v for v in macd_line if v is not None]
    first_defined_index = next((i for i, v in enumerate(macd_line) if v is not None), None)

    signal_line: list[Optional[float]] = [None] * len(macd_line)
    if first_defined_index is not None and len(defined) >= signal_period:
        signal_of_defined = ema(defined, signal_period)
        for offset, value in enumerate(signal_of_defined):
            signal_line[first_defined_index + offset] = value

    points = []
    for m, s in zip(macd_line, signal_line):
        hist = (m - s) if m is not None and s is not None else None
        points.append(MacdPoint(macd=m, signal=s, histogram=hist))
    return points


class MacdCrossover(str, Enum):
    BULLISH = "bullish_crossover"
    BEARISH = "bearish_crossover"
    NONE = "none"


def macd_crossover(points: list[MacdPoint]) -> MacdCrossover:
    """
    Detects a crossover on the most recent completed bar: the
    histogram flipping sign between the last two points. A documented,
    simple technical-state rule — not a trading signal.
    """
    defined = [p for p in points if p.histogram is not None]
    if len(defined) < 2:
        return MacdCrossover.NONE
    prev, curr = defined[-2], defined[-1]
    if prev.histogram <= 0 < curr.histogram:
        return MacdCrossover.BULLISH
    if prev.histogram >= 0 > curr.histogram:
        return MacdCrossover.BEARISH
    return MacdCrossover.NONE


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BollingerPoint:
    upper: Optional[float]
    middle: Optional[float]
    lower: Optional[float]


def bollinger_bands(values: list[float], period: int = 20, num_std_dev: float = 2.0) -> list[BollingerPoint]:
    middle = sma(values, period)
    out: list[BollingerPoint] = []
    for i, mid in enumerate(middle):
        if mid is None:
            out.append(BollingerPoint(None, None, None))
            continue
        window = values[i - period + 1 : i + 1]
        variance = sum((v - mid) ** 2 for v in window) / period
        std_dev = variance**0.5
        out.append(BollingerPoint(upper=mid + num_std_dev * std_dev, middle=mid, lower=mid - num_std_dev * std_dev))
    return out


# ---------------------------------------------------------------------------
# ATR (Average True Range)
# ---------------------------------------------------------------------------


def atr(candles: list[Candle], period: int = 14) -> list[Optional[float]]:
    """
    Average True Range using Wilder's smoothing, same method as RSI.
    True range for bar i is max(high-low, |high-prev_close|,
    |low-prev_close|); the first bar has no previous close, so it
    falls back to high-low only.
    """
    if period <= 0 or len(candles) < period:
        return [None] * len(candles)

    true_ranges: list[float] = []
    for i, candle in enumerate(candles):
        if i == 0:
            true_ranges.append(candle.high - candle.low)
            continue
        prev_close = candles[i - 1].close
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )

    out: list[Optional[float]] = [None] * (period - 1)
    avg = sum(true_ranges[:period]) / period
    out.append(avg)
    for i in range(period, len(true_ranges)):
        avg = (avg * (period - 1) + true_ranges[i]) / period
        out.append(avg)
    return out


# ---------------------------------------------------------------------------
# Support / resistance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupportResistanceLevels:
    support: list[float]
    resistance: list[float]


def support_resistance(candles: list[Candle], window: int = 5, max_levels: int = 3) -> SupportResistanceLevels:
    """
    Fractal swing-point method: a candle's low is a support pivot if
    it's the lowest low within `window` bars on each side; a high is a
    resistance pivot symmetrically. This is one reasonable, documented
    heuristic — not a guarantee that price will react at these levels
    (support/resistance is inherently probabilistic, not exact).

    Returns at most `max_levels` of each, the ones closest to the most
    recent close (most actionable), sorted ascending.
    """
    n = len(candles)
    if n < window * 2 + 1:
        return SupportResistanceLevels(support=[], resistance=[])

    supports: list[float] = []
    resistances: list[float] = []
    for i in range(window, n - window):
        neighborhood = candles[i - window : i + window + 1]
        if candles[i].low == min(c.low for c in neighborhood):
            supports.append(candles[i].low)
        if candles[i].high == max(c.high for c in neighborhood):
            resistances.append(candles[i].high)

    last_close = candles[-1].close
    supports_below = sorted({s for s in supports if s <= last_close}, reverse=True)[:max_levels]
    resistances_above = sorted({r for r in resistances if r >= last_close})[:max_levels]

    return SupportResistanceLevels(
        support=sorted(supports_below),
        resistance=sorted(resistances_above),
    )


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------


class Trend(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def classify_trend(
    *,
    last_close: Optional[float],
    sma_50: Optional[float],
    sma_200: Optional[float],
    macd_state: MacdCrossover,
    rsi_value: Optional[float],
) -> Trend:
    """
    Documented rule-based technical trend classification — intended
    purely as a descriptive label for the current technical picture,
    never a BUY/HOLD/SELL decision (that's Phase 14's job and is out
    of scope here).

    Scoring (each signal contributes at most one point either way):
      +1 bullish / -1 bearish: price above/below SMA50
      +1 bullish / -1 bearish: SMA50 above/below SMA200 (golden/death cross bias)
      +1 bullish / -1 bearish: MACD bullish/bearish crossover
      +1 bullish / -1 bearish: RSI above/below 50

    Net score > 0 -> bullish, < 0 -> bearish, 0 (or insufficient data
    for every signal) -> neutral.
    """
    score = 0
    signals_available = 0

    if last_close is not None and sma_50 is not None:
        score += 1 if last_close > sma_50 else -1
        signals_available += 1

    if sma_50 is not None and sma_200 is not None:
        score += 1 if sma_50 > sma_200 else -1
        signals_available += 1

    if macd_state != MacdCrossover.NONE:
        score += 1 if macd_state == MacdCrossover.BULLISH else -1
        signals_available += 1

    if rsi_value is not None:
        score += 1 if rsi_value > 50 else -1
        signals_available += 1

    if signals_available == 0 or score == 0:
        return Trend.NEUTRAL
    return Trend.BULLISH if score > 0 else Trend.BEARISH
