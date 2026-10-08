"""Pydantic response models for news endpoints (Phase 12)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SentimentLabel = Literal["positive", "neutral", "negative"]


class ArticleSentiment(BaseModel):
    label: SentimentLabel
    #: P(positive) - P(negative), in [-1, 1].
    score: float
    #: Probability of the predicted label.
    confidence: float
    probabilities: dict[str, float] = Field(default_factory=dict)
    model: str
    analyzed_at: datetime


class RelatedCoin(BaseModel):
    coin_id: str
    symbol: str
    name: Optional[str] = None
    logo_url: Optional[str] = None


class NewsArticle(BaseModel):
    news_id: str
    title: str
    description: Optional[str] = None
    source: str
    #: The original article at the publisher.
    source_url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: datetime
    fetched_at: datetime
    provider: str
    language: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related_coins: list[RelatedCoin] = Field(default_factory=list)
    #: Null until the article has been analyzed.
    sentiment: Optional[ArticleSentiment] = None


class NewsFeedStatus(BaseModel):
    """Honest state of the pipeline behind the feed, so the UI can explain an empty/stale feed."""

    last_sync_attempt_at: Optional[datetime] = None
    last_sync_success_at: Optional[datetime] = None
    #: Machine code of the last sync failure, null when the last sync succeeded (or none ran yet).
    last_sync_error_code: Optional[str] = None
    background_refresh_enabled: bool = True
    #: disabled | not_loaded | ready | unavailable
    sentiment_model_status: str = "not_loaded"


class NewsListResponse(BaseModel):
    items: list[NewsArticle]
    page: int
    limit: int
    total: int
    pages: int
    status: NewsFeedStatus


class NewsSourcesResponse(BaseModel):
    items: list[str]
