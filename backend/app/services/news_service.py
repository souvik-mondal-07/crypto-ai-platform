"""
News query service (Phase 12) — validation, filtering and response shaping
for the global and per-coin feeds. Routes call this; provider logic is
never reached from here (the feed is served from MongoDB only).
"""

import logging
from datetime import datetime
from typing import Any, Awaitable, Optional, TypeVar

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.core.exceptions import AppError
from app.core.news_sync_state import get_news_sync_state
from app.repositories.coin_repository import CoinRepository
from app.repositories.news_repository import NewsRepository, build_news_filter
from app.schemas.news import (
    ArticleSentiment,
    NewsArticle,
    NewsFeedStatus,
    NewsListResponse,
    NewsSourcesResponse,
    RelatedCoin,
)
from app.services.sentiment_model import get_sentiment_model_service
from app.utils.pagination import total_pages

logger = logging.getLogger("crypto_ai_platform.services.news")

MAX_NEWS_LIMIT = 50
T = TypeVar("T")


async def db_call(awaitable: Awaitable[T]) -> T:
    """MongoDB failure -> clean 503 instead of a generic 500."""
    try:
        return await awaitable
    except PyMongoError as exc:
        logger.error("Database error in news/sentiment: %s", exc.__class__.__name__)
        raise AppError(
            503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable. Please try again shortly."
        ) from exc


def parse_coin_object_id(coin_id: str) -> ObjectId:
    if not ObjectId.is_valid(coin_id):
        raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
    return ObjectId(coin_id)


def feed_status() -> NewsFeedStatus:
    state = get_news_sync_state()
    return NewsFeedStatus(
        last_sync_attempt_at=state.last_attempt_at,
        last_sync_success_at=state.last_success_at,
        last_sync_error_code=state.last_error_code,
        background_refresh_enabled=state.enabled,
        sentiment_model_status=get_sentiment_model_service().status,
    )


def doc_to_article(doc: dict[str, Any], coins_by_id: dict[ObjectId, dict[str, Any]]) -> NewsArticle:
    related = []
    for coin_oid in doc.get("related_coin_ids") or []:
        coin = coins_by_id.get(coin_oid)
        if coin is not None:  # ids whose coin no longer exists are skipped, not invented
            related.append(
                RelatedCoin(
                    coin_id=str(coin_oid), symbol=coin["symbol"], name=coin.get("name"), logo_url=coin.get("logo_url")
                )
            )
    sentiment_doc = doc.get("sentiment")
    return NewsArticle(
        news_id=doc["news_id"],
        title=doc["title"],
        description=doc.get("description"),
        source=doc["source"],
        source_url=doc["source_url"],
        image_url=doc.get("image_url"),
        author=doc.get("author"),
        published_at=doc["published_at"],
        fetched_at=doc["fetched_at"],
        provider=doc["provider"],
        language=doc.get("language"),
        categories=doc.get("categories") or [],
        tags=doc.get("tags") or [],
        related_coins=related,
        sentiment=ArticleSentiment(**sentiment_doc) if sentiment_doc else None,
    )


class NewsService:
    def __init__(
        self,
        repository: Optional[NewsRepository] = None,
        coin_repository: Optional[CoinRepository] = None,
    ) -> None:
        self._news = repository or NewsRepository()
        self._coins = coin_repository or CoinRepository()

    async def _require_coin(self, coin_id: str) -> ObjectId:
        coin_oid = parse_coin_object_id(coin_id)
        if await db_call(self._coins.find_by_internal_id(coin_id)) is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        return coin_oid

    async def _to_articles(self, docs: list[dict[str, Any]]) -> list[NewsArticle]:
        coin_ids = list({cid for d in docs for cid in (d.get("related_coin_ids") or [])})
        coins_by_id = await db_call(self._coins.find_by_internal_ids(coin_ids)) if coin_ids else {}
        return [doc_to_article(d, coins_by_id) for d in docs]

    async def list_news(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        coin_id: Optional[str] = None,
        search: Optional[str] = None,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> NewsListResponse:
        page = max(1, page)
        limit = min(max(1, limit), MAX_NEWS_LIMIT)
        if date_from and date_to and date_from > date_to:
            raise AppError(400, "INVALID_DATE_RANGE", "date_from must not be after date_to.")
        search = (search or "").strip() or None
        if search and len(search) > 100:
            raise AppError(400, "INVALID_QUERY", "Search query is too long.")

        coin_oid = await self._require_coin(coin_id) if coin_id else None
        filter_ = build_news_filter(
            coin_id=coin_oid, search=search, source=(source or "").strip() or None,
            sentiment=sentiment, date_from=date_from, date_to=date_to,
        )
        docs, total = await db_call(self._news.list_articles(filter_, page, limit))
        return NewsListResponse(
            items=await self._to_articles(docs),
            page=page,
            limit=limit,
            total=total,
            pages=total_pages(total, limit),
            status=feed_status(),
        )

    async def get_news(self, news_id: str) -> NewsArticle:
        doc = await db_call(self._news.get_by_news_id(news_id))
        if doc is None:
            raise AppError(404, "NEWS_NOT_FOUND", f"No news article found with id '{news_id}'.")
        return (await self._to_articles([doc]))[0]

    async def list_sources(self) -> NewsSourcesResponse:
        return NewsSourcesResponse(items=await db_call(self._news.list_sources()))
