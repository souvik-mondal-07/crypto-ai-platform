"""
Binance response normalization.

Converts raw Binance JSON into `NormalizedBinanceSymbol` objects. Pure
data transformation — no HTTP, no MongoDB.
"""

from typing import Any, Optional

from app.providers.normalized import NormalizedBinanceSymbol, NormalizedExchangeTicker

# Binance only lists trading pairs against a quote asset. USDT pairs
# are used to determine "this coin is available on Binance" for the
# coin-provider-mapping enrichment step — see docs/market-data.md for
# why USDT specifically (it's Binance's highest-coverage quote asset).
RELEVANT_QUOTE_ASSETS = {"USDT"}


def map_exchange_info(raw: dict[str, Any]) -> list[NormalizedBinanceSymbol]:
    """Map the `symbols` array from GET /api/v3/exchangeInfo."""
    symbols = raw.get("symbols", [])
    result = []
    for entry in symbols:
        quote_asset = entry.get("quoteAsset")
        if quote_asset not in RELEVANT_QUOTE_ASSETS:
            continue
        result.append(
            NormalizedBinanceSymbol(
                symbol=entry.get("symbol", ""),
                base_asset=entry.get("baseAsset", ""),
                quote_asset=quote_asset,
                status=entry.get("status", "UNKNOWN"),
            )
        )
    return result


def _to_float(value: Any) -> Optional[float]:
    """
    Binance returns every numeric field as a string. A value that
    isn't parseable becomes None rather than 0.0 — a zero price/volume
    would be indistinguishable from a real zero.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_ticker_24hr(
    raw_items: list[dict[str, Any]],
    symbol_index: Optional[dict[str, NormalizedBinanceSymbol]] = None,
) -> list[NormalizedExchangeTicker]:
    """
    Map GET /api/v3/ticker/24hr into normalized exchange tickers.

    `symbol_index` (from `map_exchange_info`) supplies base/quote asset
    for each pair, since the ticker payload carries only the combined
    symbol. When it's absent or a symbol is missing from it, those two
    fields stay None rather than being guessed at by string-splitting
    the symbol (which is ambiguous — "BTCUSDT" could split several ways).

    Rows without a symbol are dropped.
    """
    result: list[NormalizedExchangeTicker] = []

    for entry in raw_items:
        symbol = entry.get("symbol")
        if not symbol:
            continue

        known = symbol_index.get(symbol) if symbol_index else None

        result.append(
            NormalizedExchangeTicker(
                symbol=symbol,
                base_asset=known.base_asset if known else None,
                quote_asset=known.quote_asset if known else None,
                last_price=_to_float(entry.get("lastPrice")),
                price_change_percent_24h=_to_float(entry.get("priceChangePercent")),
                high_24h=_to_float(entry.get("highPrice")),
                low_24h=_to_float(entry.get("lowPrice")),
                volume_24h=_to_float(entry.get("volume")),
                quote_volume_24h=_to_float(entry.get("quoteVolume")),
            )
        )

    return result
