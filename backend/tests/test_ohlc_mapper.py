"""
Unit tests for CoinGecko OHLC normalization. No HTTP, no MongoDB —
pure data transformation against fixture rows.
"""

from app.providers.coingecko.mapper import map_ohlc

# [timestamp_ms, open, high, low, close]
VALID_ROW = [1735689600000, 100.0, 110.0, 95.0, 105.0]


def test_map_ohlc_maps_a_valid_row():
    candles = map_ohlc([VALID_ROW])
    assert len(candles) == 1
    candle = candles[0]
    assert candle.open == 100.0
    assert candle.high == 110.0
    assert candle.low == 95.0
    assert candle.close == 105.0
    # This endpoint carries no volume — it must stay None, never 0 or invented.
    assert candle.volume is None
    assert candle.timestamp.year == 2025 or candle.timestamp.year == 2024


def test_map_ohlc_returns_utc_aware_timestamps():
    candles = map_ohlc([VALID_ROW])
    assert candles[0].timestamp.tzinfo is not None


def test_map_ohlc_drops_row_where_high_is_below_open_or_close():
    """Inconsistent rows are dropped, never silently 'corrected'."""
    bad = [1735689600000, 100.0, 99.0, 95.0, 105.0]  # high < close
    assert map_ohlc([bad]) == []


def test_map_ohlc_drops_row_where_low_is_above_open_or_close():
    bad = [1735689600000, 100.0, 110.0, 101.0, 105.0]  # low > open
    assert map_ohlc([bad]) == []


def test_map_ohlc_drops_malformed_rows():
    assert map_ohlc([[1735689600000, 100.0]]) == []          # too short
    assert map_ohlc([["x", 100.0, 110.0, 95.0, 105.0]]) == []  # non-numeric
    assert map_ohlc(["not-a-row"]) == []                       # not a list


def test_map_ohlc_keeps_valid_rows_and_drops_only_bad_ones():
    rows = [VALID_ROW, [1735689600000, 100.0, 99.0, 95.0, 105.0], VALID_ROW]
    assert len(map_ohlc(rows)) == 2


def test_map_ohlc_sorts_chronologically():
    later = [1735776000000, 200.0, 210.0, 195.0, 205.0]
    earlier = [1735689600000, 100.0, 110.0, 95.0, 105.0]
    candles = map_ohlc([later, earlier])
    assert candles[0].timestamp < candles[1].timestamp


def test_map_ohlc_empty_input():
    assert map_ohlc([]) == []


def test_map_ohlc_allows_flat_candle_where_all_values_equal():
    flat = [1735689600000, 100.0, 100.0, 100.0, 100.0]
    candles = map_ohlc([flat])
    assert len(candles) == 1
