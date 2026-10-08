"""
Sentiment analysis job (Phase 12): classifies stored articles that have
not been analyzed yet and persists the result on the article.

Runs after each ingestion cycle (and on demand). If the model is
unavailable, articles simply stay `pending` — nothing is guessed — and
the next cycle tries again (the model service rate-limits reload attempts).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings
from app.repositories.news_repository import NewsRepository
from app.services.sentiment_model import (
    SentimentModelError,
    SentimentModelService,
    SentimentModelUnavailableError,
    get_sentiment_model_service,
)

logger = logging.getLogger("crypto_ai_platform.services.sentiment_analysis")


@dataclass
class AnalysisResult:
    analyzed: int = 0
    failed: int = 0
    pending_seen: int = 0
    model_status: str = "not_loaded"
    error: Optional[str] = None


def build_model_input(doc: dict[str, Any]) -> str:
    title = (doc.get("title") or "").strip()
    description = (doc.get("description") or "").strip()
    return f"{title}. {description}" if description else title


class SentimentAnalysisService:
    def __init__(
        self,
        repository: Optional[NewsRepository] = None,
        model_service: Optional[SentimentModelService] = None,
    ) -> None:
        self._repository = repository or NewsRepository()
        self._model = model_service or get_sentiment_model_service()

    async def analyze_pending(self, limit: Optional[int] = None) -> AnalysisResult:
        settings = get_settings()
        result = AnalysisResult(model_status=self._model.status)
        if not settings.SENTIMENT_ENABLED:
            result.error = "disabled"
            return result

        docs = await self._repository.find_pending_sentiment(limit or settings.SENTIMENT_MAX_ARTICLES_PER_CYCLE)
        result.pending_seen = len(docs)
        batch_size = max(1, settings.SENTIMENT_BATCH_SIZE)

        for start in range(0, len(docs), batch_size):
            batch = docs[start : start + batch_size]
            try:
                predictions = await self._model.classify([build_model_input(d) for d in batch])
            except SentimentModelUnavailableError as exc:
                result.error = str(exc)
                break  # leave the rest pending; retried next cycle
            except SentimentModelError as exc:
                logger.warning("Sentiment batch failed: %s", exc)
                result.failed += len(batch)
                continue

            analyzed_at = datetime.now(timezone.utc)
            model_name = self._model.model_name or "unknown"
            updates = [
                (
                    doc["news_id"],
                    {
                        "label": p.label,
                        "score": p.score,
                        "confidence": p.confidence,
                        "probabilities": p.probabilities,
                        "model": model_name,
                        "analyzed_at": analyzed_at,
                    },
                )
                for doc, p in zip(batch, predictions)
            ]
            await self._repository.save_sentiments(updates)
            result.analyzed += len(updates)

        result.model_status = self._model.status
        return result
