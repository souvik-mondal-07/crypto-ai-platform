"""
Unit tests for CoinGecko response normalization. No HTTP, no MongoDB —
pure data transformation against fixture JSON.
"""

from app.providers.coingecko.mapper import (
    map_coin_list_item,
    map_coin_market,
    map_global,
    map_trending,
)


def test_map_coin_list_item_basic():
    raw = {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}
    coin = map_coin_list_item(raw)
    assert coin.coingecko_id == "bitcoin"
    assert coin.symbol == "BTC"
    assert coin.name == "Bitcoin"
    assert coin.slug == "bitcoin"
    assert coin.logo_url is None
    assert coin.market_cap_rank is None


def test_map_coin_market_full_payload():
    raw = {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "image": "https://example.com/btc.png",
        "current_price": 65000.5,
        "market_cap": 1280000000000,
        "market_cap_rank": 1,
        "total_volume": 32000000000,
        "price_change_percentage_1h_in_currency": 0.12,
        "price_change_percentage_24h_in_currency": 1.85,
        "price_change_percentage_7d_in_currency": -2.3,
        "price_change_percentage_30d_in_currency": 10.1,
        "circulating_supply": 19700000,
        "total_supply": 21000000,
        "max_supply": 21000000,
        "ath": 73000,
        "atl": 67.81,
        "ath_change_percentage": -10.5,
        "atl_change_percentage": 95000.0,
        "ath_date": "2025-03-14T07:10:36.635Z",
        "atl_date": "2013-07-06T00:00:00.000Z",
        "price_change_24h": 1180.32,
        "price_change_percentage_1y_in_currency": 45.6,
        "fully_diluted_valuation": 1365000000000,
        "last_updated": "2026-01-01T00:00:00.000Z",
    }
    coin, market = map_coin_market(raw)

    assert coin.coingecko_id == "bitcoin"
    assert coin.symbol == "BTC"
    assert coin.logo_url == "https://example.com/btc.png"
    assert coin.market_cap_rank == 1

    assert market.price_usd == 65000.5
    assert market.market_cap_usd == 1280000000000
    assert market.percent_change_1h == 0.12
    assert market.percent_change_24h == 1.85
    assert market.percent_change_7d == -2.3
    assert market.percent_change_30d == 10.1
    assert market.circulating_supply == 19700000
    assert market.ath_usd == 73000
    assert market.last_updated is not None
    assert market.last_updated.year == 2026
    assert market.price_change_24h_usd == 1180.32
    assert market.percent_change_1y == 45.6
    assert market.fully_diluted_valuation_usd == 1365000000000
    assert market.ath_date is not None
    assert market.ath_date.year == 2025
    assert market.atl_date is not None
    assert market.atl_date.year == 2013


def test_map_coin_market_missing_fields_become_none_not_fake_values():
    """Missing provider fields must be None, never a fabricated default."""
    raw = {"id": "some-obscure-coin", "symbol": "obs", "name": "Obscure"}
    coin, market = map_coin_market(raw)

    assert coin.logo_url is None
    assert coin.market_cap_rank is None
    assert market.price_usd is None
    assert market.market_cap_usd is None
    assert market.percent_change_1h is None
    assert market.percent_change_7d is None
    assert market.percent_change_30d is None
    assert market.percent_change_1y is None
    assert market.price_change_24h_usd is None
    assert market.fully_diluted_valuation_usd is None
    assert market.ath_date is None
    assert market.atl_date is None
    assert market.ath_usd is None


def test_map_coin_market_falls_back_to_plain_24h_change_field():
    """
    If the `_in_currency` variant is absent (e.g. price_change_percentage
    param wasn't passed) but the plain 24h field is present, use it
    rather than reporting None for a field CoinGecko did provide.
    """
    raw = {
        "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
        "price_change_percentage_24h": 3.3,
    }
    _, market = map_coin_market(raw)
    assert market.percent_change_24h == 3.3


def test_map_global():
    raw = {
        "total_market_cap": {"usd": 2500000000000},
        "total_volume": {"usd": 100000000000},
        "market_cap_percentage": {"btc": 51.2, "eth": 17.4},
        "active_cryptocurrencies": 14000,
        "market_cap_change_percentage_24h_usd": 1.1,
        "updated_at": 1735689600,
    }
    global_market = map_global(raw)
    assert global_market.total_market_cap_usd == 2500000000000
    assert global_market.active_cryptocurrencies == 14000
    assert global_market.last_updated is not None


def test_map_global_missing_fields_are_none():
    global_market = map_global({})
    assert global_market.total_market_cap_usd is None
    assert global_market.active_cryptocurrencies is None
    assert global_market.last_updated is None


def test_map_trending_skips_entries_without_id():
    raw_items = [
        {"item": {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc", "market_cap_rank": 1, "score": 0}},
        {"item": {"name": "no id here"}},
    ]
    trending = map_trending(raw_items)
    assert len(trending) == 1
    assert trending[0].coingecko_id == "bitcoin"
    assert trending[0].symbol == "BTC"
