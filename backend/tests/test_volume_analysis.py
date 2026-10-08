from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

from app.services.technical_analysis_service import TechnicalAnalysisService

@pytest.mark.asyncio
@pytest.mark.parametrize(("series", "expected"), [
    ([100.0] * 10 + [120.0] * 10, "increasing"),
    ([100.0] * 10 + [80.0] * 10, "decreasing"),
    ([100.0] * 20, "neutral"),
])
async def test_volume_period_comparison(series, expected):
    svc = TechnicalAnalysisService.__new__(TechnicalAnalysisService)
    svc._market_data = SimpleNamespace(get_by_coin_id=AsyncMock(return_value={"volume_24h_usd": 999.0}))
    candles = [SimpleNamespace(timestamp=datetime.now(timezone.utc), volume=v) for v in series]
    out = await svc._volume_analysis("507f1f77bcf86cd799439011", candles)
    assert out.trend == expected
    assert out.current_volume_24h_usd == 999.0
    assert out.average_volume == pytest.approx(sum(series[-10:]) / 10)
    assert out.volume_change_percent == pytest.approx((series[-1] / series[0] - 1) * 100)
    assert len(out.historical_volume) == 20

@pytest.mark.asyncio
async def test_missing_or_insufficient_volume_does_not_invent_comparison():
    svc = TechnicalAnalysisService.__new__(TechnicalAnalysisService)
    svc._market_data = SimpleNamespace(get_by_coin_id=AsyncMock(return_value=None))
    candles = [SimpleNamespace(timestamp=datetime.now(timezone.utc), volume=None)]
    out = await svc._volume_analysis("507f1f77bcf86cd799439011", candles)
    assert out.trend == "unavailable"
    assert out.average_volume is None and out.volume_change_percent is None
    assert out.historical_volume == []

@pytest.mark.asyncio
async def test_zero_baseline_is_finite_and_unclassified():
    svc = TechnicalAnalysisService.__new__(TechnicalAnalysisService)
    svc._market_data = SimpleNamespace(get_by_coin_id=AsyncMock(return_value=None))
    vals = [0.0] * 10 + [10.0] * 10
    candles = [SimpleNamespace(timestamp=datetime.now(timezone.utc), volume=v) for v in vals]
    out = await svc._volume_analysis("507f1f77bcf86cd799439011", candles)
    assert out.trend == "unavailable"
    assert out.volume_change_percent is None
