"""
Background news refresh (Phase 12) — the same lightweight asyncio-loop
pattern as the market refresh scheduler (no Redis/Celery). One cycle =
ingest the latest articles, then analyze sentiment for any pending ones.
`run_cycle_once` is separate from the loop so a future job runner (or a
test / dev endpoint) can call it directly.
"""

import asyncio
import logging
from typing import Optional

from app.config import get_settings
from app.core.news_sync_state import get_news_sync_state
from app.services.news_ingestion_service import NewsIngestionService
from app.services.sentiment_analysis_service import SentimentAnalysisService

logger = logging.getLogger("crypto_ai_platform.services.news_refresh_scheduler")


class NewsRefreshScheduler:
    def __init__(
        self,
        ingestion: Optional[NewsIngestionService] = None,
        sentiment: Optional[SentimentAnalysisService] = None,
    ) -> None:
        self._settings = get_settings()
        self._ingestion = ingestion
        self._sentiment = sentiment
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        get_news_sync_state().enabled = self._settings.NEWS_REFRESH_ENABLED

    @property
    def is_started(self) -> bool:
        return self._task is not None

    def start(self) -> None:
        if self._task is not None:
            return
        if not self._settings.NEWS_REFRESH_ENABLED:
            logger.info("News refresh disabled (NEWS_REFRESH_ENABLED=false); background loop not started.")
            return
        self._task = asyncio.create_task(self._run_forever(), name="news-refresh-scheduler")
        logger.info("News refresh scheduler started (interval=%ss).", self._settings.NEWS_REFRESH_INTERVAL_SECONDS)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_forever(self) -> None:
        await asyncio.sleep(self._settings.NEWS_REFRESH_INITIAL_DELAY_SECONDS)
        while True:
            try:
                await self.run_cycle_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — one bad cycle must never kill the loop
                logger.exception("Unhandled error in news refresh cycle.")
            await asyncio.sleep(self._settings.NEWS_REFRESH_INTERVAL_SECONDS)

    async def run_cycle_once(self):
        """One ingest + analyze pass. Returns (sync_result, analysis_result) or None if one is already running."""
        if self._lock.locked():
            logger.warning("Previous news cycle still running — skipping this tick.")
            return None
        async with self._lock:
            ingestion = self._ingestion or NewsIngestionService()
            sentiment = self._sentiment or SentimentAnalysisService()
            sync_result = await ingestion.sync_latest()
            analysis = await sentiment.analyze_pending()
            logger.info(
                "Sentiment: analyzed=%d failed=%d model=%s%s",
                analysis.analyzed, analysis.failed, analysis.model_status,
                f" ({analysis.error})" if analysis.error else "",
            )
            return sync_result, analysis


_scheduler: Optional[NewsRefreshScheduler] = None


def get_news_scheduler() -> NewsRefreshScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = NewsRefreshScheduler()
    return _scheduler
