"""Shared builders for Phase 12 tests. Raw payloads follow the CryptoCompare news response shape;
all text here is synthetic TEST INPUT for unit tests, never shown in the app."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId

from app.providers.news.models import NewsFetchResult, NormalizedNewsArticle

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def raw_article(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "9001",
        "guid": "https://example-publisher.test/story-1",
        "published_on": int(NOW.timestamp()) - 600,
        "imageurl": "https://img.example-publisher.test/1.jpg",
        "title": "Test headline one",
        "url": "https://example-publisher.test/story-1?utm_source=feed",
        "body": "<p>First paragraph &amp; more text.</p>",
        "tags": "Market|Trading",
        "categories": "BTC|Exchange",
        "lang": "EN",
        "source": "examplepub",
        "source_info": {"name": "Example Publisher", "lang": "EN", "img": ""},
    }
    base.update(overrides)
    return base


def article(n: int = 1, *, minutes_ago: int = 10, categories: Optional[list[str]] = None, **kw: Any) -> NormalizedNewsArticle:
    return NormalizedNewsArticle(
        provider=kw.pop("provider", "cryptocompare"),
        provider_article_id=kw.pop("provider_article_id", str(1000 + n)),
        title=kw.pop("title", f"Test headline {n}"),
        url=kw.pop("url", f"https://example-publisher.test/story-{n}"),
        source=kw.pop("source", "Example Publisher"),
        published_at=NOW - timedelta(minutes=minutes_ago),
        description=kw.pop("description", f"Summary {n}"),
        categories=categories if categories is not None else ["BTC"],
        **kw,
    )


class FakeProvider:
    provider_name = "cryptocompare"

    def __init__(self, pages: list[Any]) -> None:
        self.pages = list(pages)
        self.calls: list[Optional[datetime]] = []

    async def fetch_latest(self, *, before=None, language=None):
        self.calls.append(before)
        if not self.pages:
            return NewsFetchResult(articles=[])
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page


def page_of(*articles: NormalizedNewsArticle, malformed: int = 0) -> NewsFetchResult:
    return NewsFetchResult(
        articles=list(articles),
        malformed_count=malformed,
        oldest_published_at=min((a.published_at for a in articles), default=None),
    )


BTC_ID = ObjectId("aaaaaaaaaaaaaaaaaaaaaaaa")
ETH_ID = ObjectId("bbbbbbbbbbbbbbbbbbbbbbbb")


class FakeCoinRepository:
    def __init__(self) -> None:
        self.coins = {
            BTC_ID: {"_id": BTC_ID, "symbol": "BTC", "name": "Bitcoin", "logo_url": "https://l/btc.png", "market_cap_rank": 1},
            ETH_ID: {"_id": ETH_ID, "symbol": "ETH", "name": "Ethereum", "logo_url": None, "market_cap_rank": 2},
        }

    async def find_best_by_symbols(self, symbols):
        return {c["symbol"]: c for c in self.coins.values() if c["symbol"] in symbols}

    async def find_by_internal_id(self, internal_id):
        return self.coins.get(ObjectId(internal_id))

    async def find_by_internal_ids(self, ids):
        return {i: self.coins[i] for i in ids if i in self.coins}


class FakeNewsRepository:
    """In-memory stand-in with the same idempotent-upsert semantics as NewsRepository."""

    def __init__(self) -> None:
        from app.repositories.news_repository import UpsertCounts

        self._counts_cls = UpsertCounts
        self.docs: dict[str, dict[str, Any]] = {}

    async def upsert_articles(self, documents):
        counts = self._counts_cls()
        for doc in documents:
            existing = next(
                (d for d in self.docs.values() if d["news_id"] == doc["news_id"] or d["dedupe_key"] == doc["dedupe_key"]), None
            )
            if existing:
                counts.existing += 1
                for key in ("related_coin_ids", "related_symbols", "categories", "tags"):
                    existing[key] = list(dict.fromkeys([*existing.get(key, []), *doc.get(key, [])]))
            else:
                self.docs[doc["news_id"]] = dict(doc)
                counts.inserted += 1
        return counts
