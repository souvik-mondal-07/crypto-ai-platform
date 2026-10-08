"""Phase 14: translating the existing module outputs into availability-aware engine inputs."""

from datetime import timedelta
from types import SimpleNamespace as NS

from app.config.risk_config import DEFAULT_ENGINE_CONFIG
from app.services import decision_inputs as di
from tests.decision_fixtures import NOW

CFG = DEFAULT_ENGINE_CONFIG.decision


def tech(**over):
    base = dict(
        calculated_at=NOW - timedelta(minutes=2), timeframe="30D", trend=NS(trend="bullish"),
        rsi=NS(current=61.0), macd=NS(current=NS(histogram=0.8), crossover="none"),
        moving_averages=NS(sma={"20": 99.0, "50": None}, ema={"20": 98.0}),
        bollinger_bands=NS(upper=110.0, middle=100.0, lower=90.0), atr=NS(current=2.0),
        support_resistance=NS(support_levels=[95.0], resistance_levels=[110.0]), volume=NS(trend="increasing"),
    )
    base.update(over)
    return NS(**base)


def fundamentals(**over):
    metric = lambda v: NS(value=v)  # noqa: E731
    base = dict(
        score=NS(status="scored", score=72.0, coverage_percent=85.0),
        calculated_metrics=NS(market_cap_to_fdv=metric(0.9), circulating_to_max_supply_percent=metric(None),
                              distance_from_ath_percent=metric(-40.0)),
        market=NS(market_cap_rank=5), supply=NS(supply_type="not_reported"),
        freshness=NS(market_data_is_stale=False), timestamps=NS(calculated_at=NOW),
    )
    base.update(over)
    return NS(**base)


def sentiment(**over):
    base = dict(status="ok", model_status="ready", total_articles=12, average_score=0.3, sentiment_label="positive",
                positive_percent=55.0, negative_percent=15.0, trend=NS(direction="improving"),
                min_articles_required=3, timeframe="24h", calculated_at=NOW)
    base.update(over)
    return NS(**base)


def prediction(**over):
    base = dict(generated_at=NOW - timedelta(minutes=5), horizon="24h", model="xgboost", direction="up",
                predicted_return=0.02, predicted_return_range=NS(lower=0.005, upper=0.03), confidence=0.64,
                confidence_status="calibrated")
    base.update(over)
    return NS(**base)


def snapshot(**over):
    base = dict(price_usd=100.0, market_cap_usd=1e9, volume_24h_usd=5e7, high_24h_usd=103.0, low_24h_usd=97.0,
                percent_change_24h=1.0, percent_change_7d=2.0, percent_change_30d=None, percent_change_1y=None,
                last_updated=NOW, is_stale=False)
    base.update(over)
    return NS(**base)


# ---- market ---------------------------------------------------------------------------------


def test_market_snapshot_is_available_when_it_has_a_price():
    m = di.market_from_snapshot(snapshot())
    assert m.status.usable and m.price_usd == 100.0 and m.percent_change_30d is None


def test_missing_market_snapshot_is_reported_missing():
    m = di.market_from_snapshot(None)
    assert m.status.state == "missing" and m.price_usd is None


def test_stale_market_snapshot_is_reported_stale_not_usable():
    m = di.market_from_snapshot(snapshot(is_stale=True))
    assert m.status.state == "stale" and not m.status.usable


def test_market_snapshot_without_a_price_is_insufficient():
    assert di.market_from_snapshot(snapshot(price_usd=None)).status.state == "insufficient_data"
    assert di.market_from_snapshot(snapshot(price_usd=0)).status.state == "insufficient_data"


def test_non_finite_market_numbers_are_dropped_not_propagated():
    m = di.market_from_snapshot(snapshot(volume_24h_usd=float("nan"), market_cap_usd=float("inf")))
    assert m.volume_24h_usd is None and m.market_cap_usd is None


# ---- technical -------------------------------------------------------------------------------


def test_technical_response_maps_to_inputs():
    t = di.technical_from_response(tech(), NOW, CFG)
    assert t.status.usable and t.trend == "bullish" and t.rsi == 61.0 and t.atr == 2.0
    assert t.sma == {"20": 99.0, "50": None} and t.support_levels == [95.0]


def test_old_technical_snapshot_is_stale():
    t = di.technical_from_response(tech(calculated_at=NOW - timedelta(hours=3)), NOW, CFG)
    assert t.status.state == "stale"


def test_naive_timestamps_are_treated_as_utc():
    t = di.technical_from_response(tech(calculated_at=(NOW - timedelta(minutes=1)).replace(tzinfo=None)), NOW, CFG)
    assert t.status.usable


# ---- fundamental -------------------------------------------------------------------------------


def test_scored_fundamentals_are_available():
    f = di.fundamental_from_response(fundamentals())
    assert f.status.usable and f.score == 72.0 and f.market_cap_rank == 5 and f.market_cap_to_fdv == 0.9


def test_not_enough_data_score_is_not_used_as_a_number():
    f = di.fundamental_from_response(fundamentals(score=NS(status="not_enough_data", score=None, coverage_percent=20.0)))
    assert f.score is None and f.status.usable  # rank / fdv metrics are still real data


def test_fundamentals_with_nothing_usable_are_insufficient():
    empty = NS(value=None)
    f = di.fundamental_from_response(fundamentals(
        score=NS(status="not_enough_data", score=None, coverage_percent=0.0),
        calculated_metrics=NS(market_cap_to_fdv=empty, circulating_to_max_supply_percent=empty, distance_from_ath_percent=empty),
        market=NS(market_cap_rank=None)))
    assert f.status.state == "insufficient_data"


def test_fundamentals_built_on_stale_market_data_are_stale():
    f = di.fundamental_from_response(fundamentals(freshness=NS(market_data_is_stale=True)))
    assert f.status.state == "stale"


# ---- sentiment -----------------------------------------------------------------------------------


def test_sentiment_ok_is_available():
    s = di.sentiment_from_response(sentiment())
    assert s.status.usable and s.average_score == 0.3 and s.trend_direction == "improving" and s.total_articles == 12


def test_sentiment_with_too_few_articles_is_insufficient_and_says_how_many():
    s = di.sentiment_from_response(sentiment(status="insufficient_data", average_score=None, sentiment_label=None, total_articles=1))
    assert s.status.state == "insufficient_data" and "1 analysed" in s.status.reason


def test_sentiment_model_disabled_with_no_articles_is_unavailable():
    s = di.sentiment_from_response(sentiment(status="insufficient_data", average_score=None, total_articles=0, model_status="disabled"))
    assert s.status.state == "unavailable"


# ---- prediction ------------------------------------------------------------------------------------


def test_prediction_maps_direction_return_range_and_confidence():
    p = di.prediction_from_response(prediction(), NOW, CFG)
    assert p.status.usable and p.direction == "up" and p.return_lower == 0.005 and p.confidence == 0.64


def test_prediction_without_a_range_still_maps():
    p = di.prediction_from_response(prediction(predicted_return_range=None), NOW, CFG)
    assert p.status.usable and p.return_lower is None and p.return_upper is None


def test_old_prediction_is_stale():
    p = di.prediction_from_response(prediction(generated_at=NOW - timedelta(hours=9)), NOW, CFG)
    assert p.status.state == "stale"


def test_prediction_without_a_direction_is_insufficient():
    assert di.prediction_from_response(prediction(direction=None), NOW, CFG).status.state == "insufficient_data"


def test_unavailable_input_carries_only_status_and_reason():
    p = di.unavailable_input("prediction", "unavailable", "model missing")
    assert not p.status.usable and p.status.reason == "model missing" and p.direction is None
