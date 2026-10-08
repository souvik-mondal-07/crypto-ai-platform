"""
Sentiment aggregation (Phase 12) — pure functions, no I/O.

Turns per-article results into the descriptive metrics shown for a coin.

Definitions (also shown to users):
  * article score  = P(positive) - P(negative), in [-1, 1]
  * average score  = plain mean of article scores in the window
  * overall label  = positive if average >= +threshold, negative if
                     <= -threshold, otherwise neutral (default 0.15)
  * insufficient   = fewer than `min_articles` analyzed articles; the label
                     and trend are then withheld instead of guessed
  * trend          = this window's average vs the immediately preceding
                     window of equal length (change >= +/-0.10 is
                     "improving"/"declining", otherwise "stable"). It
                     describes how the TONE OF COVERAGE changed. It is not
                     a forecast and says nothing about price.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal, Optional

TIMEFRAME_HOURS = {"24h": 24, "7d": 168}
BUCKET_HOURS = {"24h": 4, "7d": 24}


@dataclass(frozen=True)
class ArticlePoint:
    published_at: datetime
    label: str
    score: float


@dataclass
class TrendResult:
    direction: Literal["improving", "declining", "stable", "insufficient_data"]
    previous_average_score: Optional[float] = None
    change: Optional[float] = None
    previous_total_articles: int = 0


@dataclass
class BucketResult:
    bucket_start: datetime
    article_count: int
    average_score: Optional[float]


@dataclass
class AggregationResult:
    status: Literal["ok", "insufficient_data"]
    positive_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    total_articles: int = 0
    positive_percent: Optional[float] = None
    neutral_percent: Optional[float] = None
    negative_percent: Optional[float] = None
    average_score: Optional[float] = None
    sentiment_label: Optional[Literal["positive", "neutral", "negative"]] = None
    trend: TrendResult = field(default_factory=lambda: TrendResult("insufficient_data"))
    series: list[BucketResult] = field(default_factory=list)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _mean(points: Iterable[ArticlePoint]) -> Optional[float]:
    scores = [p.score for p in points]
    return round(sum(scores) / len(scores), 4) if scores else None


def label_for_score(average: float, threshold: float) -> Literal["positive", "neutral", "negative"]:
    if average >= threshold:
        return "positive"
    if average <= -threshold:
        return "negative"
    return "neutral"


def aggregate(
    points: list[ArticlePoint],
    *,
    timeframe: str,
    now: datetime,
    min_articles: int = 3,
    label_threshold: float = 0.15,
    trend_threshold: float = 0.10,
) -> AggregationResult:
    """`points` may include articles from the previous window; they are split here."""
    hours = TIMEFRAME_HOURS[timeframe]
    bucket_hours = BUCKET_HOURS[timeframe]
    now = as_utc(now)
    start = now - timedelta(hours=hours)
    previous_start = start - timedelta(hours=hours)

    current = [p for p in points if start <= as_utc(p.published_at) <= now]
    previous = [p for p in points if previous_start <= as_utc(p.published_at) < start]

    total = len(current)
    counts = {label: sum(1 for p in current if p.label == label) for label in ("positive", "neutral", "negative")}
    average = _mean(current)
    enough = total >= min_articles

    series = []
    for i in range(hours // bucket_hours):
        b_start = start + timedelta(hours=i * bucket_hours)
        b_end = b_start + timedelta(hours=bucket_hours)
        last = i == hours // bucket_hours - 1
        in_bucket = [
            p for p in current
            if b_start <= as_utc(p.published_at) and (as_utc(p.published_at) <= b_end if last else as_utc(p.published_at) < b_end)
        ]
        series.append(BucketResult(b_start, len(in_bucket), _mean(in_bucket)))

    previous_average = _mean(previous)
    if enough and len(previous) >= min_articles and average is not None and previous_average is not None:
        change = round(average - previous_average, 4)
        direction = "improving" if change >= trend_threshold else "declining" if change <= -trend_threshold else "stable"
        trend = TrendResult(direction, previous_average, change, len(previous))
    else:
        trend = TrendResult("insufficient_data", previous_average, None, len(previous))

    return AggregationResult(
        status="ok" if enough else "insufficient_data",
        positive_count=counts["positive"],
        neutral_count=counts["neutral"],
        negative_count=counts["negative"],
        total_articles=total,
        positive_percent=round(100 * counts["positive"] / total, 1) if total else None,
        neutral_percent=round(100 * counts["neutral"] / total, 1) if total else None,
        negative_percent=round(100 * counts["negative"] / total, 1) if total else None,
        average_score=average,
        sentiment_label=label_for_score(average, label_threshold) if enough and average is not None else None,
        trend=trend,
        series=series,
        period_start=start,
        period_end=now,
    )
