"""
Converts raw MongoDB documents (dicts) into the API's Pydantic
response schemas. Kept separate from the repository layer (which
returns plain dicts) so repositories stay storage-shaped and services
stay presentation-shaped.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.schemas.auth import UserResponse
from app.schemas.coin import BinanceMapping, Coin, CoinGeckoMapping, CoinProviders, CoinSearchResult
from app.schemas.market import MarketData, MoverItem

# A market snapshot older than this is flagged `is_stale` in API
# responses — a deliberately generous window for Step 3's manual sync
# trigger (no scheduler exists yet); this will typically shrink once
# Celery-based periodic sync is introduced.
STALE_AFTER = timedelta(hours=6)


def coin_doc_to_schema(doc: dict[str, Any]) -> Coin:
    providers_doc = doc.get("providers") or {}
    coingecko = providers_doc.get("coingecko")
    binance = providers_doc.get("binance")

    return Coin(
        id=str(doc["_id"]),
        name=doc["name"],
        symbol=doc["symbol"],
        slug=doc.get("slug"),
        logo_url=doc.get("logo_url"),
        market_cap_rank=doc.get("market_cap_rank"),
        is_active=doc.get("is_active", True),
        providers=CoinProviders(
            coingecko=CoinGeckoMapping(**coingecko) if coingecko else None,
            binance=BinanceMapping(**binance) if binance else None,
        ),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def coin_search_result_to_schema(
    coin_doc: dict[str, Any], market_doc: Optional[dict[str, Any]]
) -> CoinSearchResult:
    """
    Joins a coin document with its (possibly absent) current market
    snapshot into one search-result row. `market_doc` is `None` when
    no market_data has been synced yet for this coin — every market
    field is then left `None` (never a fabricated placeholder), and
    the frontend renders that as "—".
    """
    base = coin_doc_to_schema(coin_doc)
    market_fields = {
        "price_usd": market_doc.get("price_usd") if market_doc else None,
        "percent_change_24h": market_doc.get("percent_change_24h") if market_doc else None,
        "percent_change_7d": market_doc.get("percent_change_7d") if market_doc else None,
        "market_cap_usd": market_doc.get("market_cap_usd") if market_doc else None,
        "volume_24h_usd": market_doc.get("volume_24h_usd") if market_doc else None,
        "high_24h_usd": market_doc.get("high_24h_usd") if market_doc else None,
        "low_24h_usd": market_doc.get("low_24h_usd") if market_doc else None,
    }
    return CoinSearchResult(**base.model_dump(), **market_fields)


def market_data_doc_to_schema(doc: dict[str, Any]) -> MarketData:
    updated_at = doc.get("updated_at")
    is_stale = bool(updated_at) and (datetime.now(timezone.utc) - _as_aware(updated_at) > STALE_AFTER)

    return MarketData(
        coin_id=str(doc["coin_id"]),
        price_usd=doc.get("price_usd"),
        market_cap_usd=doc.get("market_cap_usd"),
        volume_24h_usd=doc.get("volume_24h_usd"),
        high_24h_usd=doc.get("high_24h_usd"),
        low_24h_usd=doc.get("low_24h_usd"),
        percent_change_1h=doc.get("percent_change_1h"),
        percent_change_24h=doc.get("percent_change_24h"),
        percent_change_7d=doc.get("percent_change_7d"),
        percent_change_30d=doc.get("percent_change_30d"),
        percent_change_1y=doc.get("percent_change_1y"),
        price_change_24h_usd=doc.get("price_change_24h_usd"),
        circulating_supply=doc.get("circulating_supply"),
        total_supply=doc.get("total_supply"),
        max_supply=doc.get("max_supply"),
        fully_diluted_valuation_usd=doc.get("fully_diluted_valuation_usd"),
        ath_usd=doc.get("ath_usd"),
        atl_usd=doc.get("atl_usd"),
        ath_change_percentage=doc.get("ath_change_percentage"),
        atl_change_percentage=doc.get("atl_change_percentage"),
        ath_date=doc.get("ath_date"),
        atl_date=doc.get("atl_date"),
        last_updated=doc.get("last_updated"),
        data_source=doc.get("data_source", "unknown"),
        is_stale=is_stale,
    )


def user_doc_to_schema(doc: dict[str, Any]) -> UserResponse:
    """
    Converts a raw `users` document into the safe, public-facing
    response shape. `password_hash` is simply never read here — there
    is no field-stripping step to forget, since UserResponse has no
    such field to populate.
    """
    return UserResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        role=doc.get("role", "user"),
        created_at=doc["created_at"],
    )


def volatility_24h_pct(
    high: Optional[float], low: Optional[float], price: Optional[float]
) -> Optional[float]:
    """
    24h range as a percentage of the current price: (high - low) / price * 100.

    Derived purely from synced provider fields. Returns None whenever an
    input is missing or the price is not positive — never a guessed value.
    """
    if high is None or low is None or price is None or price <= 0 or high < low:
        return None
    return (high - low) / price * 100.0


def is_snapshot_stale(updated_at: Optional[datetime]) -> bool:
    """Same rule as MarketData.is_stale (STALE_AFTER) — one shared definition."""
    if not updated_at:
        return False
    return datetime.now(timezone.utc) - _as_aware(updated_at) > STALE_AFTER


def mover_item(coin_doc: dict[str, Any], market_doc: dict[str, Any]) -> MoverItem:
    return MoverItem(
        coin_id=str(coin_doc["_id"]),
        name=coin_doc["name"],
        symbol=coin_doc["symbol"],
        logo_url=coin_doc.get("logo_url"),
        market_cap_rank=coin_doc.get("market_cap_rank"),
        price_usd=market_doc.get("price_usd"),
        percent_change_24h=market_doc.get("percent_change_24h"),
        market_cap_usd=market_doc.get("market_cap_usd"),
        volume_24h_usd=market_doc.get("volume_24h_usd"),
        volatility_24h_pct=volatility_24h_pct(
            market_doc.get("high_24h_usd"), market_doc.get("low_24h_usd"), market_doc.get("price_usd")
        ),
    )


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
