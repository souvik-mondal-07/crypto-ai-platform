"""AI analysis service (Phase 15) — orchestration of the Gemini EXPLANATION layer.

    Market ─┐
    Technical ─┤
    Fundamental ┤
    News ───────┼─> structured payload (app.ai.payload) ─> GeminiService ─> validated explanation
    Sentiment ──┤                                                              │
    ML prediction ┤                                         ai_analysis collection (cache) -> API
    Phase 14 Risk & Decision ┘  (official BUY/HOLD/SELL — copied, never decided here)

Rules this service follows:

* It only CONSUMES the existing services' outputs. The Phase 14 decision is the source of truth and is
  copied into the stored `decision_snapshot`; Gemini's text can never change it.
* Gemini is an enhancement. Every failure becomes a clean `AppError` (stable code, user-safe message);
  nothing else in the application depends on this service.
* Cost protection: a stored analysis is reused until it expires or the Phase 14 decision changes
  materially; generation is serialised per coin (concurrent callers share one call), globally capped,
  rate-limited per coin (manual regeneration cooldown) and backs off after failures / 429s.
* Failed attempts are never stored as analyses, and no analysis is ever fabricated.
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Optional, TypeVar

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.ai.payload import (
    availability_of, build_payload, coin_section, decision_section, fundamental_section, insufficient_reason,
    market_section, news_section, prediction_section, risk_section, sentiment_section, technical_section,
    unavailable,
)
from app.ai.prompts.market_analysis_prompt import PROMPT_VERSION, render_payload
from app.ai.schemas.ai_analysis import (
    AI_DISCLAIMER, AIAnalysisContent, AIAnalysisResponse, AIDecisionSnapshot, AIModuleAvailability,
)
from app.config import Settings, get_settings
from app.core.exceptions import AppError
from app.providers.errors import ProviderError
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.converters import market_data_doc_to_schema
from app.schemas.decisions import DecisionResponse
from app.services.decision_service import DECISION_TECHNICAL_TIMEFRAME, DecisionService
from app.services.fundamental_analysis_service import FundamentalAnalysisService
from app.services.gemini_service import GeminiError, GeminiNotConfiguredError, GeminiResult, GeminiService
from app.services.news_service import NewsService
from app.services.prediction_service import PredictionService
from app.services.sentiment_service import SentimentService
from app.services.technical_analysis_service import TechnicalAnalysisService

logger = logging.getLogger("crypto_ai_platform.services.ai_analysis")

T = TypeVar("T")

#: A stored explanation is "outdated" when the Phase 14 decision it explains changed in these ways.
OUTDATED_SCORE_DRIFT = 15.0
OUTDATED_CONFIDENCE_DRIFT = 15.0

#: Seconds to refuse new Gemini calls for a coin after a failure of the given kind.
RATE_LIMIT_BACKOFF_SECONDS = 60.0
FAILURE_BACKOFF_SECONDS = 15.0

_locks: dict[str, asyncio.Lock] = {}
_failures: dict[str, tuple[float, GeminiError]] = {}  # coin_id -> (monotonic time until, error)
_semaphore: Optional[asyncio.Semaphore] = None
_semaphore_key: Optional[tuple[int, int]] = None


def _generation_slot(limit: int) -> asyncio.Semaphore:
    """Global cap on simultaneous Gemini requests (re-created if the loop or limit changes)."""
    global _semaphore, _semaphore_key
    key = (id(asyncio.get_running_loop()), max(1, limit))
    if _semaphore is None or _semaphore_key != key:
        _semaphore, _semaphore_key = asyncio.Semaphore(key[1]), key
    return _semaphore


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _db(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except PyMongoError as exc:
        logger.error("Database error during AI analysis: %s", exc.__class__.__name__)
        raise AppError(503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable. Please try again shortly.") from exc


def decision_changed_materially(snapshot: dict[str, Any], current: Optional[DecisionResponse]) -> bool:
    """Has the official Phase 14 result moved enough that the stored explanation no longer matches it?"""
    if current is None:
        return False
    if snapshot.get("decision") != current.decision or snapshot.get("status") != current.status:
        return True
    if snapshot.get("risk_level") != current.risk_level:
        return True
    for key, now_value, limit in (
        ("decision_score", current.decision_score, OUTDATED_SCORE_DRIFT),
        ("confidence", current.confidence, OUTDATED_CONFIDENCE_DRIFT),
    ):
        before = snapshot.get(key)
        if before is not None and now_value is not None and abs(before - now_value) >= limit:
            return True
    return False


def _snapshot(decision: DecisionResponse) -> dict[str, Any]:
    return {
        "decision": decision.decision, "status": decision.status, "risk_level": decision.risk_level,
        "risk_score": decision.risk_score, "confidence": decision.confidence, "decision_score": decision.decision_score,
        "engine_version": decision.engine_version, "generated_at": decision.generated_at,
    }


def to_app_error(exc: GeminiError) -> AppError:
    message = exc.message
    if exc.retry_after_seconds:
        message = f"{message} Try again in about {int(exc.retry_after_seconds) + 1} seconds."
    return AppError(exc.http_status, exc.code, message)


class AIAnalysisService:
    def __init__(
        self,
        repository: Optional[AIAnalysisRepository] = None,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        decision_service: Optional[DecisionService] = None,
        technical_service: Optional[TechnicalAnalysisService] = None,
        fundamental_service: Optional[FundamentalAnalysisService] = None,
        sentiment_service: Optional[SentimentService] = None,
        news_service: Optional[NewsService] = None,
        prediction_service: Optional[PredictionService] = None,
        gemini_service: Optional[GeminiService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self._repo = repository or AIAnalysisRepository()
        self._coins = coin_repository or CoinRepository()
        self._market = market_data_repository or MarketDataRepository()
        self._decision = decision_service or DecisionService()
        self._technical = technical_service or TechnicalAnalysisService()
        self._fundamental = fundamental_service or FundamentalAnalysisService()
        self._sentiment = sentiment_service or SentimentService()
        self._news = news_service or NewsService()
        self._prediction = prediction_service or PredictionService()
        self._gemini = gemini_service or GeminiService()
        self._settings = settings

    @property
    def _cfg(self) -> Settings:
        return self._settings or get_settings()

    # ------------------------------------------------------------------ public API

    async def get_latest(self, coin_id: str) -> AIAnalysisResponse:
        """The most recent STORED analysis. Never calls Gemini (so a page refresh costs nothing)."""
        coin_oid, _ = await self._resolve_coin(coin_id)
        doc = await self._latest_doc(coin_oid)
        if doc is None:
            raise AppError(404, "AI_ANALYSIS_NOT_FOUND", "No AI analysis has been generated for this coin yet.")
        return self._to_response(doc, cached=True, outdated=decision_changed_materially(
            doc["decision_snapshot"], await self._stored_decision(coin_id)))

    async def generate(self, coin_id: str, force: bool = False) -> AIAnalysisResponse:
        """A fresh stored analysis when one exists, otherwise a new Gemini explanation.

        `force=True` asks for a new one even if a fresh one exists, subject to the per-coin cooldown.
        """
        coin_oid, coin_doc = await self._resolve_coin(coin_id)

        # What was stored before this request waited for the lock; anything newer was produced by a
        # concurrent request and is reused instead of calling Gemini a second time.
        before = await self._latest_doc(coin_oid)
        baseline = _aware(before["generated_at"]) if before is not None else None

        served = await self._reusable(coin_id, coin_oid, force)
        if served is not None:
            return served

        if not self._gemini.is_configured:
            raise to_app_error(GeminiNotConfiguredError())
        self._raise_if_backing_off(coin_id)

        lock = _locks.setdefault(coin_id, asyncio.Lock())
        async with lock:
            # A concurrent request may have generated while this one waited: reuse it (one Gemini call).
            served = await self._reusable(coin_id, coin_oid, force=False, just_waited=True, baseline=baseline)
            if served is not None:
                return served
            self._raise_if_backing_off(coin_id)
            async with _generation_slot(self._cfg.AI_ANALYSIS_MAX_CONCURRENT_GENERATIONS):
                return await self._generate_and_store(coin_id, coin_oid, coin_doc)

    # ------------------------------------------------------------------ cache decisions

    async def _reusable(
        self, coin_id: str, coin_oid: ObjectId, force: bool, just_waited: bool = False,
        baseline: Optional[datetime] = None,
    ) -> Optional[AIAnalysisResponse]:
        """The stored analysis to serve instead of generating, or None to generate.

        Raises the cooldown error for a forced regeneration that comes too soon. `just_waited` is the
        re-check made after acquiring the per-coin lock: it reuses ONLY an analysis stored after
        `baseline` (i.e. generated by a concurrent request while this one waited). A merely fresh
        analysis that was already there must not block a forced regeneration that is past its cooldown.
        """
        doc = await self._latest_doc(coin_oid)
        if doc is None:
            return None
        now = datetime.now(timezone.utc)
        age = (now - _aware(doc["generated_at"])).total_seconds()
        min_interval = self._cfg.AI_ANALYSIS_MIN_REGENERATE_INTERVAL_SECONDS
        outdated = decision_changed_materially(doc["decision_snapshot"], await self._stored_decision(coin_id))
        fresh = not AIAnalysisRepository.is_expired(doc, now)

        if just_waited:
            produced_meanwhile = baseline is None or _aware(doc["generated_at"]) > baseline
            return self._to_response(doc, cached=True, outdated=outdated) if produced_meanwhile else None
        if force:
            if age < min_interval:
                wait = int(min_interval - age) + 1
                raise AppError(429, "AI_ANALYSIS_COOLDOWN", f"An analysis was generated moments ago. Try again in about {wait} seconds.")
            return None
        if fresh and not outdated:
            return self._to_response(doc, cached=True, outdated=False)
        if age < min_interval:  # expired/outdated, but too recent to spend another call on
            return self._to_response(doc, cached=True, outdated=outdated)
        return None

    def _raise_if_backing_off(self, coin_id: str) -> None:
        entry = _failures.get(coin_id)
        if entry is None:
            return
        until, error = entry
        remaining = until - time.monotonic()
        if remaining <= 0:
            _failures.pop(coin_id, None)
            return
        raise to_app_error(type(error)(**({"retry_after_seconds": remaining} if error.code == "AI_RATE_LIMITED" else {})))

    @staticmethod
    def _note_failure(coin_id: str, error: GeminiError) -> None:
        if error.code in ("AI_RATE_LIMITED",):
            delay = max(error.retry_after_seconds or 0.0, RATE_LIMIT_BACKOFF_SECONDS)
        elif error.code in ("AI_TIMEOUT", "AI_UNAVAILABLE", "AI_INVALID_RESPONSE"):
            delay = FAILURE_BACKOFF_SECONDS
        else:
            return
        _failures[coin_id] = (time.monotonic() + delay, error)

    # ------------------------------------------------------------------ generation

    async def _generate_and_store(self, coin_id: str, coin_oid: ObjectId, coin_doc: dict[str, Any]) -> AIAnalysisResponse:
        decision = await self._decision.get_decision(coin_id)  # the official Phase 14 result
        payload = await self._gather_payload(coin_id, coin_oid, coin_doc, decision)

        reason = insufficient_reason(payload)
        if reason:
            raise AppError(422, "AI_INSUFFICIENT_DATA", reason)

        try:
            result = await self._gemini.generate_analysis(payload)
        except GeminiError as exc:
            self._note_failure(coin_id, exc)
            raise to_app_error(exc) from exc
        _failures.pop(coin_id, None)

        now = datetime.now(timezone.utc)
        document = self._build_document(coin_oid, coin_doc, decision, payload, result, now)
        try:
            await self._repo.insert(document)
        except Exception:  # storing is best-effort; the generated explanation is still valid
            logger.warning("Could not store AI analysis for %s", coin_id, exc_info=True)
        return self._to_response(document, cached=False, outdated=False)

    def _build_document(
        self, coin_oid: ObjectId, coin_doc: dict[str, Any], decision: DecisionResponse, payload: dict[str, Any],
        result: GeminiResult, now: datetime,
    ) -> dict[str, Any]:
        return {
            "coin_id": coin_oid,
            "symbol": coin_doc.get("symbol"),
            "status": "ready",
            "model": result.model,
            "model_version": result.model_version,
            "prompt_version": PROMPT_VERSION,
            "analysis": result.output.model_dump(),
            "decision_snapshot": _snapshot(decision),
            "data_availability": {k: v.model_dump() for k, v in availability_of(payload).items()},
            "source_data_timestamp": decision.generated_at,
            "generated_at": now,
            "expires_at": now + timedelta(seconds=self._cfg.AI_ANALYSIS_TTL_SECONDS),
            "created_at": now,
            "latency_ms": result.latency_ms,
            "attempts": result.attempts,
            "prompt_tokens": result.prompt_tokens,
            "output_tokens": result.output_tokens,
            "payload_sha256": hashlib.sha256(render_payload(payload).encode("utf-8")).hexdigest(),
        }

    # ------------------------------------------------------------------ payload assembly

    async def _gather_payload(
        self, coin_id: str, coin_oid: ObjectId, coin_doc: dict[str, Any], decision: DecisionResponse
    ) -> dict[str, Any]:
        market, technical, fundamental, news, sentiment, prediction = await asyncio.gather(
            self._load_market(coin_oid), self._load_technical(coin_id), self._load_fundamental(coin_id),
            self._load_news(coin_id), self._load_sentiment(coin_id), self._load_prediction(coin_id),
        )
        return build_payload(
            coin=coin_section(coin_id, coin_doc.get("symbol"), coin_doc.get("name")),
            market=market, technical=technical, fundamental=fundamental, news=news, sentiment=sentiment,
            prediction=prediction, risk=risk_section(decision), decision=decision_section(decision),
        )

    @staticmethod
    def _why(exc: BaseException, what: str) -> str:
        if isinstance(exc, AppError):
            return exc.message
        if isinstance(exc, ProviderError):
            return "The market data provider is temporarily unavailable."
        logger.warning("%s unavailable for AI analysis: %s", what, type(exc).__name__)
        return f"{what} could not be loaded."

    async def _load_market(self, coin_oid: ObjectId) -> dict[str, Any]:
        try:
            doc = await self._market.get_by_coin_id(coin_oid)
            return market_section(market_data_doc_to_schema(doc) if doc is not None else None)
        except Exception as exc:
            return unavailable(self._why(exc, "Market data"))

    async def _load_technical(self, coin_id: str) -> dict[str, Any]:
        try:
            return technical_section(await self._technical.get_technical_analysis(coin_id, DECISION_TECHNICAL_TIMEFRAME))
        except Exception as exc:
            return technical_section(None, self._why(exc, "Technical analysis"))

    async def _load_fundamental(self, coin_id: str) -> dict[str, Any]:
        try:
            return fundamental_section(await self._fundamental.get_fundamentals(coin_id))
        except Exception as exc:
            return fundamental_section(None, self._why(exc, "Fundamental analysis"))

    async def _load_news(self, coin_id: str) -> dict[str, Any]:
        try:
            resp = await self._news.list_news(coin_id=coin_id, page=1, limit=10)
            return news_section(resp.items, resp.total)
        except Exception as exc:
            return news_section(None, reason=self._why(exc, "News"))

    async def _load_sentiment(self, coin_id: str) -> dict[str, Any]:
        """24h sentiment; the 7d window when 24h has too few analysed articles (the same rule as Phase 14)."""
        try:
            first = await self._sentiment.get_coin_sentiment(coin_id, "24h")
            if first.status == "ok":
                return sentiment_section(first)
            wider = await self._sentiment.get_coin_sentiment(coin_id, "7d")
            return sentiment_section(wider if wider.status == "ok" else first)
        except Exception as exc:
            return sentiment_section(None, self._why(exc, "Sentiment"))

    async def _load_prediction(self, coin_id: str) -> dict[str, Any]:
        """The latest STORED Phase 13 prediction at the default horizon. Never trains or generates one here."""
        try:
            return prediction_section(await self._prediction.get_latest(coin_id, self._cfg.ML_DEFAULT_HORIZON))
        except Exception as exc:
            return prediction_section(None, self._why(exc, "The prediction"))

    # ------------------------------------------------------------------ helpers

    async def _resolve_coin(self, coin_id: str) -> tuple[ObjectId, dict[str, Any]]:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        doc = await _db(self._coins.find_by_internal_id(coin_id))
        if doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        return ObjectId(coin_id), doc

    async def _latest_doc(self, coin_oid: ObjectId) -> Optional[dict[str, Any]]:
        doc = await _db(self._repo.get_latest(coin_oid, prompt_version=PROMPT_VERSION, model=self._gemini.model))
        return doc if doc is not None and "analysis" in doc and "decision_snapshot" in doc else None

    async def _stored_decision(self, coin_id: str) -> Optional[DecisionResponse]:
        """The latest stored Phase 14 decision (no calculation); None when there is none."""
        try:
            return await self._decision.get_latest(coin_id)
        except Exception:
            return None

    def _to_response(self, doc: dict[str, Any], *, cached: bool, outdated: bool) -> AIAnalysisResponse:
        now = datetime.now(timezone.utc)
        generated_at = _aware(doc["generated_at"])
        expires_at = _aware(doc["expires_at"])
        snap = dict(doc["decision_snapshot"])
        snap["generated_at"] = _aware(snap["generated_at"])
        next_at = generated_at + timedelta(seconds=self._cfg.AI_ANALYSIS_MIN_REGENERATE_INTERVAL_SECONDS)
        return AIAnalysisResponse(
            coin_id=str(doc["coin_id"]),
            symbol=doc.get("symbol"),
            analysis=AIAnalysisContent(**{**doc["analysis"], "disclaimer": AI_DISCLAIMER}),
            decision_snapshot=AIDecisionSnapshot(**snap),
            data_availability={k: AIModuleAvailability(**v) for k, v in (doc.get("data_availability") or {}).items()},
            model=doc["model"],
            model_version=doc.get("model_version"),
            prompt_version=doc["prompt_version"],
            source_data_timestamp=_aware(doc["source_data_timestamp"]),
            generated_at=generated_at,
            expires_at=expires_at,
            is_stale=expires_at <= now,
            is_outdated=outdated,
            cached=cached,
            next_regeneration_at=next_at if next_at > now else None,
        )


__all__ = ["AIAnalysisService", "decision_changed_materially", "to_app_error"]
