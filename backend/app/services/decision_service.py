"""Decision service (Phase 14) — orchestration only. All scoring lives in the pure engines.

    Market data ─┐
    Technical    ─┤                                 ┌─> risk_service.calculate_risk
    Fundamental  ─┼─> DecisionInputs (availability) ─┤
    Sentiment    ─┤                                 └─> decision_engine.evaluate ─> BUY / HOLD / SELL
    ML prediction ┘                                                                     │
                                                          DecisionRepository (`decisions`) -> API

Rules this service follows:

* It only CONSUMES the existing modules' outputs (the same services the Coin
  Details page already calls). It never trains a model — the ML prediction comes
  from Phase 13's stored/generated prediction, and a missing/unavailable model is
  reported as such, never replaced by a made-up value.
* Every loader turns failures into an availability STATE (missing / insufficient /
  unavailable) with a reason, so one failing module can never crash the decision.
* Results are cached for `decision_ttl_seconds`; recalculation is per coin and
  serialised (one calculation at a time) so a burst of page loads costs one run.
* No LLM, no randomness, no trading.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Optional, TypeVar

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.config.risk_config import (
    DEFAULT_ENGINE_CONFIG,
    STATE_INSUFFICIENT,
    STATE_UNAVAILABLE,
    STATUS_VALID,
    EngineConfig,
)
from app.core.exceptions import AppError
from app.providers.errors import ProviderError
from app.providers.timeframes import Timeframe
from app.repositories.coin_repository import CoinRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.converters import market_data_doc_to_schema
from app.schemas.decisions import (
    AgreementSchema,
    DataQualitySchema,
    DataQualitySummary,
    DecisionResponse,
    ModuleQualitySchema,
    OverrideSchema,
    RiskComponentSchema,
    RiskResponse,
    RiskSchema,
    RiskSubFactorSchema,
    SignalScoresSchema,
    SignalsSchema,
)
from app.services import decision_inputs as di
from app.services.decision_engine import DecisionResult, evaluate
from app.services.fundamental_analysis_service import FundamentalAnalysisService
from app.services.prediction_service import PredictionService
from app.services.risk_service import RiskResult
from app.services.sentiment_service import SentimentService
from app.services.technical_analysis_service import TechnicalAnalysisService

logger = logging.getLogger("crypto_ai_platform.services.decision")

#: Technical indicators for the decision are computed over this range (30D => 4-hour candles),
#: the same default the Coin Details page uses.
DECISION_TECHNICAL_TIMEFRAME = Timeframe.DAY_30

T = TypeVar("T")
_locks: dict[str, asyncio.Lock] = {}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def _db(awaitable: Awaitable[T]) -> T:
    """MongoDB failure -> clean 503 instead of a generic 500."""
    try:
        return await awaitable
    except PyMongoError as exc:
        logger.error("Database error during decision calculation: %s", exc.__class__.__name__)
        raise AppError(503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable. Please try again shortly.") from exc


# ---------------------------------------------------------------------------
# Engine result -> API schema
# ---------------------------------------------------------------------------


def _risk_schema(risk: RiskResult) -> RiskSchema:
    return RiskSchema(
        available=risk.available,
        score=risk.score,
        level=risk.level,  # type: ignore[arg-type]
        coverage_percent=round(risk.coverage * 100.0, 1),
        components=[
            RiskComponentSchema(
                key=c.key, label=c.label, weight=c.weight, available=c.available, score=c.score,
                contribution=c.contribution, reason=c.reason,
                factors=[RiskSubFactorSchema(key=f.key, label=f.label, value=f.value, score=f.score, weight=f.weight)
                         for f in c.factors],
            )
            for c in risk.components
        ],
        positive_factors=risk.positive_factors,
        negative_factors=risk.negative_factors,
        reason=risk.reason,
        config_version=risk.config_version,
    )


def _data_quality_schema(quality: dict[str, Any]) -> DataQualitySchema:
    def module(key: str) -> ModuleQualitySchema:
        q = quality[key]
        return ModuleQualitySchema(available=q["available"], state=q["state"], reason=q["reason"], as_of=q["as_of"])

    return DataQualitySchema(
        market=module("market"), technical=module("technical"), fundamental=module("fundamental"),
        sentiment=module("sentiment"), prediction=module("prediction"),
        summary=DataQualitySummary(**quality["summary"]),
    )


def build_response(
    coin_id: str, symbol: Optional[str], result: DecisionResult, generated_at: datetime, expires_at: datetime,
    now: Optional[datetime] = None,
) -> DecisionResponse:
    sig = result.signals
    scores = result.signal_scores
    return DecisionResponse(
        coin_id=coin_id, symbol=symbol,
        decision=result.decision,  # type: ignore[arg-type]
        status=result.status,  # type: ignore[arg-type]
        status_reason=result.status_reason,
        decision_score=result.decision_score, raw_score=result.raw_score, risk_adjustment=result.risk_adjustment,
        confidence=result.confidence,
        confidence_status=result.confidence_status,  # type: ignore[arg-type]
        risk_score=result.risk.score, risk_level=result.risk.level,  # type: ignore[arg-type]
        risk=_risk_schema(result.risk),
        signals=SignalsSchema(technical=sig["technical"], fundamental=sig["fundamental"], sentiment=sig["sentiment"],
                              prediction=sig["prediction"], risk=sig["risk"]),
        signal_scores=SignalScoresSchema(technical=scores["technical"], fundamental=scores["fundamental"],
                                         sentiment=scores["sentiment"], prediction=scores["prediction"]),
        module_weights=result.effective_weights,
        positive_factors=result.positive_factors, negative_factors=result.negative_factors,
        base_decision=result.base_decision,  # type: ignore[arg-type]
        overrides=[OverrideSchema(**o) for o in result.overrides],
        agreement=AgreementSchema(**result.agreement),
        data_quality=_data_quality_schema(result.data_quality),
        warnings=result.warnings, explanation=result.explanation,
        generated_at=generated_at, expires_at=expires_at,
        is_stale=expires_at <= (now or datetime.now(timezone.utc)),
        engine_version=result.engine_version, risk_config_version=result.risk_config_version,
    )


def response_to_document(response: DecisionResponse, coin_oid: ObjectId) -> dict[str, Any]:
    """Document for the existing `decisions` collection.

    The queryable fields are top-level; the complete response is kept under `response` so a cached
    read rebuilds exactly what was calculated (no second code path that could drift).
    """
    return {
        "coin_id": coin_oid,
        "symbol": response.symbol,
        "decision": response.decision,
        "status": response.status,
        "decision_score": response.decision_score,
        "confidence": response.confidence,
        "confidence_status": response.confidence_status,
        "risk_score": response.risk_score,
        "risk_level": response.risk_level,
        "positive_factors": response.positive_factors,
        "negative_factors": response.negative_factors,
        "technical_signal": response.signals.technical,
        "fundamental_signal": response.signals.fundamental,
        "sentiment_signal": response.signals.sentiment,
        "prediction_signal": response.signals.prediction,
        "data_quality": response.data_quality.model_dump(mode="json"),
        "generated_at": response.generated_at,
        "expires_at": response.expires_at,
        "created_at": response.generated_at,
        "engine_version": response.engine_version,
        "risk_config_version": response.risk_config_version,
        "response": response.model_dump(mode="json"),
    }


def document_to_response(doc: dict[str, Any], now: Optional[datetime] = None) -> DecisionResponse:
    payload = dict(doc["response"])
    expires_at = _aware(doc["expires_at"])
    payload["is_stale"] = expires_at <= (now or datetime.now(timezone.utc))
    return DecisionResponse(**payload)


def to_risk_response(decision: DecisionResponse) -> RiskResponse:
    return RiskResponse(
        coin_id=decision.coin_id, symbol=decision.symbol, risk=decision.risk,
        risk_score=decision.risk_score, risk_level=decision.risk_level,
        positive_factors=decision.risk.positive_factors, negative_factors=decision.risk.negative_factors,
        data_quality=decision.data_quality, generated_at=decision.generated_at, expires_at=decision.expires_at,
        is_stale=decision.is_stale, engine_version=decision.engine_version,
        risk_config_version=decision.risk_config_version,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DecisionService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        decision_repository: Optional[DecisionRepository] = None,
        technical_service: Optional[TechnicalAnalysisService] = None,
        fundamental_service: Optional[FundamentalAnalysisService] = None,
        sentiment_service: Optional[SentimentService] = None,
        prediction_service: Optional[PredictionService] = None,
        config: EngineConfig = DEFAULT_ENGINE_CONFIG,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market = market_data_repository or MarketDataRepository()
        self._decisions = decision_repository or DecisionRepository()
        self._technical = technical_service or TechnicalAnalysisService()
        self._fundamental = fundamental_service or FundamentalAnalysisService()
        self._sentiment = sentiment_service or SentimentService()
        self._prediction = prediction_service or PredictionService()
        self._config = config

    # ------------------------------------------------------------------ public API

    async def get_decision(self, coin_id: str, force_refresh: bool = False) -> DecisionResponse:
        """A fresh stored decision, else a new calculation (never trains a model)."""
        coin_oid, coin_doc = await self._resolve_coin(coin_id)
        if not force_refresh:
            cached = await self._fresh_cached(coin_oid)
            if cached is not None:
                return cached
        lock = _locks.setdefault(coin_id, asyncio.Lock())
        async with lock:
            if not force_refresh:  # late arrivals reuse the result calculated while they waited
                cached = await self._fresh_cached(coin_oid)
                if cached is not None:
                    return cached
            return await self._calculate_and_store(coin_id, coin_oid, coin_doc)

    async def get_latest(self, coin_id: str) -> DecisionResponse:
        """Most recent STORED decision. Never calculates; `is_stale` says whether it has expired."""
        coin_oid, _ = await self._resolve_coin(coin_id)
        doc = await _db(self._decisions.get_latest(coin_oid))
        if doc is None or "response" not in doc:
            raise AppError(404, "DECISION_NOT_FOUND", "No decision has been generated for this coin yet.")
        return document_to_response(doc)

    async def get_risk(self, coin_id: str) -> RiskResponse:
        return to_risk_response(await self.get_decision(coin_id))

    # ------------------------------------------------------------------ internals

    async def _resolve_coin(self, coin_id: str) -> tuple[ObjectId, dict[str, Any]]:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        doc = await _db(self._coins.find_by_internal_id(coin_id))
        if doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        return ObjectId(coin_id), doc

    async def _fresh_cached(self, coin_oid: ObjectId) -> Optional[DecisionResponse]:
        doc = await _db(self._decisions.get_latest(coin_oid, engine_version=self._config.engine_version))
        if doc is None or "response" not in doc or DecisionRepository.is_expired(doc):
            return None
        return document_to_response(doc)

    async def _calculate_and_store(self, coin_id: str, coin_oid: ObjectId, coin_doc: dict[str, Any]) -> DecisionResponse:
        now = datetime.now(timezone.utc)
        inputs = await self._gather_inputs(coin_id, coin_oid, now)
        result = evaluate(inputs, self._config)
        dcfg = self._config.decision
        ttl = dcfg.decision_ttl_seconds if result.status == STATUS_VALID else dcfg.decision_failure_ttl_seconds
        response = build_response(coin_id, coin_doc.get("symbol"), result, now, now + timedelta(seconds=ttl), now)
        try:
            await self._decisions.insert(response_to_document(response, coin_oid))
        except Exception:  # storing is best-effort; the calculated decision is still valid
            logger.warning("Could not store decision for %s", coin_id, exc_info=True)
        return response

    async def _gather_inputs(self, coin_id: str, coin_oid: ObjectId, now: datetime) -> di.DecisionInputs:
        market, technical, fundamental, sentiment, prediction = await asyncio.gather(
            self._load_market(coin_oid),
            self._load_technical(coin_id, now),
            self._load_fundamental(coin_id),
            self._load_sentiment(coin_id),
            self._load_prediction(coin_id, now),
        )
        return di.DecisionInputs(market=market, technical=technical, fundamental=fundamental,
                                 sentiment=sentiment, prediction=prediction)

    # ---- loaders: each returns an input that carries its own availability state ----------

    async def _load_market(self, coin_oid: ObjectId) -> di.MarketInput:
        doc = await _db(self._market.get_by_coin_id(coin_oid))
        if doc is None:
            return di.market_from_snapshot(None)
        return di.market_from_snapshot(market_data_doc_to_schema(doc))

    async def _load_technical(self, coin_id: str, now: datetime) -> di.TechnicalInput:
        try:
            resp = await self._technical.get_technical_analysis(coin_id, DECISION_TECHNICAL_TIMEFRAME)
            return di.technical_from_response(resp, now, self._config.decision)
        except AppError as exc:
            state = STATE_INSUFFICIENT if exc.code == "INSUFFICIENT_HISTORICAL_DATA" else STATE_UNAVAILABLE
            return di.unavailable_input("technical", state, exc.message)
        except ProviderError:
            return di.unavailable_input("technical", STATE_UNAVAILABLE, "The market data provider is temporarily unavailable.")
        except Exception:
            logger.warning("Technical analysis unavailable for decision", exc_info=True)
            return di.unavailable_input("technical", STATE_UNAVAILABLE, "Technical analysis could not be loaded.")

    async def _load_fundamental(self, coin_id: str) -> di.FundamentalInput:
        try:
            return di.fundamental_from_response(await self._fundamental.get_fundamentals(coin_id))
        except AppError as exc:
            state = STATE_INSUFFICIENT if exc.code == "FUNDAMENTALS_NOT_AVAILABLE" else STATE_UNAVAILABLE
            return di.unavailable_input("fundamental", state, exc.message)
        except ProviderError:
            return di.unavailable_input("fundamental", STATE_UNAVAILABLE, "The market data provider is temporarily unavailable.")
        except Exception:
            logger.warning("Fundamental analysis unavailable for decision", exc_info=True)
            return di.unavailable_input("fundamental", STATE_UNAVAILABLE, "Fundamental analysis could not be loaded.")

    async def _load_sentiment(self, coin_id: str) -> di.SentimentInput:
        """24h sentiment; when that has too few analysed articles, the 7d window is used (and said so)."""
        try:
            first = di.sentiment_from_response(await self._sentiment.get_coin_sentiment(coin_id, "24h"))
            if first.status.usable:
                return first
            wider = di.sentiment_from_response(await self._sentiment.get_coin_sentiment(coin_id, "7d"))
            if wider.status.usable:
                wider.status.reason = "Based on the last 7 days (too few analysed articles in the last 24 hours)."
                return wider
            return first
        except AppError as exc:
            return di.unavailable_input("sentiment", STATE_UNAVAILABLE, exc.message)
        except Exception:
            logger.warning("Sentiment unavailable for decision", exc_info=True)
            return di.unavailable_input("sentiment", STATE_UNAVAILABLE, "Sentiment could not be loaded.")

    async def _load_prediction(self, coin_id: str, now: datetime) -> di.PredictionInput:
        """Phase 13 prediction at the default horizon: stored-fresh, else generated from a TRAINED model.

        No model is ever trained here. If the model/engine is missing the input is marked unavailable
        (the decision rules say what that means); a slow generation falls back to the latest stored one.
        """
        settings = get_settings()
        horizon = settings.ML_DEFAULT_HORIZON
        timeout = settings.DECISION_PREDICTION_TIMEOUT_SECONDS
        try:
            resp = await asyncio.wait_for(self._prediction.get_prediction(coin_id, horizon), timeout=timeout)
            return di.prediction_from_response(resp, now, self._config.decision)
        except asyncio.TimeoutError:
            try:
                resp = await self._prediction.get_latest(coin_id, horizon)
                return di.prediction_from_response(resp, now, self._config.decision)
            except Exception:
                return di.unavailable_input("prediction", STATE_UNAVAILABLE, "The prediction took too long to generate.")
        except AppError as exc:
            if exc.code == "INSUFFICIENT_HISTORICAL_DATA":
                return di.unavailable_input("prediction", STATE_INSUFFICIENT, exc.message)
            if exc.code in ("PREDICTION_NOT_FOUND", "PREDICTION_MODEL_UNAVAILABLE"):
                return di.unavailable_input("prediction", STATE_UNAVAILABLE, exc.message)
            return di.unavailable_input("prediction", STATE_UNAVAILABLE, exc.message)
        except ProviderError:
            return di.unavailable_input("prediction", STATE_UNAVAILABLE, "The market data provider is temporarily unavailable.")
        except Exception:
            logger.warning("Prediction unavailable for decision", exc_info=True)
            return di.unavailable_input("prediction", STATE_UNAVAILABLE, "The prediction could not be loaded.")


__all__ = ["DecisionService", "build_response", "document_to_response", "response_to_document", "to_risk_response"]
