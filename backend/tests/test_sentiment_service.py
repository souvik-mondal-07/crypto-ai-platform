"""SentimentService end-to-end over fake repositories: real documents in, structured response out."""

from datetime import timedelta

import pytest

from app.core.exceptions import AppError
from app.services.sentiment_service import SentimentService
from tests.news_fixtures import BTC_ID, NOW, FakeCoinRepository


class FakeNewsRepo:
    def __init__(self, docs=(), pending=0):
        self.docs, self.pending, self.calls = list(docs), pending, []

    async def sentiment_points_for_coin(self, coin_id, since, until, limit=10_000):
        self.calls.append((coin_id, since, until))
        return self.docs

    async def count_pending_for_coin(self, coin_id, since):
        return self.pending


def doc(hours_ago, label, score):
    return {"published_at": NOW - timedelta(hours=hours_ago), "sentiment": {"label": label, "score": score}}


def svc(repo):
    return SentimentService(repo, FakeCoinRepository())


async def test_aggregates_stored_results():
    repo = FakeNewsRepo([doc(1, "positive", 0.8), doc(2, "positive", 0.7), doc(3, "negative", -0.5)], pending=4)
    r = await svc(repo).get_coin_sentiment(str(BTC_ID), "24h", now=NOW)
    assert (r.positive_count, r.neutral_count, r.negative_count, r.total_articles) == (2, 0, 1, 3)
    assert r.average_score == pytest.approx(0.3333, abs=1e-3) and r.status == "ok" and r.sentiment_label == "positive"
    assert r.pending_article_count == 4 and r.timeframe == "24h" and r.calculated_at == NOW
    assert r.min_articles_required == 3 and "not a price prediction" in r.disclaimer


async def test_reads_current_and_previous_window_for_the_coin():
    repo = FakeNewsRepo()
    await svc(repo).get_coin_sentiment(str(BTC_ID), "7d", now=NOW)
    coin, since, until = repo.calls[0]
    assert coin == BTC_ID and until == NOW and since == NOW - timedelta(days=14)


async def test_insufficient_data_is_explicit_not_fabricated():
    r = await svc(FakeNewsRepo([doc(1, "positive", 0.9)])).get_coin_sentiment(str(BTC_ID), "24h", now=NOW)
    assert r.status == "insufficient_data" and r.sentiment_label is None and r.total_articles == 1
    empty = await svc(FakeNewsRepo()).get_coin_sentiment(str(BTC_ID), "24h", now=NOW)
    assert empty.total_articles == 0 and empty.average_score is None and empty.positive_percent is None


async def test_documents_without_a_complete_sentiment_are_skipped():
    docs = [doc(1, "positive", 0.9), {"published_at": NOW, "sentiment": None}, {"published_at": NOW, "sentiment": {"label": "positive"}}]
    r = await svc(FakeNewsRepo(docs)).get_coin_sentiment(str(BTC_ID), "24h", now=NOW)
    assert r.total_articles == 1


async def test_errors():
    with pytest.raises(AppError) as exc:
        await svc(FakeNewsRepo()).get_coin_sentiment("nope", "24h")
    assert exc.value.code == "INVALID_COIN_ID" and exc.value.status_code == 400
    with pytest.raises(AppError) as exc2:
        await svc(FakeNewsRepo()).get_coin_sentiment("cccccccccccccccccccccccc", "24h")
    assert exc2.value.code == "COIN_NOT_FOUND"
    with pytest.raises(AppError) as exc3:
        await svc(FakeNewsRepo()).get_coin_sentiment(str(BTC_ID), "1y")
    assert exc3.value.code == "INVALID_TIMEFRAME"
