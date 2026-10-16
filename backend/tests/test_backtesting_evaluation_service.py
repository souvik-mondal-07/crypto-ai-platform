"""Phase 17 — prediction/decision outcome matching, storage and accuracy reporting (service level).

Uses the real repositories over an in-memory database and real `ml.evaluation` code; only the exchange is faked
with explicit candles, so every expected number below is derivable by hand.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AppError
from app.database.collections import CollectionName as C
from app.services.evaluation_service import EvaluationService
from tests.backtesting_fixtures import BASE, FakeHistory, coins, db, decision_doc, history_for, prediction_doc, rising_closes  # noqa: F401

CLOSES = rising_closes()


def _now():
    return datetime.now(timezone.utc)


def _service(history):
    return EvaluationService(history=history)


def _seed_predictions(db, coins, count=35, **kw):
    docs = [prediction_doc(coins["btc_oid"], k, **kw) for k in range(count)]
    db[C.PREDICTIONS].docs.extend(docs)
    return docs


async def test_refresh_matches_matured_predictions_with_hand_checkable_returns(db, coins):
    _seed_predictions(db, coins, 35)
    report = await _service(history_for()).refresh_outcomes(_now())
    assert report["predictions"]["matched"] == 35 and report["predictions"]["provider_errors"] == 0
    results = db[C.PREDICTION_RESULTS].docs
    assert len(results) == 35 and all(r["record_type"] == "prediction" and r["status"] == "matched" for r in results)
    first = min(results, key=lambda r: r["reference_time"])
    # reference = close(candle 0) = 100.0 ; actual = close(candle 24) = 102.4 (price 24h later)
    assert first["actual_price"] == pytest.approx(102.4) and first["actual_return"] == pytest.approx(0.024)
    assert first["methodology_version"] and first["match_gap_seconds"] == 0
    assert first["direction_correct"] is True and first["error"] == pytest.approx(0.01 - 0.024) and first["prediction_id"] == first["source_id"]


async def test_refresh_is_idempotent_and_never_duplicates(db, coins):
    _seed_predictions(db, coins, 35)
    svc = _service(history_for())
    await svc.refresh_outcomes(_now())
    again = await svc.refresh_outcomes(_now())
    assert len(db[C.PREDICTION_RESULTS].docs) == 35
    assert again["predictions"]["pending"] == 0


async def test_unmatured_predictions_are_not_stored_or_counted(db, coins):
    _seed_predictions(db, coins, 3)
    future = prediction_doc(coins["btc_oid"], 24 * 19 + 5, reference_price=100.0)   # target is in the future
    db[C.PREDICTIONS].docs.append(future)
    await _service(history_for()).refresh_outcomes(_now())
    stored_ids = {r["source_id"] for r in db[C.PREDICTION_RESULTS].docs}
    assert future["_id"] not in stored_ids and len(stored_ids) == 3


async def test_provider_outage_stores_nothing_and_is_retried(db, coins):
    _seed_predictions(db, coins, 5)
    down = FakeHistory({}, fail=True)
    report = await _service(down).refresh_outcomes(_now())
    assert report["predictions"]["provider_errors"] == 1 and db[C.PREDICTION_RESULTS].docs == []
    ok = await _service(history_for()).refresh_outcomes(_now())          # next refresh succeeds
    assert ok["predictions"]["matched"] == 5


async def test_empty_download_is_not_mistaken_for_missing_prices(db, coins):
    _seed_predictions(db, coins, 5)
    await _service(FakeHistory({})).refresh_outcomes(_now())
    assert db[C.PREDICTION_RESULTS].docs == []


async def test_missing_reference_price_is_stored_as_unmatched_not_wrong(db, coins):
    doc = prediction_doc(coins["btc_oid"], 0)
    doc["current_price"] = None
    db[C.PREDICTIONS].docs.append(doc)
    await _service(history_for()).refresh_outcomes(_now())
    (res,) = db[C.PREDICTION_RESULTS].docs
    assert res["status"] == "missing_reference_price" and res["actual_return"] is None


async def test_unsupported_horizon_and_unmapped_coin_are_recorded_not_matched(db, coins):
    bad = prediction_doc(coins["btc_oid"], 0)
    bad["horizon"] = "2h"
    unmapped = prediction_doc(coins["eth_oid"], 0)
    db[C.PREDICTIONS].docs.extend([bad, unmapped])
    await _service(history_for()).refresh_outcomes(_now())
    statuses = {r["source_id"]: r["status"] for r in db[C.PREDICTION_RESULTS].docs}
    assert statuses[bad["_id"]] == "unsupported_horizon" and statuses[unmapped["_id"]] == "missing_future_price"


async def test_accuracy_reports_insufficient_data_without_zeros(db, coins):
    _seed_predictions(db, coins, 5)
    svc = _service(history_for())
    await svc.refresh_outcomes(_now())
    data = await svc.accuracy()
    overall = data["overall"]
    assert overall["status"] == "insufficient_data" and overall["sample_size"] == 5
    assert overall["mae"] is None and overall["rmse"] is None and overall["directional_accuracy"] is None
    assert "Insufficient historical predictions" in overall["message"]


async def test_accuracy_with_enough_matured_predictions(db, coins):
    _seed_predictions(db, coins, 35, predicted_return=0.02)
    svc = _service(history_for())
    await svc.refresh_outcomes(_now())
    data = await svc.accuracy()
    o = data["overall"]
    actual = [CLOSES[k + 24] / CLOSES[k] - 1 for k in range(35)]
    assert o["status"] == "ok" and o["sample_size"] == 35
    assert o["directional_accuracy"] == 1.0                           # prices only rose, every call was "up"
    assert o["mae"] == pytest.approx(sum(abs(0.02 - a) for a in actual) / 35)
    assert o["rmse"] == pytest.approx((sum((0.02 - a) ** 2 for a in actual) / 35) ** 0.5)
    assert o["range_coverage"] == 1.0 and o["nominal_coverage"] == pytest.approx(0.8)
    assert [h["horizon"] for h in data["by_horizon"]] == ["24h"]
    assert data["by_model"][0]["model"] == "xgboost" and data["by_model"][0]["model_version"] == "1"
    assert data["coverage"]["matured_predictions"] == 35 and data["coverage"]["pending_outcomes"] == 0


async def test_accuracy_filters_by_horizon_model_version_and_coin(db, coins):
    _seed_predictions(db, coins, 35)
    _seed_predictions(db, coins, 35, model_version="2", direction="down")
    svc = _service(history_for())
    await svc.refresh_outcomes(_now())
    v1 = await svc.accuracy(model_version="1")
    v2 = await svc.accuracy(model_version="2")
    assert v1["overall"]["directional_accuracy"] == 1.0 and v2["overall"]["directional_accuracy"] == 0.0
    assert (await svc.accuracy(horizon="7d"))["overall"]["status"] == "no_data"
    assert (await svc.accuracy(coin_id=coins["btc"]))["coin"]["symbol"] == "BTC"
    with pytest.raises(AppError) as exc:
        await svc.accuracy(horizon="2h")
    assert exc.value.code == "UNSUPPORTED_HORIZON" and exc.value.status_code == 422


async def test_duplicate_predictions_are_removed_from_metrics(db, coins):
    a = prediction_doc(coins["btc_oid"], 0)
    b = prediction_doc(coins["btc_oid"], 0, generated_at=BASE + timedelta(hours=2))      # same coin/horizon/model/reference time
    db[C.PREDICTIONS].docs.extend([a, b])
    svc = _service(history_for())
    await svc.refresh_outcomes(_now())
    data = await svc.accuracy()
    assert data["coverage"]["duplicates_removed"] == 1 and data["overall"]["sample_size"] == 1


async def test_no_predictions_gives_an_honest_limitation(db, coins):
    data = await _service(history_for()).accuracy()
    assert data["overall"]["status"] == "no_data" and data["overall"]["mae"] is None
    assert any("No predictions have been stored" in m for m in data["limitations"])


async def test_decision_evaluation_rules(db, coins):
    # 10 BUYs on the rising series: forward returns all > 0
    for k in range(10):
        db[C.DECISIONS].docs.append(decision_doc(coins["btc_oid"], k, "BUY"))
    db[C.DECISIONS].docs.append(decision_doc(coins["btc_oid"], 11, "SELL"))
    db[C.DECISIONS].docs.append(decision_doc(coins["btc_oid"], 12, "HOLD"))
    db[C.DECISIONS].docs.append(decision_doc(coins["btc_oid"], 13, None))      # no decision value -> excluded
    svc = _service(history_for())
    report = await svc.refresh_outcomes(_now())
    assert report["decisions"]["matched"] == 12 and all(r["horizon"] == "24h" for r in db[C.PREDICTION_RESULTS].docs)
    data = await svc.decisions()
    assert data["decision_counts"] == {"BUY": 10, "SELL": 1, "HOLD": 1}
    cells = {(c["decision"], c["horizon"]): c for c in data["metrics"]["by_decision_horizon"]}
    assert cells[("BUY", "24h")]["status"] == "insufficient_data" and cells[("BUY", "24h")]["directional_agreement"] is None
    assert cells[("HOLD", "24h")]["directional_agreement"] is None
    assert any("HOLD makes no directional claim" in m for m in data["limitations"])
    # SELL followed by a RISE is NOT a success; the raw forward return is recorded for it
    sell = [r for r in db[C.PREDICTION_RESULTS].docs if r.get("decision") == "SELL"][0]
    assert sell["forward_return"] > 0 and sell["reference_source"] == "candle_close"


async def test_start_refresh_runs_in_background_and_reports_state(db, coins):
    import asyncio
    _seed_predictions(db, coins, 3)
    svc = _service(history_for())
    started = await svc.start_refresh()
    assert started["accepted"] is True and started["running"] is True
    again = await svc.start_refresh()
    assert again["accepted"] is False
    for _ in range(100):
        if not EvaluationService.refresh_state()["running"]:
            break
        await asyncio.sleep(0.02)
    state = EvaluationService.refresh_state()
    assert state["running"] is False and state["last_error"] is None and state["last_report"]["predictions"]["matched"] == 3
