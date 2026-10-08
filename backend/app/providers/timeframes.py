"""
Supported historical-data timeframes.

This is the single source of truth for which timeframes the platform
can actually serve. It is deliberately narrower than the "wish list"
of 1H/4H/1D/7D/30D/90D/1Y: CoinGecko's `/coins/{id}/ohlc` endpoint
takes a `days` parameter and chooses candle granularity itself, so
sub-daily *ranges* (1H, 4H) are not something the provider exposes as
a distinct request. Rather than fabricate intraday candles or silently
serve a day of data when an hour was asked for, those timeframes are
simply not offered.

CoinGecko's documented granularity for /ohlc:
    days=1        -> ~30-minute candles
    days=7,14,30  -> ~4-hour candles
    days >= 31    -> ~4-day candles

So "1D" already gives an intraday (30-minute) view, which is what a
short-timeframe user actually wants from this data source.
"""

from enum import Enum


class Timeframe(str, Enum):
    """Timeframes the historical endpoint accepts."""

    DAY_1 = "1D"
    DAY_7 = "7D"
    DAY_30 = "30D"
    DAY_90 = "90D"
    YEAR_1 = "1Y"


#: Maps each supported timeframe to CoinGecko's `days` query value.
TIMEFRAME_TO_DAYS: dict[Timeframe, int] = {
    Timeframe.DAY_1: 1,
    Timeframe.DAY_7: 7,
    Timeframe.DAY_30: 30,
    Timeframe.DAY_90: 90,
    Timeframe.YEAR_1: 365,
}


#: Human-readable description of the candle granularity the provider
#: returns for each timeframe — surfaced in the API response so the
#: frontend can label the chart honestly rather than guessing.
TIMEFRAME_GRANULARITY: dict[Timeframe, str] = {
    Timeframe.DAY_1: "30m",
    Timeframe.DAY_7: "4h",
    Timeframe.DAY_30: "4h",
    Timeframe.DAY_90: "4d",
    Timeframe.YEAR_1: "4d",
}
