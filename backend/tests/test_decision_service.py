"""DecisionService (Phase 14) with fake repositories and fake module services — no MongoDB, no providers, no model."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.providers.errors import ProviderUnavailableError
from app.schemas.decisions import DISCLAIMER, DecisionResponse
from app.services.decision_service import DecisionService, document_to_response, response_to_document, to_risk_response
from tests.test_decision_inputs import fundamentals, prediction, sentiment, tech

COIN_ID = "507f1f77bcf86cd799439011"
COIN_OID = ObjectId(COIN_ID)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeCoins:
    def __init__(self, found=True):
        self.found = found

    async def find_by_internal_id(self, coin_id):
        return {"_id": ObjectId(coin_id), "symbol": "AAA", "name": "Aaa"} if self.found else None


class FakeMarket:
    def __init__(self, doc="default"):
        now = _now()
        self.doc = {
            "coin_id": COIN_OID, "price_usd": 100.0, "market_cap_usd": 5e10, "volume_24h_usd": 2e9, "high_24h_usd": 101.0,
            "low_24h_usd": 99.0, "percent_change_24h": 1.0, "percent_change_7d": 3.0, "data_source": "coingecko",
            "updated_at": now, "last_updated": now,
        } if doc == "default" else doc

    async def get_by_coin_id(self, coin_id):
        return self.doc


class FakeDecisions:
    def __init__(self):
        self.docs = []

    async def insert(self, doc):
        self.docs.append(doc)

    async def get_latest(self, coin_id, engine_version=None):
        matching = [d for d in self.docs if d["coin_id"] == coin_id and (engine_version is None or d["engine_version"] == engine_version)]
        return matching[-1] if matching else None


def _tech_resp():
    now = _now()
    return tech(calculated_at=now)


def _fund_resp():
    return fundamentals()


def _sent_resp():
    return sentiment(calculated_at=_now())


def _pred_resp():
    return prediction(generated_at=_now())


def build(*, coins=None, market=None, decisions=None, technical=None, fundamental=None, senti=None, pred=None) -> DecisionService:
    technical = technical or NS(get_technical_analysis=AsyncMock(return_value=_tech_resp()))
    fundamental = fundamental or NS(get_fundamentals=AsyncMock(return_value=_fund_resp()))
    senti = senti or NS(get_coin_sentiment=AsyncMock(return_value=_sent_resp()))
    pred = pred or NS(get_prediction=AsyncMock(return_value=_pred_resp()), get_latest=AsyncMock(side_effect=AppError(404, "PREDICTION_NOT_FOUND", "none")))
    return DecisionService(
        coin_repository=coins or FakeCoins(), market_data_repository=market or FakeMarket(),
        decision_repository=decisions or FakeDecisions(), technical_service=technical,
        fundamental_service=fundamental, sentiment_service=senti, prediction_service=pred,
    )


# ---- input validation ------------------------------------------------------------------------------


async def test_invalid_coin_id_is_rejected():
    with pytest.raises(AppError) as err:
        await build().get_decision("not-an-id")
    assert err.value.status_code == 400 and err.value.code == "INVALID_COIN_ID"


async def test_unknown_coin_is_404():
    with pytest.raises(AppError) as err:
        await build(coins=FakeCoins(found=False)).get_decision(COIN_ID)
    assert err.value.status_code == 404 and err.value.code == "COIN_NOT_FOUND"


async def test_latest_with_nothing_stored_is_404_and_never_calculates():
    technical = NS(get_technical_analysis=AsyncMock())
    with pytest.raises(AppError) as err:
        await build(technical=technical).get_latest(COIN_ID)
    assert err.value.code == "DECISION_NOT_FOUND"
    technical.get_technical_analysis.assert_not_awaited()


# ---- full decision -----------------------------------------------------------------------------------


async def test_full_decision_is_valid_and_complete():
    result = await build().get_decision(COIN_ID)
    assert isinstance(result, DecisionResponse)
    assert result.status == "VALID" and result.decision in ("BUY", "HOLD", "SELL")
    assert result.symbol == "AAA" and result.coin_id == COIN_ID
    assert result.risk_level is not None and 0 <= result.risk_score <= 100
    assert result.signals.technical in ("BULLISH", "NEUTRAL", "BEARISH")
    assert result.data_quality.prediction.available is True
    assert result.engine_version == "1.0" and result.risk_config_version == "1.0"
    assert result.kind == "model_based_decision" and result.disclaimer == DISCLAIMER
    assert result.expires_at > result.generated_at and result.is_stale is False


async def test_decision_is_stored_in_the_decisions_collection_with_queryable_fields():
    decisions = FakeDecisions()
    result = await build(decisions=decisions).get_decision(COIN_ID)
    (doc,) = decisions.docs
    for key in ("coin_id", "symbol", "decision", "decision_score", "confidence", "risk_score", "risk_level",
                "positive_factors", "negative_factors", "technical_signal", "fundamental_signal", "sentiment_signal",
                "prediction_signal", "data_quality", "generated_at", "expires_at", "engine_version"):
        assert key in doc
    assert doc["coin_id"] == COIN_OID and doc["decision"] == result.decision and doc["risk_level"] == result.risk_level


async def test_fresh_stored_decision_is_reused_without_recalculating():
    decisions = FakeDecisions()
    technical = NS(get_technical_analysis=AsyncMock(return_value=_tech_resp()))
    service = build(decisions=decisions, technical=technical)
    first = await service.get_decision(COIN_ID)
    second = await service.get_decision(COIN_ID)
    assert technical.get_technical_analysis.await_count == 1 and len(decisions.docs) == 1
    assert second.generated_at == first.generated_at and second.decision == first.decision


async def test_expired_stored_decision_is_recalculated():
    decisions = FakeDecisions()
    technical = NS(get_technical_analysis=AsyncMock(return_value=_tech_resp()))
    service = build(decisions=decisions, technical=technical)
    await service.get_decision(COIN_ID)
    decisions.docs[0]["expires_at"] = _now() - timedelta(seconds=1)
    await service.get_decision(COIN_ID)
    assert technical.get_technical_analysis.await_count == 2 and len(decisions.docs) == 2


async def test_force_refresh_recalculates():
    technical = NS(get_technical_analysis=AsyncMock(return_value=_tech_resp()))
    service = build(technical=technical)
    await service.get_decision(COIN_ID)
    await service.get_decision(COIN_ID, force_refresh=True)
    assert technical.get_technical_analysis.await_count == 2


async def test_concurrent_requests_cost_one_calculation():
    async def slow(*_a, **_k):
        await asyncio.sleep(0.05)
        return _tech_resp()

    technical = NS(get_technical_analysis=AsyncMock(side_effect=slow))
    service = build(technical=technical)
    results = await asyncio.gather(*[service.get_decision(COIN_ID) for _ in range(4)])
    assert technical.get_technical_analysis.await_count == 1
    assert len({r.generated_at for r in results}) == 1


async def test_latest_returns_the_stored_decision_and_flags_expiry():
    decisions = FakeDecisions()
    service = build(decisions=decisions)
    await service.get_decision(COIN_ID)
    assert (await service.get_latest(COIN_ID)).is_stale is False
    decisions.docs[0]["expires_at"] = _now() - timedelta(minutes=1)
    assert (await service.get_latest(COIN_ID)).is_stale is True


async def test_storing_failure_does_not_lose_the_calculated_decision():
    class Broken(FakeDecisions):
        async def insert(self, doc):
            raise RuntimeError("write failed")

    assert (await build(decisions=Broken()).get_decision(COIN_ID)).status == "VALID"


# ---- unavailable prediction (Phase 13 engine / model not available) ----------------------------------------------


@pytest.mark.parametrize("code,status", [
    ("PREDICTION_ENGINE_UNAVAILABLE", 503), ("PREDICTION_MODEL_UNAVAILABLE", 404), ("INSUFFICIENT_HISTORICAL_DATA", 422),
])
async def test_unavailable_prediction_does_not_break_the_decision(code, status):
    pred = NS(get_prediction=AsyncMock(side_effect=AppError(status, code, "The prediction engine is not available on the server right now.")),
              get_latest=AsyncMock(side_effect=AppError(404, "PREDICTION_NOT_FOUND", "none")))
    result = await build(pred=pred).get_decision(COIN_ID)
    assert result.status == "VALID" and result.decision is not None
    assert result.data_quality.prediction.available is False
    assert result.data_quality.summary.prediction_available is False
    assert result.signals.prediction == "UNAVAILABLE" and result.signal_scores.prediction is None
    assert any("ML prediction unavailable" in w for w in result.warnings)


async def test_a_slow_prediction_falls_back_to_the_latest_stored_one(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "DECISION_PREDICTION_TIMEOUT_SECONDS", 0.01)

    async def slow(*_a, **_k):
        await asyncio.sleep(0.5)

    pred = NS(get_prediction=AsyncMock(side_effect=slow), get_latest=AsyncMock(return_value=_pred_resp()))
    result = await build(pred=pred).get_decision(COIN_ID)
    assert result.data_quality.prediction.available is True
    pred.get_latest.assert_awaited_once()


async def test_a_slow_prediction_with_nothing_stored_is_unavailable(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "DECISION_PREDICTION_TIMEOUT_SECONDS", 0.01)

    async def slow(*_a, **_k):
        await asyncio.sleep(0.5)

    pred = NS(get_prediction=AsyncMock(side_effect=slow), get_latest=AsyncMock(side_effect=AppError(404, "PREDICTION_NOT_FOUND", "none")))
    result = await build(pred=pred).get_decision(COIN_ID)
    assert result.data_quality.prediction.available is False and result.status == "VALID"


async def test_the_decision_service_never_trains_or_imports_training_code():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "app" / "services" / "decision_service.py").read_text(encoding="utf-8").lower()
    assert "training_pipeline" not in text and "trainer" not in text and ".fit(" not in text


# ---- other modules failing ------------------------------------------------------------------------------------------


async def test_missing_sentiment_does_not_break_the_decision():
    senti = NS(get_coin_sentiment=AsyncMock(return_value=sentiment(status="insufficient_data", average_score=None, total_articles=0, sentiment_label=None)))
    result = await build(senti=senti).get_decision(COIN_ID)
    assert result.status == "VALID" and result.data_quality.sentiment.available is False
    assert result.data_quality.sentiment.state == "insufficient_data"


async def test_sentiment_falls_back_to_the_7_day_window_and_says_so():
    calls = []

    async def by_window(_coin, timeframe):
        calls.append(timeframe)
        if timeframe == "24h":
            return sentiment(status="insufficient_data", average_score=None, total_articles=1, sentiment_label=None)
        return sentiment(timeframe="7d", total_articles=9)

    result = await build(senti=NS(get_coin_sentiment=AsyncMock(side_effect=by_window))).get_decision(COIN_ID)
    assert calls == ["24h", "7d"]
    assert result.data_quality.sentiment.available is True and "7 days" in result.data_quality.sentiment.reason


async def test_provider_failure_in_technical_analysis_is_isolated():
    technical = NS(get_technical_analysis=AsyncMock(side_effect=ProviderUnavailableError("down")))
    result = await build(technical=technical).get_decision(COIN_ID)
    assert result.data_quality.technical.state == "unavailable" and result.status == "VALID"


async def test_unexpected_module_exception_is_isolated():
    fundamental = NS(get_fundamentals=AsyncMock(side_effect=RuntimeError("boom")))
    result = await build(fundamental=fundamental).get_decision(COIN_ID)
    assert result.data_quality.fundamental.state == "unavailable" and result.status == "VALID"
    assert "boom" not in " ".join(result.warnings)  # internal error text is never leaked


async def test_no_market_data_gives_insufficient_data_not_a_fake_decision():
    result = await build(market=FakeMarket(doc=None)).get_decision(COIN_ID)
    assert result.status == "INSUFFICIENT_DATA" and result.decision is None
    assert result.confidence is None and result.confidence_status == "unavailable"
    assert result.risk_score is None and result.risk_level is None
    assert result.expires_at - result.generated_at <= timedelta(seconds=120)  # failures are retried soon


async def test_stale_market_data_gives_stale_data_status():
    old = _now() - timedelta(hours=12)
    doc = {"coin_id": COIN_OID, "price_usd": 100.0, "market_cap_usd": 5e10, "volume_24h_usd": 2e9, "data_source": "coingecko",
           "updated_at": old, "last_updated": old}
    result = await build(market=FakeMarket(doc=doc)).get_decision(COIN_ID)
    assert result.status == "STALE_DATA" and result.decision is None


async def test_every_module_failing_gives_a_status_not_an_exception():
    boom = AppError(503, "X", "down")
    result = await build(
        technical=NS(get_technical_analysis=AsyncMock(side_effect=boom)),
        fundamental=NS(get_fundamentals=AsyncMock(side_effect=boom)),
        senti=NS(get_coin_sentiment=AsyncMock(side_effect=boom)),
        pred=NS(get_prediction=AsyncMock(side_effect=boom), get_latest=AsyncMock(side_effect=boom)),
    ).get_decision(COIN_ID)
    assert result.decision is None and result.status in ("ANALYSIS_UNAVAILABLE", "INSUFFICIENT_DATA")


# ---- risk endpoint / round trip ---------------------------------------------------------------------------------------------


async def test_risk_response_carries_score_level_components_and_factors():
    risk = await build().get_risk(COIN_ID)
    assert risk.risk_level is not None and len(risk.risk.components) == 6
    assert {c.key for c in risk.risk.components} == {"volatility", "liquidity", "technical", "fundamental", "sentiment", "prediction"}
    assert abs(sum(c.weight for c in risk.risk.components) - 1.0) < 1e-9


async def test_document_round_trip_rebuilds_the_same_response():
    result = await build().get_decision(COIN_ID)
    doc = response_to_document(result, COIN_OID)
    again = document_to_response(doc)
    assert again.model_dump(exclude={"is_stale"}) == result.model_dump(exclude={"is_stale"})
    assert to_risk_response(again).risk_score == result.risk_score


async def test_same_inputs_give_the_same_decision_values():
    a = await build().get_decision(COIN_ID)
    b = await build().get_decision(COIN_ID)
    for field in ("decision", "decision_score", "confidence", "risk_score", "risk_level", "positive_factors", "negative_factors"):
        assert getattr(a, field) == getattr(b, field)
