"""Prediction service (Phase 13).

    Coin -> Historical candles (Binance klines) -> ML features -> trained model
         -> prediction -> MongoDB `predictions` -> API

All ML logic lives in the repo-level `ml/` package; this service only resolves the
coin, fetches REAL recent candles/sentiment, calls `ml`, stores the result and
maps outcomes to API responses/errors. It never trains a model — training is the
explicit CLI `python -m ml.pipelines.training_pipeline`.

Outcomes:
    model_unavailable  -> 404 PREDICTION_MODEL_UNAVAILABLE
    insufficient_data  -> 422 INSUFFICIENT_HISTORICAL_DATA
    nothing stored     -> 404 PREDICTION_NOT_FOUND   (only on /latest)
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId

from app.config import get_settings
from app.core.exceptions import AppError
from app.providers.binance.provider import BinanceProvider
from app.repositories.coin_repository import CoinRepository
from app.repositories.news_repository import NewsRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.predictions import (
    ModelEvaluation,
    PredictionListResponse,
    PredictionResponse,
    PriceRange,
    ReturnRange,
    UnavailableHorizon,
)

logger = logging.getLogger("crypto_ai_platform.services.prediction")

# `ml/` lives at the repository root, next to `backend/`.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

HORIZON_ORDER = ("1h", "4h", "24h", "7d", "30d")


def _ml():
    """Import the ML package lazily so the API still starts if ML libs are missing."""
    try:
        from ml.config.model_config import HORIZONS, MLConfig, get_horizon
        from ml.data.loaders import candles_from_klines
        from ml.pipelines.prediction_pipeline import PredictionPipeline
    except ImportError as exc:  # numpy/pandas/scikit-learn not installed
        raise AppError(
            503, "PREDICTION_ENGINE_UNAVAILABLE",
            "The ML prediction engine is not installed on this server (see backend/requirements.txt).",
        ) from exc
    return HORIZONS, MLConfig, get_horizon, candles_from_klines, PredictionPipeline


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _build_config():
    _, MLConfig, *_ = _ml()
    s = get_settings()
    try:
        return MLConfig.from_mapping({
            "ML_ARTIFACT_DIR": s.ML_ARTIFACT_DIR,
            "ML_DEFAULT_HORIZON": s.ML_DEFAULT_HORIZON,
            "ML_DEFAULT_MODEL": s.ML_DEFAULT_MODEL,
            "ML_MIN_HISTORY_LENGTH": s.ML_MIN_HISTORY_LENGTH,
            "ML_PREDICTION_TTL_SECONDS": s.ML_PREDICTION_TTL_SECONDS,
        })
    except ValueError as exc:
        raise AppError(500, "PREDICTION_CONFIG_INVALID", f"Invalid ML configuration: {exc}") from exc


def validate_horizon(horizon: str) -> str:
    h = (horizon or "").lower()
    if h not in HORIZON_ORDER:
        raise AppError(400, "INVALID_HORIZON", f"horizon must be one of: {', '.join(HORIZON_ORDER)}.")
    return h


def to_response(doc: dict[str, Any], now: Optional[datetime] = None) -> PredictionResponse:
    """Stored document -> API response."""
    rng = doc.get("range") or {}
    rr = ReturnRange(lower=rng["return_lower"], upper=rng["return_upper"]) if rng.get("return_lower") is not None else None
    pr = PriceRange(lower=rng["price_lower"], upper=rng["price_upper"]) if rng.get("price_lower") is not None else None
    expires_at = _aware(doc["expires_at"])
    return PredictionResponse(
        coin_id=str(doc["coin_id"]),
        symbol=doc.get("symbol"),
        horizon=doc["horizon"],
        current_price=doc["current_price"],
        reference_time=_aware(doc["reference_time"]),
        target_time=_aware(doc["target_time"]),
        predicted_return=doc["prediction"]["predicted_return"],
        predicted_return_range=rr,
        predicted_price_range=pr,
        range_nominal_coverage=rng.get("nominal_coverage"),
        direction=doc["direction"],
        confidence=doc.get("confidence"),
        confidence_status=doc.get("confidence_status", "unavailable"),
        confidence_note=doc.get("confidence_note"),
        model=doc["model"],
        model_version=doc["model_version"],
        feature_version=doc["feature_version"],
        evaluation=ModelEvaluation(**doc["evaluation"]) if doc.get("evaluation") else None,
        trained_at=doc.get("trained_at"),
        generated_at=_aware(doc["generated_at"]),
        expires_at=expires_at,
        is_stale=expires_at <= (now or datetime.now(timezone.utc)),
    )


def result_to_document(result: Any, coin_oid: ObjectId) -> dict[str, Any]:
    """`ml` PredictionResult (status ok) -> document for the existing `predictions` collection."""
    rr = result.predicted_return_range or {}
    pr = result.predicted_price_range or {}
    return {
        "coin_id": coin_oid,
        "symbol": result.symbol,
        "horizon": result.horizon,
        "current_price": result.current_price,
        "prediction": {"predicted_return": result.predicted_return, "kind": result.kind},
        "range": {
            "return_lower": rr.get("lower"), "return_upper": rr.get("upper"),
            "price_lower": pr.get("lower"), "price_upper": pr.get("upper"),
            "nominal_coverage": result.range_nominal_coverage,
        } if rr else {},
        "direction": result.direction,
        "confidence": result.confidence,
        "confidence_status": result.confidence_status,
        "confidence_note": result.confidence_note,
        "model": result.model,
        "model_version": result.model_version,
        "feature_version": result.feature_version,
        "evaluation": result.model_metrics,
        "trained_at": result.trained_at,
        "reference_time": result.reference_time,
        "target_time": result.target_time,
        "generated_at": result.generated_at,
        "expires_at": result.expires_at,
        "created_at": result.generated_at,   # kept for the pre-existing (coin_id, horizon, created_at) index
        "status": "active",
    }


_locks: dict[tuple[str, str], asyncio.Lock] = {}


class PredictionService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        prediction_repository: Optional[PredictionRepository] = None,
        news_repository: Optional[NewsRepository] = None,
        binance_provider: Optional[BinanceProvider] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._predictions = prediction_repository or PredictionRepository()
        self._news = news_repository or NewsRepository()
        self._binance = binance_provider or BinanceProvider()

    # ------------------------------------------------------------------ public API

    async def get_prediction(self, coin_id: str, horizon: str, model: Optional[str] = None) -> PredictionResponse:
        """One horizon: a fresh stored prediction, else generate from the trained model."""
        h = validate_horizon(horizon)
        coin_oid, coin_doc = await self._resolve_coin(coin_id)
        outcome = await self._fresh_or_generate(coin_id, coin_oid, coin_doc, h, model)
        if isinstance(outcome, PredictionResponse):
            return outcome
        status, reason = outcome
        if status == "model_unavailable":
            raise AppError(404, "PREDICTION_MODEL_UNAVAILABLE", reason)
        raise AppError(422, "INSUFFICIENT_HISTORICAL_DATA", reason)

    async def list_predictions(self, coin_id: str) -> PredictionListResponse:
        """Every horizon that currently has a valid prediction (others listed as unavailable)."""
        coin_oid, coin_doc = await self._resolve_coin(coin_id)
        now = datetime.now(timezone.utc)
        results = await asyncio.gather(
            *[self._fresh_or_generate(coin_id, coin_oid, coin_doc, h, None) for h in HORIZON_ORDER]
        )
        ok: list[PredictionResponse] = []
        unavailable: list[UnavailableHorizon] = []
        for h, outcome in zip(HORIZON_ORDER, results):
            if isinstance(outcome, PredictionResponse):
                ok.append(outcome)
            else:
                unavailable.append(UnavailableHorizon(horizon=h, status=outcome[0], reason=outcome[1]))  # type: ignore[arg-type]
        return PredictionListResponse(
            coin_id=coin_id, symbol=coin_doc.get("symbol"), predictions=ok, unavailable=unavailable, generated_at=now
        )

    async def get_latest(self, coin_id: str, horizon: Optional[str] = None) -> PredictionResponse:
        """Most recent STORED prediction. Never generates one; `is_stale` says if it has expired."""
        h = validate_horizon(horizon) if horizon else None
        coin_oid, _ = await self._resolve_coin(coin_id)
        doc = (await self._predictions.get_latest(coin_oid, h)) if h else (await self._predictions.get_latest_any_horizon(coin_oid))
        if doc is None:
            raise AppError(404, "PREDICTION_NOT_FOUND", "No prediction has been generated for this coin yet.")
        return to_response(doc)

    # ------------------------------------------------------------------ internals

    async def _resolve_coin(self, coin_id: str) -> tuple[ObjectId, dict[str, Any]]:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        doc = await self._coins.find_by_internal_id(coin_id)
        if doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")
        return ObjectId(coin_id), doc

    async def _fresh_or_generate(self, coin_id, coin_oid, coin_doc, horizon, model):
        """PredictionResponse, or (status, reason) when no honest prediction can be made."""
        cached = await self._predictions.get_latest(coin_oid, horizon, model=model)
        if cached is not None and not PredictionRepository.is_expired(cached):
            return to_response(cached)

        # One generation per (coin, horizon) at a time; late arrivals reuse the stored result.
        lock = _locks.setdefault((coin_id, horizon), asyncio.Lock())
        async with lock:
            cached = await self._predictions.get_latest(coin_oid, horizon, model=model)
            if cached is not None and not PredictionRepository.is_expired(cached):
                return to_response(cached)
            return await self._generate(coin_id, coin_oid, coin_doc, horizon, model)

    async def _generate(self, coin_id, coin_oid, coin_doc, horizon, model):
        _, _, get_horizon, candles_from_klines, PredictionPipeline = _ml()
        config = _build_config()
        pipeline = PredictionPipeline(config)
        spec = get_horizon(horizon)

        # Cheap check first: no validated model -> no need to hit the exchange.
        if not await asyncio.to_thread(pipeline.has_model, coin_id, horizon):
            return ("model_unavailable", (
                f"No validated model is available for the {horizon} horizon. Models are trained "
                "explicitly (python -m ml.pipelines.training_pipeline) and only activated when they beat "
                "baseline checks on held-out data."))

        binance_symbol = ((coin_doc.get("providers") or {}).get("binance") or {}).get("symbol")
        if not binance_symbol:
            return ("insufficient_data",
                    "This coin has no exchange trading pair, so no real historical OHLCV data is available.")

        raw = await self._binance.get_klines(binance_symbol, spec.interval, spec.predict_candles + 50)
        candles = candles_from_klines(raw)
        articles = await self._sentiment_articles(coin_oid, spec)

        result = await asyncio.to_thread(
            pipeline.run, coin_id, horizon, candles, symbol=coin_doc.get("symbol"),
            sentiment_articles=articles, model_type=model,
        )
        if result.status != "ok":
            return (result.status, result.reason or "No prediction available.")
        doc = result_to_document(result, coin_oid)
        try:
            await self._predictions.insert(doc)
        except Exception:  # storing is best-effort; the computed prediction is still valid
            logger.warning("Could not store prediction for %s/%s", coin_id, horizon, exc_info=True)
        return to_response(doc)

    async def _sentiment_articles(self, coin_oid: ObjectId, spec) -> list[dict[str, Any]]:
        """Real analyzed articles from the news collection (point-in-time filtering happens in `ml`)."""
        now = datetime.now(timezone.utc)
        since = now - timedelta(seconds=spec.predict_candles * spec.interval_seconds)
        try:
            docs = await self._news.sentiment_points_for_coin(coin_oid, since, now)
        except Exception:
            logger.warning("Sentiment articles unavailable for prediction features", exc_info=True)
            return []
        return [
            {"published_at": d["published_at"], "label": d["sentiment"]["label"], "score": float(d["sentiment"]["score"])}
            for d in docs
            if isinstance(d.get("sentiment"), dict) and "label" in d["sentiment"] and "score" in d["sentiment"]
        ]
