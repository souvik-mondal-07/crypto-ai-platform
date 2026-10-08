"""
API-level tests for GET /api/v1/coins/{coin_id}/fundamentals, with the
service layer mocked — no MongoDB, no live provider calls. Also checks
that the route contains no business logic of its own.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import app
from app.providers.errors import ProviderRateLimitError, ProviderUnavailableError
from app.schemas.fundamentals import (
    CalculatedMetric,
    CalculatedMetrics,
    FundamentalAnalysisResponse,
    FundamentalFreshness,
    FundamentalScore,
    FundamentalTimestamps,
    MarketOverview,
    ProjectInfo,
    SupplyData,
)
from app.services import fundamental_calculations as calc

VALID_COIN_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _metric(value, unit="ratio", reason=None):
    return CalculatedMetric(value=value, unit=unit, formula="f", unavailable_reason=reason)


def _response(**overrides) -> FundamentalAnalysisResponse:
    data = dict(
        coin_id=VALID_COIN_ID, symbol="EXC", name="Examplecoin", source="coingecko", market_data_source="coingecko",
        market=MarketOverview(market_cap_usd=1e9, market_cap_rank=12, volume_24h_usd=5e7),
        supply=SupplyData(circulating_supply=15e6, max_supply=21e6, supply_type="capped"),
        project_info=ProjectInfo(categories=["Layer 1 (L1)"], genesis_date="2015-01-01"),
        calculated_metrics=CalculatedMetrics(
            volume_to_market_cap=_metric(0.05),
            market_cap_to_fdv=_metric(None, reason="Fully diluted valuation is not available."),
            circulating_to_max_supply_percent=_metric(71.4, "percent"),
            remaining_to_max_supply_percent=_metric(28.6, "percent"),
            remaining_supply_to_max=_metric(6e6, "tokens"),
            circulating_to_total_supply_percent=_metric(None, "percent", "Total supply is not available."),
            distance_from_ath_percent=_metric(-75.0, "percent"),
            distance_from_atl_percent=_metric(400.0, "percent"),
        ),
        score=FundamentalScore(
            status="not_enough_data", score=None, coverage_percent=35.0, min_coverage_percent=50.0,
            components=[], method_version=calc.SCORE_METHOD_VERSION, message="Not enough data",
            disclaimer=calc.SCORE_DISCLAIMER,
        ),
        timestamps=FundamentalTimestamps(
            fetched_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            calculated_at=datetime(2026, 9, 30, 1, tzinfo=timezone.utc),
        ),
        freshness=FundamentalFreshness(),
        is_partial=True, unavailable_sections=["ecosystem"], warnings=["example warning"],
    )
    data.update(overrides)
    return FundamentalAnalysisResponse(**data)


def _get(client, service_mock, path_suffix=""):
    with patch("app.api.v1.coins.FundamentalAnalysisService") as cls:
        cls.return_value.get_fundamentals = service_mock
        return client.get(f"/api/v1/coins/{VALID_COIN_ID}/fundamentals{path_suffix}")


def test_returns_structured_fundamentals_with_nulls_preserved(client):
    response = _get(client, AsyncMock(return_value=_response()))
    assert response.status_code == 200
    body = response.json()
    assert body["market"]["market_cap_usd"] == 1e9
    assert body["supply"]["supply_type"] == "capped"
    assert body["calculated_metrics"]["origin"] == "calculated"
    assert body["calculated_metrics"]["market_cap_to_fdv"]["value"] is None
    assert body["calculated_metrics"]["market_cap_to_fdv"]["unavailable_reason"]
    assert body["score"]["status"] == "not_enough_data" and body["score"]["score"] is None
    assert body["is_partial"] is True and body["unavailable_sections"] == ["ecosystem"]
    assert body["timestamps"]["fetched_at"] and body["timestamps"]["calculated_at"]
    assert body["valuation"] is None  # absent sections stay null, never fabricated


def test_response_never_contains_a_trading_decision(client):
    body = _get(client, AsyncMock(return_value=_response())).json()
    flat = str(body).lower()
    for word in ("'buy'", "'sell'", "'hold'", "recommendation"):
        assert word not in flat


def test_force_refresh_query_flag_is_passed_to_the_service(client):
    mock = AsyncMock(return_value=_response())
    _get(client, mock, "?force_refresh=true")
    mock.assert_awaited_once_with(VALID_COIN_ID, force_refresh=True)


def test_force_refresh_defaults_to_false(client):
    mock = AsyncMock(return_value=_response())
    _get(client, mock)
    mock.assert_awaited_once_with(VALID_COIN_ID, force_refresh=False)


@pytest.mark.parametrize(
    "status,code",
    [(400, "INVALID_COIN_ID"), (404, "COIN_NOT_FOUND"), (404, "FUNDAMENTALS_NOT_AVAILABLE"), (503, "DATABASE_UNAVAILABLE")],
)
def test_app_errors_use_the_standard_error_shape(client, status, code):
    response = _get(client, AsyncMock(side_effect=AppError(status, code, "message")))
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_provider_failure_maps_to_503(client):
    response = _get(client, AsyncMock(side_effect=ProviderUnavailableError("down")))
    assert response.status_code == 503
    assert "error" in response.json()


def test_provider_rate_limit_maps_to_429(client):
    response = _get(client, AsyncMock(side_effect=ProviderRateLimitError("slow down")))
    assert response.status_code == 429


def test_route_is_registered_under_the_coins_prefix(client):
    paths = [route.path for route in app.routes]
    assert "/api/v1/coins/{coin_id}/fundamentals" in paths
