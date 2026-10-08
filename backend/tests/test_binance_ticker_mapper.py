"""Unit tests for Binance 24h-ticker normalization."""

from app.providers.binance.mapper import map_exchange_info, map_ticker_24hr

EXCHANGE_INFO = {
    "symbols": [
        {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
    ]
}

TICKER_ROW = {
    "symbol": "BTCUSDT",
    "lastPrice": "65000.12",
    "priceChangePercent": "1.85",
    "highPrice": "66000.00",
    "lowPrice": "64000.00",
    "volume": "1234.5",
    "quoteVolume": "80000000.0",
}


def test_map_ticker_parses_binance_string_numerics():
    tickers = map_ticker_24hr([TICKER_ROW])
    assert len(tickers) == 1
    ticker = tickers[0]
    assert ticker.last_price == 65000.12
    assert ticker.price_change_percent_24h == 1.85
    assert ticker.high_24h == 66000.00
    assert ticker.low_24h == 64000.00
    assert ticker.volume_24h == 1234.5
    assert ticker.quote_volume_24h == 80000000.0


def test_map_ticker_fills_base_quote_from_symbol_index():
    index = {pair.symbol: pair for pair in map_exchange_info(EXCHANGE_INFO)}
    ticker = map_ticker_24hr([TICKER_ROW], index)[0]
    assert ticker.base_asset == "BTC"
    assert ticker.quote_asset == "USDT"


def test_map_ticker_leaves_base_quote_none_without_index():
    """Never guessed by string-splitting the symbol — that's ambiguous."""
    ticker = map_ticker_24hr([TICKER_ROW])[0]
    assert ticker.base_asset is None
    assert ticker.quote_asset is None


def test_map_ticker_unparseable_number_becomes_none_not_zero():
    """A zero price would be indistinguishable from a real zero."""
    row = {**TICKER_ROW, "lastPrice": "not-a-number", "volume": None}
    ticker = map_ticker_24hr([row])[0]
    assert ticker.last_price is None
    assert ticker.volume_24h is None


def test_map_ticker_drops_rows_without_a_symbol():
    assert map_ticker_24hr([{"lastPrice": "1.0"}]) == []


def test_map_ticker_missing_fields_are_none():
    ticker = map_ticker_24hr([{"symbol": "ETHUSDT"}])[0]
    assert ticker.symbol == "ETHUSDT"
    assert ticker.last_price is None
    assert ticker.high_24h is None
    assert ticker.quote_volume_24h is None


def test_map_ticker_empty_input():
    assert map_ticker_24hr([]) == []
