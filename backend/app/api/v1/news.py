"""News endpoints (Phase 12). Logic lives in NewsService; this layer only validates query parameters."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Query

from app.schemas.news import NewsArticle, NewsListResponse, NewsSourcesResponse
from app.services.news_service import MAX_NEWS_LIMIT, NewsService

router = APIRouter(prefix="/news", tags=["News"])


def _service() -> NewsService:
    return NewsService()


@router.get("", response_model=NewsListResponse)
async def list_news(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=MAX_NEWS_LIMIT),
    coin_id: Optional[str] = Query(None, description="Internal coin id — only articles related to this coin"),
    search: Optional[str] = Query(None, max_length=100, description="Case-insensitive match on title/summary"),
    source: Optional[str] = Query(None, max_length=100, description="Exact publisher name (see /news/sources)"),
    sentiment: Optional[Literal["positive", "neutral", "negative"]] = Query(None),
    date_from: Optional[datetime] = Query(None, description="Published at/after (ISO 8601)"),
    date_to: Optional[datetime] = Query(None, description="Published at/before (ISO 8601)"),
) -> NewsListResponse:
    """Global crypto news feed, newest first, filtered and paginated in the database."""
    return await _service().list_news(
        page=page, limit=limit, coin_id=coin_id, search=search, source=source,
        sentiment=sentiment, date_from=date_from, date_to=date_to,
    )


# Static path first so "sources" is never captured by the {news_id} route.
@router.get("/sources", response_model=NewsSourcesResponse)
async def list_news_sources() -> NewsSourcesResponse:
    """Distinct publisher names currently stored — the values accepted by `source`."""
    return await _service().list_sources()


@router.get("/{news_id}", response_model=NewsArticle)
async def get_news(news_id: str) -> NewsArticle:
    return await _service().get_news(news_id)
