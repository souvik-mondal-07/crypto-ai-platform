"""API-level tests for /api/v1/predictions (service mocked — no MongoDB, no provider calls)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.schemas.predictions import (
    DISCLAIMER, ModelEvaluation, PredictionListResponse, PredictionResponse, PriceRange, ReturnRange, UnavailableHorizon,
)

COIN_ID = "507f1f77bcf86cd799439011"
NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _prediction(horizon="24h", **over) -> PredictionResponse:
    base = dict(
        coin_id=COIN_ID, symbol="AAA", horizon=horizon, current_price=100.0,
        reference_time=NOW, target_time=NOW + timedelta(hours=24),
        predicted_return=0.024, predicted_return_range=ReturnRange(lower=0.01, upper=0.04),
        predicted_price_range=PriceRange(lower=101.0, upper=104.0), range_nominal_coverage=0.8,
        direction="up", confidence=0.61, confidence_status="calibrated", model="xgboost", model_version="v1",
        feature_version="v1", evaluation=ModelEvaluation(test_mae=0.01, baseline_mae=0.012, test_directional_accuracy=0.57, test_samples=400),
        trained_at="2026-01-01T00:00:00+00:00", generated_at=NOW, expires_at=NOW + timedelta(minutes=15),
    )
    base.update(over)
    return PredictionResponse(**base)


def test_single_horizon_returns_the_standard_schema(client):
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.get_prediction = AsyncMock(return_value=_prediction())
        r = client.get(f"/api/v1/predictions/{COIN_ID}?horizon=24h")
    assert r.status_code == 200
    body = r.json()
    for key in ("coin_id", "symbol", "current_price", "horizon", "predicted_return", "predicted_price_range", "direction",
                "confidence", "confidence_status", "model", "model_version", "generated_at", "expires_at", "kind", "disclaimer"):
        assert key in body
    assert body["kind"] == "model_prediction" and body["disclaimer"] == DISCLAIMER
    assert body["predicted_price_range"]["lower"] < body["predicted_price_range"]["upper"]
    # Phase 14 / later-phase content must not leak into this response.
    for forbidden in ("decision", "recommendation", "risk", "action", "explanation"):
        assert forbidden not in body
    svc.return_value.get_prediction.assert_awaited_once_with(COIN_ID, "24h", None)


def test_without_horizon_lists_available_and_unavailable(client):
    listing = PredictionListResponse(
        coin_id=COIN_ID, symbol="AAA", predictions=[_prediction("1h"), _prediction("24h")],
        unavailable=[UnavailableHorizon(horizon="7d", status="model_unavailable", reason="no model")], generated_at=NOW,
    )
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.list_predictions = AsyncMock(return_value=listing)
        r = client.get(f"/api/v1/predictions/{COIN_ID}")
    assert r.status_code == 200
    body = r.json()
    assert [p["horizon"] for p in body["predictions"]] == ["1h", "24h"]
    assert body["unavailable"][0]["status"] == "model_unavailable"


def test_unavailable_confidence_is_null_not_invented(client):
    p = _prediction(confidence=None, confidence_status="unavailable", confidence_note="not calibrated")
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.get_prediction = AsyncMock(return_value=p)
        body = client.get(f"/api/v1/predictions/{COIN_ID}?horizon=24h").json()
    assert body["confidence"] is None and body["confidence_status"] == "unavailable"


@pytest.mark.parametrize("code,status", [
    ("INVALID_HORIZON", 400), ("INVALID_COIN_ID", 400), ("COIN_NOT_FOUND", 404),
    ("PREDICTION_MODEL_UNAVAILABLE", 404), ("INSUFFICIENT_HISTORICAL_DATA", 422), ("PREDICTION_NOT_FOUND", 404),
])
def test_service_errors_are_mapped_to_clean_http_errors(client, code, status):
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.get_prediction = AsyncMock(side_effect=AppError(status, code, "explained"))
        r = client.get(f"/api/v1/predictions/{COIN_ID}?horizon=24h")
    assert r.status_code == status
    assert r.json() == {"error": {"code": code, "message": "explained"}}


def test_latest_route_is_not_captured_as_a_coin_id(client):
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.get_latest = AsyncMock(return_value=_prediction(is_stale=True))
        r = client.get(f"/api/v1/predictions/{COIN_ID}/latest?horizon=24h")
    assert r.status_code == 200 and r.json()["is_stale"] is True
    svc.return_value.get_latest.assert_awaited_once_with(COIN_ID, "24h")


def test_latest_without_stored_prediction_is_404(client):
    with patch("app.api.v1.predictions.PredictionService") as svc:
        svc.return_value.get_latest = AsyncMock(side_effect=AppError(404, "PREDICTION_NOT_FOUND", "none yet"))
        r = client.get(f"/api/v1/predictions/{COIN_ID}/latest")
    assert r.status_code == 404 and r.json()["error"]["code"] == "PREDICTION_NOT_FOUND"


def test_unknown_model_query_value_is_rejected_before_the_service(client):
    with patch("app.api.v1.predictions.PredictionService") as svc:
        r = client.get(f"/api/v1/predictions/{COIN_ID}?horizon=24h&model=gpt")
    assert r.status_code == 422
    svc.return_value.get_prediction.assert_not_called()


def test_prediction_router_is_registered_under_the_v1_prefix(client):
    paths = {route.path for route in app.routes}
    assert "/api/v1/predictions/{coin_id}" in paths and "/api/v1/predictions/{coin_id}/latest" in paths
