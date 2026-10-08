"""Pydantic response models for coin sentiment (Phase 12)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SentimentTimeframe = Literal["24h", "7d"]

DISCLAIMER = (
    "Descriptive summary of the tone of recent news coverage, produced by an NLP model. "
    "It is not a price prediction, trading signal or investment advice."
)


class SentimentTrend(BaseModel):
    #: improving/declining/stable compare the tone of coverage with the previous equal-length period.
    direction: Literal["improving", "declining", "stable", "insufficient_data"]
    previous_average_score: Optional[float] = None
    change: Optional[float] = None
    previous_total_articles: int = 0


class SentimentBucket(BaseModel):
    bucket_start: datetime
    article_count: int
    average_score: Optional[float] = None


class CoinSentimentResponse(BaseModel):
    # `model_status` is a legitimate field name here, not a pydantic-model namespace clash.
    model_config = ConfigDict(protected_namespaces=())

    coin_id: str
    timeframe: SentimentTimeframe
    #: ok | insufficient_data (too few analyzed articles to describe a tone — nothing is estimated).
    status: Literal["ok", "insufficient_data"]
    positive_count: int
    neutral_count: int
    negative_count: int
    #: Analyzed articles in the period.
    total_articles: int
    positive_percent: Optional[float] = None
    neutral_percent: Optional[float] = None
    negative_percent: Optional[float] = None
    average_score: Optional[float] = None
    #: Null while status is insufficient_data.
    sentiment_label: Optional[Literal["positive", "neutral", "negative"]] = None
    trend: SentimentTrend
    series: list[SentimentBucket] = Field(default_factory=list)
    #: Related articles in the period still waiting for analysis.
    pending_article_count: int = 0
    min_articles_required: int
    #: disabled | not_loaded | ready | unavailable
    model_status: str
    period_start: datetime
    period_end: datetime
    calculated_at: datetime
    disclaimer: str = DISCLAIMER
