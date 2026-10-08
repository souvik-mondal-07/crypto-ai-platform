"""Coin sentiment service (Phase 12): loads real analyzed articles and aggregates them (see sentiment_aggregation.py)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import get_settings
from app.core.exceptions import AppError
from app.repositories.coin_repository import CoinRepository
from app.repositories.news_repository import NewsRepository
from app.schemas.sentiment import CoinSentimentResponse, SentimentBucket, SentimentTrend
from app.services.news_service import db_call, parse_coin_object_id
from app.services.sentiment_aggregation import TIMEFRAME_HOURS, ArticlePoint, aggregate
from app.services.sentiment_model import get_sentiment_model_service


class SentimentService:
    def __init__(
        self,
        repository: Optional[NewsRepository] = None,
        coin_repository: Optional[CoinRepository] = None,
    ) -> None:
        self._news = repository or NewsRepository()
        self._coins = coin_repository or CoinRepository()

    async def get_coin_sentiment(
        self, coin_id: str, timeframe: str = "24h", now: Optional[datetime] = None
    ) -> CoinSentimentResponse:
        if timeframe not in TIMEFRAME_HOURS:
            raise AppError(400, "INVALID_TIMEFRAME", "timeframe must be '24h' or '7d'.")
        coin_oid = parse_coin_object_id(coin_id)
        if await db_call(self._coins.find_by_internal_id(coin_id)) is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")

        settings = get_settings()
        now = now or datetime.now(timezone.utc)
        window = timedelta(hours=TIMEFRAME_HOURS[timeframe])

        # Two windows are read: the requested period and the one before it (for the trend).
        docs = await db_call(self._news.sentiment_points_for_coin(coin_oid, now - 2 * window, now))
        points = [
            ArticlePoint(d["published_at"], d["sentiment"]["label"], float(d["sentiment"]["score"]))
            for d in docs
            if isinstance(d.get("sentiment"), dict) and "label" in d["sentiment"] and "score" in d["sentiment"]
        ]
        pending = await db_call(self._news.count_pending_for_coin(coin_oid, now - window))

        agg = aggregate(
            points,
            timeframe=timeframe,
            now=now,
            min_articles=settings.SENTIMENT_MIN_ARTICLES,
            label_threshold=settings.SENTIMENT_LABEL_THRESHOLD,
            trend_threshold=settings.SENTIMENT_TREND_THRESHOLD,
        )
        return CoinSentimentResponse(
            coin_id=coin_id,
            timeframe=timeframe,  # type: ignore[arg-type]
            status=agg.status,
            positive_count=agg.positive_count,
            neutral_count=agg.neutral_count,
            negative_count=agg.negative_count,
            total_articles=agg.total_articles,
            positive_percent=agg.positive_percent,
            neutral_percent=agg.neutral_percent,
            negative_percent=agg.negative_percent,
            average_score=agg.average_score,
            sentiment_label=agg.sentiment_label,
            trend=SentimentTrend(
                direction=agg.trend.direction,
                previous_average_score=agg.trend.previous_average_score,
                change=agg.trend.change,
                previous_total_articles=agg.trend.previous_total_articles,
            ),
            series=[SentimentBucket(bucket_start=b.bucket_start, article_count=b.article_count, average_score=b.average_score) for b in agg.series],
            pending_article_count=pending,
            min_articles_required=settings.SENTIMENT_MIN_ARTICLES,
            model_status=get_sentiment_model_service().status,
            period_start=agg.period_start,
            period_end=agg.period_end,
            calculated_at=now,
        )
