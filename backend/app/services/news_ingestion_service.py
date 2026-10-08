"""
News ingestion (Phase 12):

    NewsProvider(s) -> NormalizedNewsArticle -> dedupe keys + coin
    association -> NewsRepository (idempotent upsert) -> `news`

Failure policy: a provider failure never raises out of `sync_latest` —
it is recorded in the result and the sync state, and whatever was
already stored keeps being served. Malformed provider entries are
dropped and counted. Running a sync twice stores nothing twice.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo.errors import PyMongoError

from app.config import get_settings
from app.core.news_sync_state import NewsSyncState, get_news_sync_state
from app.providers.errors import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.news import NewsProvider, get_news_providers
from app.providers.news.models import NormalizedNewsArticle
from app.repositories.news_repository import NewsRepository
from app.services.news_coin_matcher import NewsCoinMatcher, extract_candidate_symbols
from app.services.news_dedupe import build_dedupe_key, build_news_id

logger = logging.getLogger("crypto_ai_platform.services.news_ingestion")


@dataclass
class NewsSyncResult:
    started_at: datetime
    finished_at: Optional[datetime] = None
    pages_fetched: int = 0
    articles_seen: int = 0
    inserted: int = 0
    already_stored: int = 0
    malformed_dropped: int = 0
    associated_with_coins: int = 0
    errors: list[str] = field(default_factory=list)


def error_code_for(exc: Exception) -> str:
    if isinstance(exc, ProviderRateLimitError):
        return "PROVIDER_RATE_LIMITED"
    if isinstance(exc, ProviderTimeoutError):
        return "PROVIDER_TIMEOUT"
    if isinstance(exc, ProviderUnavailableError):
        return "PROVIDER_UNAVAILABLE"
    return "PROVIDER_BAD_RESPONSE" if isinstance(exc, ProviderError) else "INTERNAL_ERROR"


class NewsIngestionService:
    def __init__(
        self,
        providers: Optional[list[NewsProvider]] = None,
        repository: Optional[NewsRepository] = None,
        matcher: Optional[NewsCoinMatcher] = None,
        state: Optional[NewsSyncState] = None,
    ) -> None:
        self._providers = providers if providers is not None else get_news_providers()
        self._repository = repository or NewsRepository()
        self._matcher = matcher or NewsCoinMatcher()
        self._state = state or get_news_sync_state()

    async def _build_documents(
        self, articles: list[NormalizedNewsArticle], fetched_at: datetime
    ) -> tuple[list[dict[str, Any]], int]:
        candidates = {a.url: extract_candidate_symbols(a) for a in articles}
        resolved = await self._matcher.resolve_symbols(s for syms in candidates.values() for s in syms)

        documents: dict[str, dict[str, Any]] = {}
        associated = 0
        for article in articles:
            dedupe_key = build_dedupe_key(article.url, article.source, article.title, article.published_at)
            if dedupe_key in documents:
                continue  # same story twice in one page
            coin_ids, symbols = self._matcher.associate(candidates[article.url], resolved)
            associated += 1 if coin_ids else 0
            documents[dedupe_key] = {
                "news_id": build_news_id(article, dedupe_key),
                "dedupe_key": dedupe_key,
                "provider": article.provider,
                "provider_article_id": article.provider_article_id,
                "title": article.title,
                "description": article.description,
                "source": article.source,
                "source_url": article.url,
                "image_url": article.image_url,
                "author": article.author,
                "published_at": article.published_at,
                "fetched_at": fetched_at,
                "language": article.language,
                "related_coin_ids": coin_ids,
                "related_symbols": symbols,
                "categories": article.categories,
                "tags": article.tags,
                "sentiment": None,
                "sentiment_status": "pending",
            }
        return list(documents.values()), associated

    async def sync_latest(self, max_pages: Optional[int] = None) -> NewsSyncResult:
        settings = get_settings()
        pages_budget = max_pages or settings.NEWS_FETCH_MAX_PAGES
        result = NewsSyncResult(started_at=datetime.now(timezone.utc))
        any_success = False
        first_error: Optional[str] = None

        for provider in self._providers:
            before: Optional[datetime] = None
            for page in range(pages_budget):
                if page > 0:
                    await asyncio.sleep(settings.NEWS_FETCH_PAGE_DELAY_SECONDS)
                try:
                    fetched = await provider.fetch_latest(before=before)
                except ProviderError as exc:
                    code = error_code_for(exc)
                    logger.warning("%s news fetch failed (page %d): %s", provider.provider_name, page + 1, code)
                    result.errors.append(f"{provider.provider_name}: {code}")
                    first_error = first_error or code
                    break

                any_success = True
                result.pages_fetched += 1
                result.malformed_dropped += fetched.malformed_count
                result.articles_seen += len(fetched.articles)
                if not fetched.articles:
                    break

                try:
                    documents, associated = await self._build_documents(fetched.articles, datetime.now(timezone.utc))
                    counts = await self._repository.upsert_articles(documents)
                except PyMongoError as exc:
                    logger.error("News persistence failed: %s", exc.__class__.__name__)
                    result.errors.append("database: DATABASE_UNAVAILABLE")
                    first_error = first_error or "DATABASE_UNAVAILABLE"
                    break

                result.inserted += counts.inserted
                result.already_stored += counts.existing
                result.associated_with_coins += associated
                if counts.failed:
                    result.errors.append(f"{counts.failed} article(s) failed to store")

                # A page with nothing new means we've caught up — don't spend more provider calls.
                if counts.inserted == 0 or fetched.oldest_published_at is None:
                    break
                before = fetched.oldest_published_at

        self._state.record(success=any_success, error_code=first_error)
        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            "News sync: pages=%d seen=%d inserted=%d existing=%d malformed=%d errors=%d",
            result.pages_fetched, result.articles_seen, result.inserted,
            result.already_stored, result.malformed_dropped, len(result.errors),
        )
        return result
