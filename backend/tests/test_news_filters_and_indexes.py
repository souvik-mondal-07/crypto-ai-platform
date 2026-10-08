"""Backend filtering is built in the database layer (never by downloading the dataset), and indexes exist."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.database.collections import CollectionName
from app.database.indexes import initialize_indexes
from app.repositories.news_repository import build_news_filter
from tests.news_fixtures import BTC_ID


def test_empty_filter():
    assert build_news_filter() == {}


def test_all_filters_combine():
    start, end = datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 30, tzinfo=timezone.utc)
    f = build_news_filter(coin_id=BTC_ID, source="CoinDesk", sentiment="negative", date_from=start, date_to=end, search="etf")
    assert f["related_coin_ids"] == BTC_ID and f["source"] == "CoinDesk" and f["sentiment.label"] == "negative"
    assert f["published_at"] == {"$gte": start, "$lte": end}
    assert f["$or"] == [
        {"title": {"$regex": "etf", "$options": "i"}},
        {"description": {"$regex": "etf", "$options": "i"}},
    ]


def test_search_text_is_regex_escaped():
    pattern = build_news_filter(search="a.b(c)+")["$or"][0]["title"]["$regex"]
    assert pattern == r"a\.b\(c\)\+"


def test_open_ended_date_range():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert build_news_filter(date_from=start)["published_at"] == {"$gte": start}


class _FakeDatabase:
    def __init__(self):
        self.collections: dict[str, AsyncMock] = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, AsyncMock())


async def test_news_indexes_are_created():
    db = _FakeDatabase()
    await initialize_indexes(db)
    news = db.collections[CollectionName.NEWS.value]
    created = {c.kwargs["name"]: c for c in news.create_index.await_args_list}

    assert created["uniq_news_newsid"].kwargs["unique"] and created["uniq_news_dedupekey"].kwargs["unique"]
    keys = {name: [k for k, _ in c.args[0]] if isinstance(c.args[0], list) else [c.args[0]] for name, c in created.items()}
    assert keys["idx_news_publishedat"] == ["published_at"]
    assert keys["idx_news_relatedcoinids_publishedat"] == ["related_coin_ids", "published_at"]
    assert keys["idx_news_source_publishedat"][0] == "source"
    assert keys["idx_news_provider"] == ["provider"]
    assert keys["idx_news_sentimentstatus_publishedat"][0] == "sentiment_status"
    news.drop_index.assert_awaited_with("idx_news_coins_publishedat")
