"""Phase 17 API tests — real routes/services/repositories over the in-memory database with REAL JWTs.

Covers authentication, parameter validation, user isolation of backtest runs, background execution of a run on
explicit test candles, and the "insufficient data" / empty states of the accuracy endpoints.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.core.security import create_access_token
from app.database.collections import CollectionName as C
from app.schemas.backtesting import BacktestRunCreate
from app.services import backtest_service
from app.services.backtest_service import BacktestService
from tests.backtesting_fixtures import (  # noqa: F401
    BASE, FakeHistory, client, coins, db, decision_doc, history_for, rising_closes, user_a, user_b,
)

API = "/api/v1/backtesting"


def _body(coins, **kw):
    body = {
        "coin_ids": [coins["btc"]], "start": (BASE + timedelta(hours=1)).isoformat(), "end": (BASE + timedelta(days=10)).isoformat(),
        "starting_capital": 10_000, "bar_interval": "1h", "position_size": 0.5, "max_allocation_pct": 1.0,
        "fee_rate": 0.001, "slippage_rate": 0.0005,
    }
    body.update(kw)
    return body


# ----------------------------------------------------------------------------- authentication
PROTECTED = [("get", "/config"), ("get", "/accuracy"), ("post", "/accuracy/refresh"), ("get", "/accuracy/refresh"),
             ("get", f"/accuracy/{'a' * 24}"), ("get", "/decisions"), ("post", "/runs"), ("get", "/runs"),
             ("get", "/runs/abc"), ("get", "/runs/abc/trades")]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_backtesting_endpoint_requires_a_token(client, method, path):
    assert getattr(client, method)(API + path).status_code == 401


def test_expired_token_rejected(client, user_a):
    token = create_access_token(subject=str(user_a[0]["_id"]), expires_minutes=-1)
    r = client.get(API + "/accuracy", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ----------------------------------------------------------------------------- config + accuracy (read-only)
def test_config_exposes_versions_defaults_and_limits(client, user_a):
    r = client.get(API + "/config", headers=user_a[1])
    assert r.status_code == 200
    j = r.json()
    assert j["strategy"] == "phase14_decisions" and j["defaults"]["fee_rate"] > 0 and j["defaults"]["slippage_rate"] > 0
    assert j["limits"]["max_coins"] >= 1 and "24h" in j["horizons"] and j["disclaimer"]


def test_accuracy_with_no_stored_predictions_is_an_honest_empty_state(client, user_a):
    r = client.get(API + "/accuracy", headers=user_a[1])
    assert r.status_code == 200
    j = r.json()
    assert j["overall"]["status"] == "no_data" and j["overall"]["mae"] is None and j["overall"]["directional_accuracy"] is None
    assert j["coverage"]["total_predictions"] == 0 and j["limitations"]


def _seed_results(db, coin_oid, n=40, horizon="24h", hit=True):
    t = BASE
    for i in range(n):
        db[C.PREDICTION_RESULTS].docs.append({
            "_id": ObjectId(), "record_type": "prediction", "source_id": ObjectId(), "coin_id": coin_oid, "symbol": "BTC",
            "horizon": horizon, "model": "xgboost", "model_version": "1", "feature_version": "f1", "status": "matched",
            "direction": "up" if hit else "down", "predicted_return": 0.01, "actual_return": 0.03, "actual_price": 103.0,
            "reference_price": 100.0, "reference_time": t + timedelta(hours=i), "target_time": t + timedelta(hours=i + 24),
            "generated_at": t + timedelta(hours=i), "evaluated_at": t + timedelta(days=5), "return_lower": -0.05, "return_upper": 0.05,
            "nominal_coverage": 0.8, "methodology_version": "1.0.0",
        })


def test_accuracy_values_come_from_stored_results(client, user_a, db, coins):
    _seed_results(db, coins["btc_oid"], 40)
    j = client.get(API + "/accuracy", headers=user_a[1]).json()
    o = j["overall"]
    assert o["status"] == "ok" and o["sample_size"] == 40 and o["directional_accuracy"] == 1.0
    assert o["mae"] == pytest.approx(0.02) and o["rmse"] == pytest.approx(0.02) and o["range_coverage"] == 1.0
    assert j["by_horizon"][0]["horizon"] == "24h" and j["options"]["horizons"] == ["24h"]
    one = client.get(f"{API}/accuracy/{coins['btc']}?horizon=24h", headers=user_a[1]).json()
    assert one["coin"]["symbol"] == "BTC" and one["overall"]["sample_size"] == 40
    empty = client.get(f"{API}/accuracy?horizon=7d", headers=user_a[1]).json()
    assert empty["overall"]["status"] == "no_data" and empty["overall"]["mae"] is None


def test_accuracy_parameter_validation(client, user_a, coins):
    h = user_a[1]
    assert client.get(API + "/accuracy?horizon=2h", headers=h).status_code == 422
    assert client.get(API + "/accuracy?coin_id=short", headers=h).status_code == 422
    assert client.get(f"{API}/accuracy/{'f' * 24}", headers=h).status_code == 404
    assert client.get(f"{API}/accuracy/not-an-object-id", headers=h).status_code == 400
    assert client.get(API + "/decisions?horizon=1h", headers=h).status_code == 422


def test_decision_evaluation_empty_state(client, user_a):
    j = client.get(API + "/decisions", headers=user_a[1]).json()
    assert j["metrics"]["evaluated_decisions"] == 0 and j["total_decisions_stored"] == 0 and j["limitations"]


# ----------------------------------------------------------------------------- run validation
@pytest.mark.parametrize("override,status", [
    ({"starting_capital": 0}, 422), ({"starting_capital": -10}, 422), ({"fee_rate": -0.001}, 422), ({"fee_rate": 0.5}, 422),
    ({"slippage_rate": -1}, 422), ({"max_allocation_pct": 0}, 422), ({"max_allocation_pct": 1.5}, 422),
    ({"position_size": 0}, 422), ({"position_size": 1.5}, 422), ({"sizing_mode": "kelly"}, 422), ({"bar_interval": "5m"}, 422),
    ({"coin_ids": []}, 422), ({"user_id": "someone-else"}, 422), ({"owner": "x"}, 422),
    ({"start": "2026-01-02T00:00:00Z", "end": "2026-01-01T00:00:00Z"}, 422),
    ({"end": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()}, 422),
    ({"start": (BASE - timedelta(days=400)).isoformat()}, 422),
    ({"coin_ids": ["nothex"]}, 400),
    ({"coin_ids": ["a" * 24]}, 404),
])
def test_invalid_backtest_configuration_is_rejected(client, user_a, coins, override, status):
    r = client.post(API + "/runs", json=_body(coins, **override), headers=user_a[1])
    assert r.status_code == status, r.text


def test_duplicate_coins_and_too_many_bars_rejected(client, user_a, coins):
    assert client.post(API + "/runs", json=_body(coins, coin_ids=[coins["btc"], coins["btc"]]), headers=user_a[1]).status_code == 422
    r = client.post(API + "/runs", json=_body(coins, start=(BASE - timedelta(days=300)).isoformat(), end=(BASE + timedelta(days=19)).isoformat()), headers=user_a[1])
    assert r.status_code == 422 and r.json()["error"]["code"] == "TOO_MANY_BARS"


# ----------------------------------------------------------------------------- user isolation (service created without a background task)
class _NoBackground(BacktestService):
    async def create_run(self, user_id, payload, *, run_in_background=True):
        return await super().create_run(user_id, payload, run_in_background=False)


def test_runs_are_isolated_per_authenticated_user(client, user_a, user_b, coins, monkeypatch):
    monkeypatch.setattr("app.api.v1.backtesting._backtests", lambda: _NoBackground(history=history_for()))
    created = client.post(API + "/runs", json=_body(coins), headers=user_a[1])
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]
    assert created.json()["status"] == "queued" and created.json()["result_status"] is None

    assert client.get(f"{API}/runs/{run_id}", headers=user_a[1]).status_code == 200
    # another user gets the same 404 as for a run that does not exist
    other = client.get(f"{API}/runs/{run_id}", headers=user_b[1])
    missing = client.get(f"{API}/runs/{'0' * 32}", headers=user_b[1])
    assert other.status_code == 404 and other.json() == missing.json()
    assert client.get(f"{API}/runs/{run_id}/trades", headers=user_b[1]).status_code == 404
    assert client.get(API + "/runs", headers=user_b[1]).json()["total"] == 0
    assert client.get(API + "/runs", headers=user_a[1]).json()["total"] == 1


def test_owner_comes_from_the_jwt_not_the_body(client, user_a, user_b, coins, db, monkeypatch):
    monkeypatch.setattr("app.api.v1.backtesting._backtests", lambda: _NoBackground(history=history_for()))
    run_id = client.post(API + "/runs", json=_body(coins), headers=user_a[1]).json()["run_id"]
    assert db[C.BACKTEST_RUNS].docs[0]["user_id"] == user_a[0]["_id"] and db[C.BACKTEST_RUNS].docs[0]["run_id"] == run_id


def test_concurrent_run_limit(client, user_a, coins, monkeypatch):
    monkeypatch.setattr("app.api.v1.backtesting._backtests", lambda: _NoBackground(history=history_for()))
    codes = [client.post(API + "/runs", json=_body(coins), headers=user_a[1]).status_code for _ in range(3)]
    assert codes == [202, 202, 429]


# ----------------------------------------------------------------------------- end-to-end run (async, explicit candles)
async def _run(db, coins, user_oid, history, **kw):
    svc = BacktestService(history=history)
    payload = BacktestRunCreate(**_body(coins, **kw))
    created = await svc.create_run(user_oid, payload)
    await asyncio.gather(*list(backtest_service._background))
    return svc, await svc.get_run(user_oid, created["run_id"])


async def test_backtest_runs_in_background_and_completes_with_real_inputs(db, coins):
    user = ObjectId()
    closes = rising_closes()
    db[C.DECISIONS].docs.extend([decision_doc(coins["btc_oid"], 5, "BUY"), decision_doc(coins["btc_oid"], 100, "SELL")])
    svc, run = await _run(db, coins, user, history_for(closes))
    assert run["status"] == "completed" and run["result_status"] == "ok"
    s = run["summary"]
    assert s["number_of_trades"] == 1 and s["total_fees"] > 0 and s["estimated_slippage"] > 0
    assert s["total_return"] > 0 and s["benchmark_return"] is not None and s["max_drawdown"] is not None
    assert run["assumptions"]["fee_rate"] == 0.001 and run["assumptions"]["execution"] == "next_bar_open"
    assert run["equity_curve"][0]["value"] == 10_000 and len(run["equity_curve"]) > 10 and run["benchmark_curve"]
    assert run["data_summary"][0]["decisions"] == 2 and run["disclaimer"]
    page = await svc.list_trades(user, run["run_id"], 1, 50)
    assert page["total"] == 2 and [t["side"] for t in page["items"]] == ["BUY", "SELL"]
    assert page["items"][0]["execution_time"] >= page["items"][0]["decision_time"]       # no look-ahead
    assert page["items"][0]["symbol"] == "BTC"


async def test_run_without_stored_decisions_is_flagged_insufficient_not_successful(db, coins):
    _, run = await _run(db, coins, ObjectId(), history_for())
    assert run["status"] == "completed" and run["result_status"] == "insufficient_data" and "No stored Phase 14 decisions" in run["reason"]
    assert run["summary"]["number_of_trades"] == 0


async def test_run_with_no_candles_is_insufficient_data(db, coins):
    _, run = await _run(db, coins, ObjectId(), FakeHistory({}))
    assert run["result_status"] == "insufficient_data" and run["summary"] is None and "No real historical candles" in run["reason"]


async def test_provider_failure_marks_the_run_failed(db, coins):
    _, run = await _run(db, coins, ObjectId(), FakeHistory({}, fail=True))
    assert run["status"] == "failed" and "provider error" in run["error"].lower()


async def test_unmapped_coin_is_excluded_with_an_explanation(db, coins):
    db[C.DECISIONS].docs.append(decision_doc(coins["btc_oid"], 5, "BUY"))
    _, run = await _run(db, coins, ObjectId(), history_for(), coin_ids=[coins["btc"], coins["eth"]])
    eth = [d for d in run["data_summary"] if d["symbol"] == "ETH"][0]
    assert eth["bars"] == 0 and "No Binance market mapping" in eth["note"] and any("excluded" in w for w in run["warnings"])


async def test_identical_inputs_give_identical_results(db, coins):
    db[C.DECISIONS].docs.extend([decision_doc(coins["btc_oid"], 5, "BUY"), decision_doc(coins["btc_oid"], 100, "SELL")])
    _, a = await _run(db, coins, ObjectId(), history_for())
    _, b = await _run(db, coins, ObjectId(), history_for())
    assert a["summary"] == b["summary"] and a["equity_curve"] == b["equity_curve"]


async def test_interrupted_runs_are_failed_on_startup_hygiene(db, coins):
    user = ObjectId()
    svc = BacktestService(history=history_for())
    created = await svc.create_run(user, BacktestRunCreate(**_body(coins)), run_in_background=False)
    db[C.BACKTEST_RUNS].docs[0]["updated_at"] = datetime.now(timezone.utc) - timedelta(hours=2)
    assert await svc.fail_interrupted_runs() == 1
    assert (await svc.get_run(user, created["run_id"]))["status"] == "failed"
