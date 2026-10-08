"""
CoinGecko response normalization.

Converts raw CoinGecko JSON into the app's provider-agnostic
dataclasses (`app/providers/normalized.py`). No HTTP, no MongoDB —
pure data transformation, which is what makes it straightforward to
unit test with fixture JSON (see tests/test_coingecko_mapper.py).

Every field read from the raw payload uses `.get()` with a safe
default — a missing field becomes `None`, never a fabricated value.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from app.providers.normalized import (
    NormalizedCandle,
    NormalizedCoin,
    NormalizedCoinProfile,
    NormalizedCommunityData,
    NormalizedDeveloperData,
    NormalizedGlobalMarket,
    NormalizedMarketData,
    NormalizedTrendingCoin,
)


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """CoinGecko timestamps are ISO-8601 UTC strings like '...Z'."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def map_coin_list_item(raw: dict[str, Any]) -> NormalizedCoin:
    """
    Map one entry from GET /coins/list — id/symbol/name only, no rank
    or market data (that's filled in separately by `map_coin_market`
    when/if that coin appears in a /coins/markets page).
    """
    coingecko_id = raw["id"]
    return NormalizedCoin(
        coingecko_id=coingecko_id,
        symbol=(raw.get("symbol") or "").upper(),
        name=raw.get("name") or coingecko_id,
        # CoinGecko doesn't return a separate "slug" on /coins/list —
        # its own `id` field IS already a URL-friendly slug (e.g.
        # "bitcoin", "usd-coin"), so we reuse it rather than inventing
        # a second identifier that would just duplicate `coingecko_id`.
        slug=coingecko_id,
    )


def map_coin_market(raw: dict[str, Any]) -> tuple[NormalizedCoin, NormalizedMarketData]:
    """
    Map one entry from GET /coins/markets into both its coin-identity
    fields and its market-data fields — the endpoint returns both
    together, but the application stores them in separate collections
    (see docs/database-schema.md), so the mapper returns both parts
    for the sync service to route independently.
    """
    coingecko_id = raw["id"]

    coin = NormalizedCoin(
        coingecko_id=coingecko_id,
        symbol=(raw.get("symbol") or "").upper(),
        name=raw.get("name") or coingecko_id,
        slug=coingecko_id,
        logo_url=raw.get("image"),
        market_cap_rank=raw.get("market_cap_rank"),
    )

    market = NormalizedMarketData(
        coingecko_id=coingecko_id,
        price_usd=raw.get("current_price"),
        market_cap_usd=raw.get("market_cap"),
        volume_24h_usd=raw.get("total_volume"),
        high_24h_usd=raw.get("high_24h"),
        low_24h_usd=raw.get("low_24h"),
        percent_change_1h=raw.get("price_change_percentage_1h_in_currency"),
        percent_change_24h=raw.get("price_change_percentage_24h_in_currency")
        if raw.get("price_change_percentage_24h_in_currency") is not None
        else raw.get("price_change_percentage_24h"),
        percent_change_7d=raw.get("price_change_percentage_7d_in_currency"),
        percent_change_30d=raw.get("price_change_percentage_30d_in_currency"),
        percent_change_1y=raw.get("price_change_percentage_1y_in_currency"),
        price_change_24h_usd=raw.get("price_change_24h"),
        circulating_supply=raw.get("circulating_supply"),
        total_supply=raw.get("total_supply"),
        max_supply=raw.get("max_supply"),
        fully_diluted_valuation_usd=raw.get("fully_diluted_valuation"),
        ath_usd=raw.get("ath"),
        atl_usd=raw.get("atl"),
        ath_change_percentage=raw.get("ath_change_percentage"),
        atl_change_percentage=raw.get("atl_change_percentage"),
        ath_date=_parse_timestamp(raw.get("ath_date")),
        atl_date=_parse_timestamp(raw.get("atl_date")),
        last_updated=_parse_timestamp(raw.get("last_updated")),
    )

    return coin, market


def map_global(raw: dict[str, Any]) -> NormalizedGlobalMarket:
    """Map the `data` object from GET /global."""
    total_market_cap = raw.get("total_market_cap") or {}
    total_volume = raw.get("total_volume") or {}
    market_cap_change = raw.get("market_cap_change_percentage_24h_usd")
    updated_at_epoch = raw.get("updated_at")

    return NormalizedGlobalMarket(
        total_market_cap_usd=total_market_cap.get("usd"),
        total_volume_24h_usd=total_volume.get("usd"),
        market_cap_percentage=raw.get("market_cap_percentage"),
        active_cryptocurrencies=raw.get("active_cryptocurrencies"),
        market_cap_change_percentage_24h=market_cap_change,
        last_updated=(
            datetime.fromtimestamp(updated_at_epoch, tz=timezone.utc)
            if isinstance(updated_at_epoch, (int, float))
            else None
        ),
    )


def map_trending(raw_items: list[dict[str, Any]]) -> list[NormalizedTrendingCoin]:
    """Map the `coins` array from GET /search/trending."""
    result = []
    for entry in raw_items:
        item = entry.get("item") or {}
        coingecko_id = item.get("id")
        if not coingecko_id:
            continue
        result.append(
            NormalizedTrendingCoin(
                coingecko_id=coingecko_id,
                name=item.get("name") or coingecko_id,
                symbol=(item.get("symbol") or "").upper(),
                market_cap_rank=item.get("market_cap_rank"),
                score=item.get("score"),
            )
        )
    return result


def map_ohlc(raw_rows: list[list[float]]) -> list[NormalizedCandle]:
    """
    Map CoinGecko's /coins/{id}/ohlc response — an array of
    `[timestamp_ms, open, high, low, close]` arrays — into candles.

    Validates rather than manufactures: a row that is malformed (wrong
    length, non-numeric) or internally inconsistent (high below the
    max of open/close, or low above the min) is DROPPED, not "fixed"
    by adjusting its values. Silently reshaping a provider's numbers
    would mean charting data the provider never actually reported.

    Volume is left as None — this endpoint carries no volume component.
    Results are sorted chronologically so the chart library receives
    ordered data regardless of provider ordering.
    """
    candles: list[NormalizedCandle] = []

    for row in raw_rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue

        timestamp_ms, open_, high, low, close = row[0], row[1], row[2], row[3], row[4]

        if any(not isinstance(v, (int, float)) for v in (timestamp_ms, open_, high, low, close)):
            continue

        # OHLC internal consistency — drop rather than clamp.
        if high < max(open_, close) or low > min(open_, close) or low > high:
            continue

        try:
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            continue

        candles.append(
            NormalizedCandle(
                timestamp=timestamp,
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=None,
            )
        )

    candles.sort(key=lambda c: c.timestamp)
    return candles


# ---------------------------------------------------------------------------
# Coin profile (GET /coins/{id}) — Phase 11
# ---------------------------------------------------------------------------


def _clean_str(value: Any) -> Optional[str]:
    """A non-blank string, or None. Never coerces other types to text."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _clean_url_list(value: Any) -> list[str]:
    """Non-blank strings only, de-duplicated in order (CoinGecko pads lists with '')."""
    if not isinstance(value, list):
        return []
    seen: list[str] = []
    for item in value:
        cleaned = _clean_str(item)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _clean_int(value: Any) -> Optional[int]:
    # bool is an int subclass — a stray `true` must not become 1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return int(value)


def _clean_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return float(value)


def map_coin_profile(raw: dict[str, Any]) -> NormalizedCoinProfile:
    """
    Map a GET /coins/{id} payload into a NormalizedCoinProfile.

    Deliberately NOT mapped: `sentiment_votes_*`, `watchlist_portfolio_users`
    and any market_data — sentiment belongs to a later phase, and market
    figures already come from the `market_data` collection.
    """
    links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    repos = links.get("repos_url") if isinstance(links.get("repos_url"), dict) else {}
    description = raw.get("description")
    description_en = _clean_str(description.get("en")) if isinstance(description, dict) else None

    platforms = raw.get("platforms") if isinstance(raw.get("platforms"), dict) else {}
    contract_addresses = {
        k: v.strip()
        for k, v in platforms.items()
        if isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
    }

    dev_raw = raw.get("developer_data") if isinstance(raw.get("developer_data"), dict) else {}
    additions_deletions = (
        dev_raw.get("code_additions_deletions_4_weeks")
        if isinstance(dev_raw.get("code_additions_deletions_4_weeks"), dict)
        else {}
    )
    developer = NormalizedDeveloperData(
        forks=_clean_int(dev_raw.get("forks")),
        stars=_clean_int(dev_raw.get("stars")),
        subscribers=_clean_int(dev_raw.get("subscribers")),
        total_issues=_clean_int(dev_raw.get("total_issues")),
        closed_issues=_clean_int(dev_raw.get("closed_issues")),
        pull_requests_merged=_clean_int(dev_raw.get("pull_requests_merged")),
        pull_request_contributors=_clean_int(dev_raw.get("pull_request_contributors")),
        commit_count_4_weeks=_clean_int(dev_raw.get("commit_count_4_weeks")),
        code_additions_4_weeks=_clean_int(additions_deletions.get("additions")),
        code_deletions_4_weeks=_clean_int(additions_deletions.get("deletions")),
    )

    comm_raw = raw.get("community_data") if isinstance(raw.get("community_data"), dict) else {}
    community = NormalizedCommunityData(
        reddit_subscribers=_clean_int(comm_raw.get("reddit_subscribers")),
        telegram_channel_user_count=_clean_int(comm_raw.get("telegram_channel_user_count")),
        facebook_likes=_clean_int(comm_raw.get("facebook_likes")),
    )

    # `max_supply_infinite` is documented at the top level of the coin
    # payload; also accept it under market_data if a plan/version puts
    # it there. Only a real boolean counts — anything else is "unknown".
    market_block = raw.get("market_data") if isinstance(raw.get("market_data"), dict) else {}
    infinite_flag = raw.get("max_supply_infinite")
    if not isinstance(infinite_flag, bool):
        infinite_flag = market_block.get("max_supply_infinite")
    if not isinstance(infinite_flag, bool):
        infinite_flag = None

    genesis = _clean_str(raw.get("genesis_date"))

    return NormalizedCoinProfile(
        coingecko_id=raw["id"],
        description=description_en,
        homepage_urls=_clean_url_list(links.get("homepage")),
        whitepaper_url=_clean_str(links.get("whitepaper")),
        blockchain_explorer_urls=_clean_url_list(links.get("blockchain_site")),
        official_forum_urls=_clean_url_list(links.get("official_forum_url")),
        announcement_urls=_clean_url_list(links.get("announcement_url")),
        chat_urls=_clean_url_list(links.get("chat_url")),
        twitter_screen_name=_clean_str(links.get("twitter_screen_name")),
        subreddit_url=_clean_str(links.get("subreddit_url")),
        telegram_channel_identifier=_clean_str(links.get("telegram_channel_identifier")),
        github_repos=_clean_url_list(repos.get("github")),
        categories=_clean_url_list(raw.get("categories")),
        asset_platform_id=_clean_str(raw.get("asset_platform_id")),
        contract_addresses=contract_addresses,
        hashing_algorithm=_clean_str(raw.get("hashing_algorithm")),
        block_time_in_minutes=_clean_float(raw.get("block_time_in_minutes")),
        genesis_date=genesis,
        max_supply_infinite=infinite_flag,
        developer=developer,
        community=community,
        last_updated=_parse_timestamp(raw.get("last_updated")),
    )
