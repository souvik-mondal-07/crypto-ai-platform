"""NewsService: validation, pagination, related-coin shaping, error mapping (fake repositories)."""

from datetime import timedelta
from typing import Any

import pytest
from pymongo.errors import PyMongoError

from app.core.exceptions import AppError
from app.services.news_service import NewsService
from tests.news_fixtures import BTC_ID, ETH_ID, NOW, FakeCoinRepository


def stored(n: int, **kw: Any) -> dict[str, Any]:
    doc = {
        "news_id": f"cryptocompare:{n}", "title": f"Headline {n}", "description": None, "source": "Pub",
        "source_url": f"https://pub.test/{n}", "image_url": None, "author": None,
        "published_at": NOW - timedelta(minutes=n), "fetched_at": NOW, "provider": "cryptocompare",
        "language": "en", "categories": [], "tags": [], "related_coin_ids": [BTC_ID], "sentiment": None,
    }
    doc.update(kw)
    return doc


class FakeRepo:
    def __init__(self, docs=None, total=None, error=None):
        self.docs, self.total, self.error, self.last_filter, self.last_page = docs or [], total, error, None, None

    async def list_articles(self, filter_, page, limit):
        if self.error:
            raise self.error
        self.last_filter, self.last_page = filter_, (page, limit)
        return self.docs, self.total if self.total is not None else len(self.docs)

    async def get_by_news_id(self, news_id):
        return next((d for d in self.docs if d["news_id"] == news_id), None)

    async def list_sources(self):
        return ["A", "b"]


def service(repo):
    return NewsService(repo, FakeCoinRepository())


async def test_list_shapes_articles_and_related_coins():
    sentiment = {"label": "positive", "score": 0.8, "confidence": 0.9, "probabilities": {}, "model": "m", "analyzed_at": NOW}
    repo = FakeRepo([stored(1, related_coin_ids=[BTC_ID, ETH_ID], sentiment=sentiment), stored(2, related_coin_ids=[])])
    resp = await service(repo).list_news()
    first, second = resp.items
    assert [c.symbol for c in first.related_coins] == ["BTC", "ETH"] and first.related_coins[0].coin_id == str(BTC_ID)
    assert first.sentiment.label == "positive" and second.sentiment is None and second.related_coins == []
    assert first.source_url == "https://pub.test/1"


async def test_pagination_metadata_and_limit_clamp():
    repo = FakeRepo([stored(1)], total=95)
    resp = await service(repo).list_news(page=3, limit=20)
    assert (resp.page, resp.limit, resp.total, resp.pages) == (3, 20, 95, 5)
    assert repo.last_page == (3, 20)
    await service(repo).list_news(page=0, limit=9999)
    assert repo.last_page == (1, 50)


async def test_filters_are_passed_to_the_database_layer():
    repo = FakeRepo([])
    await service(repo).list_news(coin_id=str(BTC_ID), search=" etf ", source="Pub", sentiment="positive")
    f = repo.last_filter
    assert f["related_coin_ids"] == BTC_ID and f["source"] == "Pub" and f["sentiment.label"] == "positive"
    assert f["$or"][0]["title"]["$regex"] == "etf"


async def test_invalid_coin_id_is_400_and_unknown_coin_is_404():
    with pytest.raises(AppError) as bad:
        await service(FakeRepo()).list_news(coin_id="not-an-object-id")
    assert bad.value.status_code == 400 and bad.value.code == "INVALID_COIN_ID"
    with pytest.raises(AppError) as missing:
        await service(FakeRepo()).list_news(coin_id="cccccccccccccccccccccccc")
    assert missing.value.status_code == 404 and missing.value.code == "COIN_NOT_FOUND"


async def test_invalid_date_range_and_long_search():
    with pytest.raises(AppError) as exc:
        await service(FakeRepo()).list_news(date_from=NOW, date_to=NOW - timedelta(days=1))
    assert exc.value.code == "INVALID_DATE_RANGE"
    with pytest.raises(AppError) as exc2:
        await service(FakeRepo()).list_news(search="x" * 101)
    assert exc2.value.code == "INVALID_QUERY"


async def test_database_failure_is_a_clean_503():
    with pytest.raises(AppError) as exc:
        await service(FakeRepo(error=PyMongoError("boom"))).list_news()
    assert exc.value.status_code == 503 and exc.value.code == "DATABASE_UNAVAILABLE"


async def test_get_news_found_and_not_found():
    repo = FakeRepo([stored(7)])
    assert (await service(repo).get_news("cryptocompare:7")).title == "Headline 7"
    with pytest.raises(AppError) as exc:
        await service(repo).get_news("cryptocompare:404")
    assert exc.value.status_code == 404 and exc.value.code == "NEWS_NOT_FOUND"


async def test_empty_feed_is_a_valid_empty_response():
    resp = await service(FakeRepo([])).list_news()
    assert resp.items == [] and resp.total == 0 and resp.pages == 0
    assert resp.status.sentiment_model_status in {"disabled", "not_loaded", "ready", "unavailable"}
