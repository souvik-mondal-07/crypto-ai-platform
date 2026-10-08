"""Aggregation is pure arithmetic over real article results; these tests pin the definitions."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.sentiment_aggregation import ArticlePoint, aggregate, label_for_score
from tests.news_fixtures import NOW


def pt(hours_ago: float, label: str, score: float) -> ArticlePoint:
    return ArticlePoint(NOW - timedelta(hours=hours_ago), label, score)


def agg(points, timeframe="24h", **kw):
    return aggregate(points, timeframe=timeframe, now=NOW, **kw)


def test_counts_percentages_and_average():
    r = agg([pt(1, "positive", 0.8), pt(2, "positive", 0.6), pt(3, "neutral", 0.0), pt(4, "negative", -0.6)])
    assert (r.positive_count, r.neutral_count, r.negative_count, r.total_articles) == (2, 1, 1, 4)
    assert (r.positive_percent, r.neutral_percent, r.negative_percent) == (50.0, 25.0, 25.0)
    assert r.average_score == pytest.approx(0.2) and r.status == "ok" and r.sentiment_label == "positive"


def test_counts_always_sum_to_total():
    r = agg([pt(i, ["positive", "neutral", "negative"][i % 3], 0.0) for i in range(1, 10)])
    assert r.positive_count + r.neutral_count + r.negative_count == r.total_articles == 9


@pytest.mark.parametrize(
    "average, expected", [(0.15, "positive"), (0.5, "positive"), (0.14, "neutral"), (0.0, "neutral"), (-0.14, "neutral"), (-0.15, "negative"), (-0.9, "negative")]
)
def test_label_thresholds(average, expected):
    assert label_for_score(average, 0.15) == expected


def test_insufficient_data_withholds_label_and_trend_but_reports_counts():
    r = agg([pt(1, "positive", 0.9), pt(2, "positive", 0.9)], min_articles=3)
    assert r.status == "insufficient_data" and r.sentiment_label is None
    assert r.total_articles == 2 and r.positive_count == 2
    assert r.trend.direction == "insufficient_data"


def test_no_articles_at_all():
    r = agg([])
    assert r.status == "insufficient_data" and r.total_articles == 0
    assert r.average_score is None and r.positive_percent is None and r.sentiment_label is None


def test_articles_outside_the_window_are_ignored():
    r = agg([pt(1, "positive", 0.5), pt(30, "negative", -0.9), ArticlePoint(NOW + timedelta(hours=1), "negative", -1.0)])
    assert r.total_articles == 1 and r.negative_count == 0


def test_seven_day_window_includes_older_articles():
    pts = [pt(30, "positive", 0.5), pt(100, "positive", 0.5), pt(200, "negative", -0.5)]
    assert agg(pts, "24h").total_articles == 0
    assert agg(pts, "7d").total_articles == 2


def test_trend_improving_declining_stable():
    now_pts = [pt(h, "positive", 0.6) for h in (1, 2, 3)]
    prev_bad = [pt(h, "negative", -0.4) for h in (25, 26, 27)]
    r = agg(now_pts + prev_bad)
    assert r.trend.direction == "improving" and r.trend.change == pytest.approx(1.0) and r.trend.previous_total_articles == 3
    prev_good = [pt(h, "positive", 0.9) for h in (25, 26, 27)]
    assert agg(now_pts + prev_good).trend.direction == "declining"
    prev_same = [pt(h, "positive", 0.55) for h in (25, 26, 27)]
    assert agg(now_pts + prev_same).trend.direction == "stable"


def test_trend_needs_enough_articles_in_both_windows():
    now_pts = [pt(h, "positive", 0.6) for h in (1, 2, 3)]
    assert agg(now_pts + [pt(25, "negative", -0.5)]).trend.direction == "insufficient_data"


def test_series_buckets():
    r = agg([pt(1, "positive", 0.4), pt(1.5, "positive", 0.6), pt(23, "negative", -0.2)])
    assert len(r.series) == 6  # 24h in 4h buckets
    assert sum(b.article_count for b in r.series) == 3
    assert r.series[-1].article_count == 2 and r.series[-1].average_score == pytest.approx(0.5)
    assert r.series[0].article_count == 1 and r.series[1].average_score is None
    seven = agg([pt(5, "positive", 0.1)], "7d")
    assert len(seven.series) == 7 and seven.series[-1].article_count == 1


def test_naive_datetimes_from_the_database_are_treated_as_utc():
    naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
    r = agg([ArticlePoint(naive, "positive", 0.5)] * 3)
    assert r.total_articles == 3
    assert r.period_end == NOW and r.period_start == NOW - timedelta(hours=24)
