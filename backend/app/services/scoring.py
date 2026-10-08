"""Tiny, dependency-free numeric helpers shared by the risk and decision engines (Phase 14).

Pure functions only — no I/O, no randomness, no clock.
"""

import math
from typing import Iterable, Mapping, Optional, Sequence

Curve = Sequence[tuple[float, float]]


def is_number(value: object) -> bool:
    """True for a finite int/float (bool is excluded, NaN/inf are not numbers here)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def piecewise(value: float, curve: Curve) -> float:
    """Linearly interpolate `value` along `curve` ((x, y) points sorted by x), clamped at both ends."""
    points = sorted(curve)
    if value <= points[0][0]:
        return float(points[0][1])
    if value >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return float(y1)
            return float(y0 + (y1 - y0) * (value - x0) / (x1 - x0))
    return float(points[-1][1])  # pragma: no cover - unreachable for sorted, finite input


def weighted_average(items: Iterable[tuple[float, float]]) -> Optional[float]:
    """Weighted mean of (value, weight) pairs; None when there is no positive total weight."""
    total_w = 0.0
    total = 0.0
    for value, weight in items:
        if weight > 0:
            total += value * weight
            total_w += weight
    return total / total_w if total_w > 0 else None


def sign(value: float, threshold: float = 0.0) -> int:
    """+1 / -1 when |value| exceeds `threshold`, otherwise 0."""
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


def level_for_score(score: float, bounds: Sequence[tuple[str, float]]) -> str:
    """Map a 0-100 score to a level using inclusive upper bounds (e.g. 20 -> VERY_LOW, 21 -> LOW)."""
    for name, upper in bounds:
        if score <= upper:
            return name
    return bounds[-1][0]


def level_for_rounded_score(score: float, bounds: Sequence[tuple[str, float]]) -> str:
    """Like `level_for_score`, but classifies the score as DISPLAYED (nearest integer).

    The documented bands are integer bands (0-20, 21-40, ...), so a score shown as
    "41" is MODERATE. Rounding first keeps the level consistent with the number on screen.
    """
    return level_for_score(float(round(score)), bounds)


def fmt_money(value: float) -> str:
    """Compact USD for factor text: 1.2B, 340M, 12.5K."""
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            return f"${value / threshold:.1f}{suffix}"
    return f"${value:,.0f}"


def get(mapping: Mapping[str, float], key: Optional[str]) -> Optional[float]:
    return mapping.get(key) if key is not None else None
