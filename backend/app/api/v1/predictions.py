"""Prediction endpoints (Phase 13). Logic lives in PredictionService; this layer only validates input.

Like the other analysis endpoints, these are not individually token-gated (the
frontend routes are behind ProtectedRoute). Predictions are MODEL ESTIMATES.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.predictions import PredictionListResponse, PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


def _service() -> PredictionService:
    return PredictionService()


# Static path segment first so "latest" can never be captured as a coin id.
@router.get("/{coin_id}/latest", response_model=PredictionResponse)
async def get_latest_prediction(
    coin_id: str,
    horizon: Optional[str] = Query(None, description="1h | 4h | 24h | 7d | 30d (default: newest of any horizon)"),
) -> PredictionResponse:
    """Most recent stored prediction; never triggers generation. `is_stale` flags an expired one."""
    return await _service().get_latest(coin_id, horizon)


@router.get("/{coin_id}", response_model=PredictionListResponse | PredictionResponse)
async def get_predictions(
    coin_id: str,
    horizon: Optional[str] = Query(None, description="1h | 4h | 24h | 7d | 30d. Omit to list every available horizon."),
    model: Optional[str] = Query(None, pattern="^(xgboost|lightgbm|lstm|ridge|ensemble)$", description="Only use this model type"),
):
    """
    With `horizon`: one prediction (404 PREDICTION_MODEL_UNAVAILABLE / 422
    INSUFFICIENT_HISTORICAL_DATA when none can honestly be produced).
    Without: every horizon that has a valid prediction, plus why the others don't.
    """
    service = _service()
    if horizon is not None:
        return await service.get_prediction(coin_id, horizon, model)
    return await service.list_predictions(coin_id)
