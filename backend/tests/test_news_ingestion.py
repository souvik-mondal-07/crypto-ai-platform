"""Ingestion: normalization -> association -> idempotent storage, with provider/DB failure handling."""

import pytest
from pymongo.errors import PyMongoError

from app.core.news_sync_state import NewsSyncState
from app.providers.errors import ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError
from app.services.news_coin_matcher import NewsCoinMatcher
from app.services.news_ingestion_service import NewsIngestionService
from tests.news_fixtures import BTC_ID, ETH_ID, FakeCoinRepository, FakeNewsRepository, FakeProvider, article, page_of


@pytest.fixture(autouse=True)
def _no_page_delay(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "NEWS_FETCH_PAGE_DELAY_SECONDS", 0.0)


def build(provider, repo=None, state=None):
    repo = repo or FakeNewsRepository()
    state = state or NewsSyncState()
    service = NewsIngestionService(
        providers=[provider], repository=repo, matcher=NewsCoinMatcher(FakeCoinRepository()), state=state
    )
    return service, repo, state


async def test_stores_articles_with_normalized_fields_and_coin_association():
    a1 = article(1, categories=["BTC", "ETH", "Exchange"])
    a2 = article(2, categories=["Mining"])
    service, repo, state = build(FakeProvider([page_of(a1, a2)]))
    result = await service.sync_latest(max_pages=1)

    assert (result.inserted, result.already_stored, result.associated_with_coins) == (2, 0, 1)
    doc = repo.docs["cryptocompare:1001"]
    assert doc["related_coin_ids"] == [BTC_ID, ETH_ID] and doc["related_symbols"] == ["BTC", "ETH"]
    assert doc["source_url"] == a1.url and doc["source"] == "Example Publisher"
    assert doc["sentiment"] is None and doc["sentiment_status"] == "pending"
    assert doc["fetched_at"] is not None and doc["published_at"] == a1.published_at
    assert repo.docs["cryptocompare:1002"]["related_coin_ids"] == []
    assert state.last_success_at is not None and state.last_error_code is None


async def test_running_twice_does_not_duplicate():
    page = lambda: page_of(article(1), article(2))  # noqa: E731
    service, repo, _ = build(FakeProvider([page(), page()]))
    first = await service.sync_latest(max_pages=1)
    second = await service.sync_latest(max_pages=1)
    assert first.inserted == 2 and second.inserted == 0 and second.already_stored == 2
    assert len(repo.docs) == 2


async def test_same_story_from_different_provider_ids_is_one_record():
    a = article(1, provider_article_id="1")
    b = article(1, provider_article_id="999", url=a.url + "?utm_source=rss")  # same story, new id + tracking
    service, repo, _ = build(FakeProvider([page_of(a), page_of(b)]))
    await service.sync_latest(max_pages=1)
    await service.sync_latest(max_pages=1)
    assert len(repo.docs) == 1


async def test_duplicates_within_one_page_are_collapsed():
    service, repo, _ = build(FakeProvider([page_of(article(1), article(1, provider_article_id="dup"))]))
    result = await service.sync_latest(max_pages=1)
    assert result.inserted == 1 and len(repo.docs) == 1


async def test_refetch_merges_new_coin_tags_without_dropping_old_ones():
    service, repo, _ = build(FakeProvider([page_of(article(1, categories=["BTC"])), page_of(article(1, categories=["ETH"]))]))
    await service.sync_latest(max_pages=1)
    await service.sync_latest(max_pages=1)
    assert set(repo.docs["cryptocompare:1001"]["related_coin_ids"]) == {BTC_ID, ETH_ID}


async def test_paging_continues_backwards_then_stops_when_caught_up():
    p1 = page_of(article(1, minutes_ago=10), article(2, minutes_ago=20))
    p2 = page_of(article(3, minutes_ago=30))
    p3 = page_of(article(1, minutes_ago=10))  # nothing new -> must stop
    provider = FakeProvider([p1, p2, p3, page_of(article(9))])
    service, repo, _ = build(provider)
    result = await service.sync_latest(max_pages=5)
    assert result.pages_fetched == 3 and len(provider.calls) == 3
    assert provider.calls[0] is None and provider.calls[1] == p1.oldest_published_at
    assert len(repo.docs) == 3


async def test_malformed_entries_are_counted():
    service, _, _ = build(FakeProvider([page_of(article(1), malformed=4)]))
    assert (await service.sync_latest(max_pages=1)).malformed_dropped == 4


@pytest.mark.parametrize(
    "error, code",
    [
        (ProviderRateLimitError("x"), "PROVIDER_RATE_LIMITED"),
        (ProviderTimeoutError("x"), "PROVIDER_TIMEOUT"),
        (ProviderUnavailableError("x"), "PROVIDER_UNAVAILABLE"),
    ],
)
async def test_provider_failure_is_recorded_not_raised(error, code):
    service, repo, state = build(FakeProvider([error]))
    result = await service.sync_latest(max_pages=2)
    assert result.errors and result.inserted == 0 and repo.docs == {}
    assert state.last_error_code == code and state.last_success_at is None


async def test_failure_on_a_later_page_keeps_earlier_articles():
    service, repo, state = build(FakeProvider([page_of(article(1)), ProviderRateLimitError("x")]))
    result = await service.sync_latest(max_pages=3)
    assert result.inserted == 1 and len(repo.docs) == 1
    assert state.last_success_at is not None and state.last_error_code == "PROVIDER_RATE_LIMITED"


async def test_database_failure_is_recorded():
    class BrokenRepo(FakeNewsRepository):
        async def upsert_articles(self, documents):
            raise PyMongoError("down")

    service, _, state = build(FakeProvider([page_of(article(1))]), repo=BrokenRepo())
    result = await service.sync_latest(max_pages=1)
    assert "database: DATABASE_UNAVAILABLE" in result.errors and state.last_error_code == "DATABASE_UNAVAILABLE"
