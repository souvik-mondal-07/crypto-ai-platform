"""Unit tests for Binance response normalization."""

from app.providers.binance.mapper import map_exchange_info


def test_map_exchange_info_filters_to_usdt_pairs_only():
    raw = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
            {"symbol": "ETHBTC", "baseAsset": "ETH", "quoteAsset": "BTC", "status": "TRADING"},
            {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
        ]
    }
    pairs = map_exchange_info(raw)
    symbols = {p.symbol for p in pairs}
    assert symbols == {"BTCUSDT", "ETHUSDT"}
    assert all(p.quote_asset == "USDT" for p in pairs)


def test_map_exchange_info_empty_symbols():
    assert map_exchange_info({"symbols": []}) == []
    assert map_exchange_info({}) == []
