"""Shared fixtures for the Phase 16 tests: an in-memory database, two real users with real JWTs, two coins."""

from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.database.collections import CollectionName as C
from app.main import app
from tests.fake_mongo import FakeCollection

PASSWORD = "correct-horse-1"
NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


@pytest.fixture
def db(monkeypatch):
    collections = {
        C.USERS: FakeCollection(),
        C.COINS: FakeCollection(),
        C.MARKET_DATA: FakeCollection(),
        C.WATCHLISTS: FakeCollection(unique=[("user_id", "coin_id")]),
        C.PORTFOLIOS: FakeCollection(unique=[("user_id", "coin_id")]),
        C.PORTFOLIO_TRANSACTIONS: FakeCollection(),
        C.ANALYSIS_HISTORY: FakeCollection(),
        C.ALERTS: FakeCollection(),
        C.DECISIONS: FakeCollection(),
        C.PREDICTIONS: FakeCollection(),
        C.AI_ANALYSIS: FakeCollection(),
    }
    monkeypatch.setattr("app.repositories.base.get_collection", lambda name: collections[name])
    return collections


def _add_user(db, name, email):
    doc = {"_id": ObjectId(), "name": name, "email": email, "password_hash": hash_password(PASSWORD),
           "is_active": True, "role": "user", "created_at": NOW(), "updated_at": NOW()}
    db[C.USERS].docs.append(doc)
    return doc, {"Authorization": f"Bearer {create_access_token(subject=str(doc['_id']))}"}


@pytest.fixture
def user_a(db):
    return _add_user(db, "Alice", "alice@example.com")


@pytest.fixture
def user_b(db):
    return _add_user(db, "Bob", "bob@example.com")


@pytest.fixture
def coins(db):
    """BTC (priced, fresh) and ETH (no market data at all)."""
    btc, eth = ObjectId(), ObjectId()
    for oid, name, sym in ((btc, "Bitcoin", "BTC"), (eth, "Ethereum", "ETH")):
        db[C.COINS].docs.append({"_id": oid, "name": name, "symbol": sym, "logo_url": None, "market_cap_rank": 1,
                                 "is_active": True, "created_at": NOW(), "updated_at": NOW()})
    db[C.MARKET_DATA].docs.append({"coin_id": btc, "price_usd": 100.0, "percent_change_24h": 2.5, "market_cap_usd": 1e9,
                                   "volume_24h_usd": 1e6, "updated_at": NOW(), "last_updated": NOW()})
    return {"btc": str(btc), "eth": str(eth), "btc_oid": btc, "eth_oid": eth}


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c
