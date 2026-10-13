"""Phase 16 API tests — real routes, services and repositories over an in-memory database
(see fake_mongo.py), with REAL JWTs for two different users."""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.core.security import create_access_token, verify_password
from app.database.collections import CollectionName as C
from tests.user_features_fixtures import PASSWORD, client, coins, db, user_a, user_b  # noqa: F401

API = "/api/v1"
FUTURE = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


# ----------------------------------------------------------------------------- auth on every endpoint
PROTECTED = [
    ("get", "/watchlist"), ("post", "/watchlist"), ("get", f"/watchlist/{'a' * 24}"), ("delete", f"/watchlist/{'a' * 24}"),
    ("get", "/portfolio"), ("post", "/portfolio"), ("get", "/portfolio/transactions"),
    ("put", f"/portfolio/{'a' * 24}"), ("delete", f"/portfolio/{'a' * 24}"),
    ("get", "/history"), ("post", "/history"), ("get", f"/history/{'a' * 24}"), ("delete", f"/history/{'a' * 24}"),
    ("get", "/alerts"), ("post", "/alerts"), ("post", "/alerts/check"), ("put", f"/alerts/{'a' * 24}"), ("delete", f"/alerts/{'a' * 24}"),
    ("get", "/profile"), ("put", "/profile"), ("post", "/profile/password"), ("get", "/settings"), ("put", "/settings"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_user_endpoint_requires_a_token(client, method, path):
    assert getattr(client, method)(API + path).status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED[:6])
def test_invalid_and_expired_tokens_are_rejected(client, user_a, method, path):
    bad = getattr(client, method)(API + path, headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "AUTH_INVALID_TOKEN"
    expired = create_access_token(subject=str(user_a[0]["_id"]), expires_minutes=-1)
    r = getattr(client, method)(API + path, headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


# ----------------------------------------------------------------------------- watchlist
def test_watchlist_add_list_status_remove(client, user_a, coins):
    _, h = user_a
    assert client.get(f"{API}/watchlist", headers=h).json()["items"] == []
    assert client.get(f"{API}/watchlist/{coins['btc']}", headers=h).json()["in_watchlist"] is False

    r = client.post(f"{API}/watchlist", json={"coin_id": coins["btc"]}, headers=h)
    assert r.status_code == 201 and r.json()["in_watchlist"] is True

    body = client.get(f"{API}/watchlist", headers=h).json()
    assert body["total"] == 1
    item = body["items"][0]
    # market data is joined at read time from market_data (real stored values), not stored on the watchlist
    assert item["symbol"] == "BTC" and item["price_usd"] == 100.0 and item["percent_change_24h"] == 2.5
    assert client.get(f"{API}/watchlist/{coins['btc']}", headers=h).json()["in_watchlist"] is True

    assert client.delete(f"{API}/watchlist/{coins['btc']}", headers=h).status_code == 200
    assert client.get(f"{API}/watchlist", headers=h).json()["total"] == 0


def test_watchlist_coin_without_market_data_shows_nulls_not_fake_prices(client, user_a, coins):
    _, h = user_a
    client.post(f"{API}/watchlist", json={"coin_id": coins["eth"]}, headers=h)
    item = client.get(f"{API}/watchlist", headers=h).json()["items"][0]
    assert item["price_usd"] is None and item["market_cap_usd"] is None


def test_watchlist_duplicate_unknown_and_invalid_ids(client, user_a, coins):
    _, h = user_a
    client.post(f"{API}/watchlist", json={"coin_id": coins["btc"]}, headers=h)
    dup = client.post(f"{API}/watchlist", json={"coin_id": coins["btc"]}, headers=h)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "WATCHLIST_ALREADY_EXISTS"
    unknown = client.post(f"{API}/watchlist", json={"coin_id": str(ObjectId())}, headers=h)
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "COIN_NOT_FOUND"
    assert client.post(f"{API}/watchlist", json={"coin_id": "z" * 24}, headers=h).status_code == 400
    assert client.post(f"{API}/watchlist", json={"coin_id": "short"}, headers=h).status_code == 422
    assert client.get(f"{API}/watchlist/not-an-id", headers=h).status_code == 400
    assert client.delete(f"{API}/watchlist/{coins['eth']}", headers=h).status_code == 404


def test_watchlist_rejects_a_user_id_in_the_body(client, user_a, user_b, coins):
    r = client.post(f"{API}/watchlist", json={"coin_id": coins["btc"], "user_id": str(user_b[0]["_id"])}, headers=user_a[1])
    assert r.status_code == 422


def test_watchlist_user_isolation(client, user_a, user_b, coins, db):
    client.post(f"{API}/watchlist", json={"coin_id": coins["btc"]}, headers=user_a[1])
    # B sees nothing, and A's entry is not B's
    assert client.get(f"{API}/watchlist", headers=user_b[1]).json()["total"] == 0
    assert client.get(f"{API}/watchlist/{coins['btc']}", headers=user_b[1]).json()["in_watchlist"] is False
    # B cannot delete A's entry
    assert client.delete(f"{API}/watchlist/{coins['btc']}", headers=user_b[1]).status_code == 404
    assert client.get(f"{API}/watchlist", headers=user_a[1]).json()["total"] == 1
    # B can watch the same coin independently
    assert client.post(f"{API}/watchlist", json={"coin_id": coins["btc"]}, headers=user_b[1]).status_code == 201
    assert len(db[C.WATCHLISTS].docs) == 2


# ----------------------------------------------------------------------------- portfolio
def _add(client, h, coin, qty=2, price=50, **extra):
    return client.post(f"{API}/portfolio", json={"coin_id": coin, "quantity": qty, "price": price, **extra}, headers=h)


def test_portfolio_create_and_real_price_calculations(client, user_a, coins):
    _, h = user_a
    assert client.get(f"{API}/portfolio", headers=h).json()["holdings"] == []
    r = _add(client, h, coins["btc"], qty=2, price=50)
    assert r.status_code == 201
    holding = r.json()
    # BTC market price in the DB is 100.0:  value = 2 × 100, invested = 2 × 50, P/L = 100 (100%)
    assert holding["current_price"] == 100.0 and holding["current_value"] == 200.0
    assert holding["invested_value"] == 100.0 and holding["unrealized_pnl"] == 100.0 and holding["unrealized_pnl_pct"] == 100.0

    summary = client.get(f"{API}/portfolio", headers=h).json()["summary"]
    assert summary["total_current_value"] == 200.0 and summary["total_invested"] == 100.0
    assert summary["total_unrealized_pnl"] == 100.0 and summary["total_unrealized_pnl_pct"] == 100.0
    assert summary["is_partial"] is False


def test_portfolio_unpriced_holding_is_not_valued_at_a_guess(client, user_a, coins):
    _, h = user_a
    _add(client, h, coins["btc"], qty=1, price=80)
    _add(client, h, coins["eth"], qty=3, price=10)  # ETH has no market data
    body = client.get(f"{API}/portfolio", headers=h).json()
    eth = next(x for x in body["holdings"] if x["symbol"] == "ETH")
    assert eth["has_price"] is False and eth["current_value"] is None and eth["unrealized_pnl"] is None
    s = body["summary"]
    assert s["is_partial"] is True and s["unpriced_count"] == 1
    assert s["total_current_value"] == 100.0 and s["total_invested"] == 110.0 and s["priced_invested"] == 80.0
    assert s["total_unrealized_pnl"] == 20.0


def test_portfolio_zero_buy_price_has_no_percentage(client, user_a, coins):
    r = _add(client, user_a[1], coins["btc"], qty=1, price=0)
    assert r.status_code == 201 and r.json()["unrealized_pnl_pct"] is None


def test_portfolio_second_buy_merges_with_weighted_average_and_logs_transactions(client, user_a, coins):
    _, h = user_a
    _add(client, h, coins["btc"], qty=1, price=100)
    r = _add(client, h, coins["btc"], qty=3, price=200)
    assert r.json()["quantity"] == 4 and r.json()["average_buy_price"] == 175.0
    tx = client.get(f"{API}/portfolio/transactions", headers=h).json()
    assert tx["total"] == 2 and {t["transaction_type"] for t in tx["items"]} == {"buy"}


def test_portfolio_update_and_delete(client, user_a, coins):
    _, h = user_a
    _add(client, h, coins["btc"], qty=1, price=100)
    r = client.put(f"{API}/portfolio/{coins['btc']}", json={"quantity": 5, "average_buy_price": 60}, headers=h)
    assert r.status_code == 200 and r.json()["quantity"] == 5 and r.json()["average_buy_price"] == 60
    assert client.put(f"{API}/portfolio/{coins['eth']}", json={"quantity": 1}, headers=h).status_code == 404
    assert client.delete(f"{API}/portfolio/{coins['btc']}", headers=h).status_code == 200
    assert client.get(f"{API}/portfolio", headers=h).json()["holdings"] == []
    assert client.get(f"{API}/portfolio/transactions", headers=h).json()["total"] == 0
    assert client.delete(f"{API}/portfolio/{coins['btc']}", headers=h).status_code == 404


@pytest.mark.parametrize("body", [
    {"quantity": 0, "price": 1}, {"quantity": -1, "price": 1}, {"quantity": 1, "price": -5},
    {"quantity": "abc", "price": 1}, {"quantity": 1e30, "price": 1}, {"quantity": 1}, {"price": 1},
    {"quantity": 1, "price": 1, "bought_at": "2999-01-01T00:00:00Z"}, {"quantity": 1, "price": 1, "user_id": "x"},
])
def test_portfolio_rejects_invalid_input(client, user_a, coins, body):
    r = client.post(f"{API}/portfolio", json={"coin_id": coins["btc"], **body}, headers=user_a[1])
    assert r.status_code == 422


def test_portfolio_rejects_nan_and_invalid_updates(client, user_a, coins):
    _, h = user_a
    _add(client, h, coins["btc"])
    assert client.put(f"{API}/portfolio/{coins['btc']}", json={}, headers=h).status_code == 422
    assert client.put(f"{API}/portfolio/{coins['btc']}", json={"quantity": -2}, headers=h).status_code == 422
    assert client.put(f"{API}/portfolio/{coins['btc']}", json={"quantity": None}, headers=h).status_code == 422
    assert client.post(f"{API}/portfolio", content='{"coin_id": "%s", "quantity": NaN, "price": 1}' % coins["btc"],
                       headers={**h, "Content-Type": "application/json"}).status_code == 422
    assert _add(client, h, str(ObjectId())).status_code == 404
    assert client.put(f"{API}/portfolio/bad-id", json={"quantity": 1}, headers=h).status_code == 400


def test_portfolio_user_isolation(client, user_a, user_b, coins):
    _add(client, user_a[1], coins["btc"], qty=2, price=50)
    assert client.get(f"{API}/portfolio", headers=user_b[1]).json()["holdings"] == []
    assert client.get(f"{API}/portfolio/transactions", headers=user_b[1]).json()["total"] == 0
    assert client.put(f"{API}/portfolio/{coins['btc']}", json={"quantity": 99}, headers=user_b[1]).status_code == 404
    assert client.delete(f"{API}/portfolio/{coins['btc']}", headers=user_b[1]).status_code == 404
    a = client.get(f"{API}/portfolio", headers=user_a[1]).json()["holdings"][0]
    assert a["quantity"] == 2  # untouched by B's attempts


# ----------------------------------------------------------------------------- history
def _decision(db, coin_oid, decision="BUY", risk="LOW"):
    db[C.DECISIONS].docs.append({"_id": ObjectId(), "coin_id": coin_oid, "decision": decision, "risk_level": risk,
                                 "risk_score": 30.0, "generated_at": datetime.now(timezone.utc)})


def test_history_records_server_side_outcome_and_lists_newest_first(client, user_a, coins, db):
    _, h = user_a
    _decision(db, coins["btc_oid"])
    r = client.post(f"{API}/history", json={"coin_id": coins["btc"], "analysis_type": "risk_decision"}, headers=h)
    assert r.status_code == 201
    e = r.json()
    assert e["decision"] == "BUY" and e["risk_level"] == "LOW" and e["status"] == "COMPLETED" and e["symbol"] == "BTC"

    # nothing stored for ETH => UNAVAILABLE, with no invented decision
    u = client.post(f"{API}/history", json={"coin_id": coins["eth"], "analysis_type": "risk_decision"}, headers=h).json()
    assert u["status"] == "UNAVAILABLE" and u["decision"] is None

    items = client.get(f"{API}/history", headers=h).json()["items"]
    assert [i["symbol"] for i in items] == ["ETH", "BTC"]


def test_history_identical_recent_entry_is_not_duplicated(client, user_a, coins):
    _, h = user_a
    body = {"coin_id": coins["btc"], "analysis_type": "coin_analysis"}
    assert client.post(f"{API}/history", json=body, headers=h).status_code == 201
    assert client.post(f"{API}/history", json=body, headers=h).status_code == 200
    assert client.get(f"{API}/history", headers=h).json()["total"] == 1


def test_history_pagination_filter_get_delete(client, user_a, coins):
    _, h = user_a
    for t in ("coin_analysis", "prediction", "risk_decision", "ai_analysis"):
        client.post(f"{API}/history", json={"coin_id": coins["btc"], "analysis_type": t}, headers=h)
    client.post(f"{API}/history", json={"coin_id": coins["eth"], "analysis_type": "coin_analysis"}, headers=h)

    page1 = client.get(f"{API}/history?limit=2&page=1", headers=h).json()
    page3 = client.get(f"{API}/history?limit=2&page=3", headers=h).json()
    assert page1["total"] == 5 and page1["pages"] == 3 and len(page1["items"]) == 2 and len(page3["items"]) == 1
    assert client.get(f"{API}/history?coin_id={coins['eth']}", headers=h).json()["total"] == 1
    assert client.get(f"{API}/history?analysis_type=prediction", headers=h).json()["total"] == 1
    assert client.get(f"{API}/history?analysis_type=bogus", headers=h).status_code == 400
    assert client.get(f"{API}/history?limit=0", headers=h).status_code == 422

    entry_id = page1["items"][0]["id"]
    assert client.get(f"{API}/history/{entry_id}", headers=h).json()["id"] == entry_id
    assert client.delete(f"{API}/history/{entry_id}", headers=h).status_code == 200
    assert client.get(f"{API}/history/{entry_id}", headers=h).status_code == 404
    assert client.get(f"{API}/history/bad", headers=h).status_code == 400
    assert client.post(f"{API}/history", json={"coin_id": coins["btc"], "analysis_type": "nope"}, headers=h).status_code == 422


def test_history_user_isolation(client, user_a, user_b, coins):
    r = client.post(f"{API}/history", json={"coin_id": coins["btc"], "analysis_type": "coin_analysis"}, headers=user_a[1])
    entry_id = r.json()["id"]
    assert client.get(f"{API}/history", headers=user_b[1]).json()["total"] == 0
    assert client.get(f"{API}/history/{entry_id}", headers=user_b[1]).status_code == 404
    assert client.delete(f"{API}/history/{entry_id}", headers=user_b[1]).status_code == 404
    assert client.get(f"{API}/history/{entry_id}", headers=user_a[1]).status_code == 200


# ----------------------------------------------------------------------------- alerts
def _alert(client, h, coin, condition="ABOVE", target=120000, **extra):
    return client.post(f"{API}/alerts", json={"coin_id": coin, "condition": condition, "target_price": target, **extra}, headers=h)


def test_alert_create_list_update_delete(client, user_a, coins):
    _, h = user_a
    assert client.get(f"{API}/alerts", headers=h).json()["items"] == []
    r = _alert(client, h, coins["btc"], expires_at=FUTURE)
    assert r.status_code == 201
    a = r.json()
    assert a["status"] == "ACTIVE" and a["condition"] == "ABOVE" and a["target_price"] == 120000 and a["triggered_at"] is None
    assert a["current_price"] == 100.0  # context only, read from stored market data

    u = client.put(f"{API}/alerts/{a['id']}", json={"target_price": 90, "condition": "BELOW"}, headers=h).json()
    assert u["target_price"] == 90 and u["condition"] == "BELOW"
    assert client.put(f"{API}/alerts/{a['id']}", json={"status": "DISABLED"}, headers=h).json()["status"] == "DISABLED"
    assert client.get(f"{API}/alerts?status=DISABLED", headers=h).json()["total"] == 1
    assert client.get(f"{API}/alerts?status=ACTIVE", headers=h).json()["total"] == 0
    assert client.delete(f"{API}/alerts/{a['id']}", headers=h).status_code == 200
    assert client.delete(f"{API}/alerts/{a['id']}", headers=h).status_code == 404


@pytest.mark.parametrize("body", [
    {"condition": "SIDEWAYS", "target_price": 10}, {"condition": "ABOVE", "target_price": 0},
    {"condition": "ABOVE", "target_price": -5}, {"condition": "ABOVE", "target_price": "x"},
    {"condition": "ABOVE", "target_price": 1e30}, {"condition": "ABOVE"}, {"target_price": 10},
    {"condition": "ABOVE", "target_price": 10, "expires_at": "2001-01-01T00:00:00Z"},
    {"condition": "ABOVE", "target_price": 10, "user_id": "x"}, {"condition": "ABOVE", "target_price": 10, "status": "TRIGGERED"},
])
def test_alert_validation(client, user_a, coins, body):
    r = client.post(f"{API}/alerts", json={"coin_id": coins["btc"], **body}, headers=user_a[1])
    assert r.status_code == 422


def test_alert_unknown_coin_invalid_ids_and_manual_trigger_forbidden(client, user_a, coins):
    _, h = user_a
    assert _alert(client, h, str(ObjectId())).status_code == 404
    assert client.put(f"{API}/alerts/bad", json={"target_price": 1}, headers=h).status_code == 400
    a = _alert(client, h, coins["btc"]).json()
    assert client.put(f"{API}/alerts/{a['id']}", json={"status": "TRIGGERED"}, headers=h).status_code == 422
    assert client.put(f"{API}/alerts/{a['id']}", json={}, headers=h).status_code == 422


def test_alert_user_isolation(client, user_a, user_b, coins):
    a = _alert(client, user_a[1], coins["btc"]).json()
    assert client.get(f"{API}/alerts", headers=user_b[1]).json()["total"] == 0
    assert client.put(f"{API}/alerts/{a['id']}", json={"target_price": 1}, headers=user_b[1]).status_code == 404
    assert client.delete(f"{API}/alerts/{a['id']}", headers=user_b[1]).status_code == 404
    assert client.get(f"{API}/alerts", headers=user_a[1]).json()["items"][0]["target_price"] == 120000


def test_alert_check_triggers_only_on_a_real_fresh_price_and_only_for_the_caller(client, user_a, user_b, coins, db):
    hit = _alert(client, user_a[1], coins["btc"], "BELOW", 150).json()       # price 100 < 150  -> triggers
    miss = _alert(client, user_a[1], coins["btc"], "ABOVE", 150).json()      # price 100 > 150? no
    nopx = _alert(client, user_a[1], coins["eth"], "ABOVE", 1).json()        # ETH has no price -> skipped
    others = _alert(client, user_b[1], coins["btc"], "BELOW", 150).json()    # B's alert, not A's to evaluate

    r = client.post(f"{API}/alerts/check", headers=user_a[1]).json()
    assert r["triggered"] == 1 and r["triggered_alert_ids"] == [hit["id"]]
    assert r["checked"] == 2 and r["skipped_no_price"] == 1 and r["skipped_stale"] == 0

    by_id = {a["id"]: a for a in client.get(f"{API}/alerts", headers=user_a[1]).json()["items"]}
    assert by_id[hit["id"]]["status"] == "TRIGGERED" and by_id[hit["id"]]["triggered_price"] == 100.0
    assert by_id[miss["id"]]["status"] == "ACTIVE" and by_id[miss["id"]]["last_checked_at"] is not None
    assert by_id[nopx["id"]]["status"] == "ACTIVE" and by_id[nopx["id"]]["last_checked_at"] is None
    assert client.get(f"{API}/alerts", headers=user_b[1]).json()["items"][0]["status"] == "ACTIVE"
    # a second check never re-triggers
    assert client.post(f"{API}/alerts/check", headers=user_a[1]).json()["triggered"] == 0


def test_alert_check_never_fires_on_a_stale_price(client, user_a, coins, db):
    db[C.MARKET_DATA].docs[0]["updated_at"] = datetime.now(timezone.utc) - timedelta(days=2)
    _alert(client, user_a[1], coins["btc"], "BELOW", 150)
    r = client.post(f"{API}/alerts/check", headers=user_a[1]).json()
    assert r["triggered"] == 0 and r["skipped_stale"] == 1


def test_alert_check_expires_past_due_alerts_and_rearm_requires_a_future_expiry(client, user_a, coins, db):
    a = _alert(client, user_a[1], coins["btc"], "ABOVE", 999, expires_at=FUTURE).json()
    db[C.ALERTS].docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    r = client.post(f"{API}/alerts/check", headers=user_a[1]).json()
    assert r["expired"] == 1 and r["triggered"] == 0
    assert client.get(f"{API}/alerts", headers=user_a[1]).json()["items"][0]["status"] == "EXPIRED"
    assert client.put(f"{API}/alerts/{a['id']}", json={"status": "ACTIVE"}, headers=user_a[1]).status_code == 422
    ok = client.put(f"{API}/alerts/{a['id']}", json={"status": "ACTIVE", "expires_at": None}, headers=user_a[1])
    assert ok.status_code == 200 and ok.json()["status"] == "ACTIVE"


def test_alert_condition_boundaries():
    from app.services.alert_service import condition_met
    assert condition_met("ABOVE", 101, 100) and not condition_met("ABOVE", 100, 100)
    assert condition_met("BELOW", 99, 100) and not condition_met("BELOW", 100, 100)
    assert not condition_met("UNKNOWN", 1, 1)


# ----------------------------------------------------------------------------- profile / password / settings
def test_profile_get_and_update_name(client, user_a):
    _, h = user_a
    p = client.get(f"{API}/profile", headers=h).json()
    assert p["name"] == "Alice" and p["email"] == "alice@example.com" and "password_hash" not in p and "created_at" in p
    r = client.put(f"{API}/profile", json={"name": "  Alicia  "}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "Alicia"
    assert client.get(f"{API}/auth/me", headers=h).json()["name"] == "Alicia"
    assert client.put(f"{API}/profile", json={"name": "   "}, headers=h).status_code == 422
    assert client.put(f"{API}/profile", json={"name": "x", "email": "new@example.com"}, headers=h).status_code == 422  # email not editable


def test_change_password_success_stores_an_argon2_hash(client, user_a, db):
    doc, h = user_a
    r = client.post(f"{API}/profile/password", headers=h,
                    json={"current_password": PASSWORD, "new_password": "brand-new-pass-9", "confirm_new_password": "brand-new-pass-9"})
    assert r.status_code == 200
    stored = db[C.USERS].docs[0]["password_hash"]
    assert stored.startswith("$argon2") and "brand-new-pass-9" not in stored
    assert verify_password("brand-new-pass-9", stored) and not verify_password(PASSWORD, stored)


@pytest.mark.parametrize("current,new,confirm,status,code", [
    ("wrong-password", "brand-new-pass-9", "brand-new-pass-9", 400, "CURRENT_PASSWORD_INCORRECT"),
    (PASSWORD, "brand-new-pass-9", "different-pass-99", 422, None),
    (PASSWORD, "short", "short", 422, None),
    (PASSWORD, PASSWORD, PASSWORD, 422, None),
    ("", "brand-new-pass-9", "brand-new-pass-9", 422, None),
])
def test_change_password_failures_leave_the_hash_untouched(client, user_a, db, current, new, confirm, status, code):
    before = db[C.USERS].docs[0]["password_hash"]
    r = client.post(f"{API}/profile/password", headers=user_a[1],
                    json={"current_password": current, "new_password": new, "confirm_new_password": confirm})
    assert r.status_code == status
    if code:
        assert r.json()["error"]["code"] == code
    assert db[C.USERS].docs[0]["password_hash"] == before


def test_change_password_only_affects_the_caller(client, user_a, user_b, db):
    b_hash = db[C.USERS].docs[1]["password_hash"]
    client.post(f"{API}/profile/password", headers=user_a[1],
                json={"current_password": PASSWORD, "new_password": "brand-new-pass-9", "confirm_new_password": "brand-new-pass-9"})
    assert db[C.USERS].docs[1]["password_hash"] == b_hash


def test_settings_defaults_update_and_persist_per_user(client, user_a, user_b):
    _, a = user_a
    assert client.get(f"{API}/settings", headers=a).json() == {"theme": None, "notifications": {"price_alerts": True}}
    r = client.put(f"{API}/settings", json={"theme": "dark", "notifications": {"price_alerts": False}}, headers=a)
    assert r.json() == {"theme": "dark", "notifications": {"price_alerts": False}}
    # persisted: a fresh read returns it; another user is unaffected
    assert client.get(f"{API}/settings", headers=a).json()["theme"] == "dark"
    assert client.get(f"{API}/settings", headers=user_b[1]).json()["theme"] is None
    # partial update keeps the rest; null resets the theme
    assert client.put(f"{API}/settings", json={"theme": "light"}, headers=a).json()["notifications"]["price_alerts"] is False
    assert client.put(f"{API}/settings", json={"theme": None}, headers=a).json()["theme"] is None


@pytest.mark.parametrize("body", [{}, {"theme": "purple"}, {"currency": "EUR"}, {"notifications": None}, {"notifications": {"sms": True}}])
def test_settings_validation(client, user_a, body):
    assert client.put(f"{API}/settings", json=body, headers=user_a[1]).status_code == 422


# ----------------------------------------------------------------------------- non-finite JSON numbers -> 422
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["quantity", "price"])
def test_portfolio_non_finite_numbers_return_422_not_a_server_error(client, user_a, coins, field, literal):
    body = {"quantity": "1", "price": "1"}
    body[field] = literal
    raw = '{"coin_id": "%s", "quantity": %s, "price": %s}' % (coins["btc"], body["quantity"], body["price"])
    r = client.post(f"{API}/portfolio", content=raw, headers={**user_a[1], "Content-Type": "application/json"})
    assert r.status_code == 422
    detail = r.json()["detail"]  # the response itself is strict, parseable JSON
    assert isinstance(detail, list) and detail and detail[0]["loc"][-1] == field


def test_alert_and_holding_update_non_finite_numbers_return_422(client, user_a, coins):
    h = {**user_a[1], "Content-Type": "application/json"}
    r = client.post(f"{API}/alerts", content='{"coin_id": "%s", "condition": "ABOVE", "target_price": NaN}' % coins["btc"], headers=h)
    assert r.status_code == 422
    client.post(f"{API}/portfolio", json={"coin_id": coins["btc"], "quantity": 1, "price": 1}, headers=user_a[1])
    r = client.put(f"{API}/portfolio/{coins['btc']}", content='{"quantity": Infinity}', headers=h)
    assert r.status_code == 422


def test_valid_portfolio_input_still_works_after_the_handler_change(client, user_a, coins):
    assert _add(client, user_a[1], coins["btc"], qty=1, price=10).status_code == 201


def test_ordinary_validation_errors_keep_the_default_422_shape(client, user_a, coins):
    r = client.post(f"{API}/portfolio", json={"coin_id": coins["btc"], "quantity": -1, "price": 1}, headers=user_a[1])
    assert r.status_code == 422
    first = r.json()["detail"][0]
    assert set(first) >= {"type", "loc", "msg"} and first["loc"][-1] == "quantity"
