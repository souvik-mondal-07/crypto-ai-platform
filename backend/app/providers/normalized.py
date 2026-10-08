"""
Normalized, provider-agnostic domain objects.

Provider mappers translate raw CoinGecko/Binance responses into these
dataclasses. Nothing downstream of a mapper (sync service,
repositories, API layer) needs to know which provider a piece of data
came from beyond the `provider`/`coingecko_id`/`binance_symbol` fields
themselves — this is the "Normalizer" layer in:

    provider response -> provider mapper -> normalized object -> MongoDB
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class NormalizedCoin:
    """A coin's identity/master-record fields, independent of live price data."""

    coingecko_id: str
    symbol: str
    name: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    market_cap_rank: Optional[int] = None
    binance_symbol: Optional[str] = None


@dataclass
class NormalizedMarketData:
    """A single coin's current market snapshot, keyed by CoinGecko ID."""

    coingecko_id: str
    price_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None
    #: Absolute USD change over 24h — distinct from percent_change_24h.
    price_change_24h_usd: Optional[float] = None
    percent_change_1h: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    percent_change_30d: Optional[float] = None
    percent_change_1y: Optional[float] = None
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    fully_diluted_valuation_usd: Optional[float] = None
    ath_usd: Optional[float] = None
    atl_usd: Optional[float] = None
    ath_change_percentage: Optional[float] = None
    atl_change_percentage: Optional[float] = None
    #: When the coin reached its ATH/ATL — the provider's own record,
    #: never computed locally.
    ath_date: Optional[datetime] = None
    atl_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None


@dataclass
class NormalizedGlobalMarket:
    total_market_cap_usd: Optional[float] = None
    total_volume_24h_usd: Optional[float] = None
    market_cap_percentage: Optional[dict] = None
    active_cryptocurrencies: Optional[int] = None
    market_cap_change_percentage_24h: Optional[float] = None
    last_updated: Optional[datetime] = None


@dataclass
class NormalizedTrendingCoin:
    coingecko_id: str
    name: str
    symbol: str
    market_cap_rank: Optional[int] = None
    score: Optional[int] = None


@dataclass
class NormalizedCandle:
    """
    A single OHLC candle. `volume` is Optional because not every
    provider endpoint supplies it — CoinGecko's /coins/{id}/ohlc
    returns OHLC only, with no volume component. It is left as None
    rather than fabricated (see docs/market-data.md).
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


@dataclass
class NormalizedExchangeTicker:
    """
    Exchange-specific 24h market stats for one trading pair — one
    venue's view of a single pair (e.g. BTCUSDT on Binance), not the
    cross-market aggregate CoinGecko provides.

    Still backs `/market/exchange/binance/tickers` as Binance's own
    numbers. As of the real-time refresh upgrade, it is ALSO used —
    narrowly and disclosed via `data_source="binance"` — to keep a
    handful of live-tracking fields on `market_data` fresh for coins
    with a valid Binance mapping; see
    `MarketDataRepository.bulk_upsert_binance_prices` for exactly
    which fields, and why the rest (market cap, supply, ATH/ATL) are
    deliberately left untouched rather than derived from this.
    """

    symbol: str
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None
    last_price: Optional[float] = None
    price_change_percent_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    quote_volume_24h: Optional[float] = None


@dataclass
class NormalizedBinanceSymbol:
    """A single Binance trading pair, e.g. BTCUSDT."""

    symbol: str
    base_asset: str
    quote_asset: str
    status: str


@dataclass
class NormalizedDeveloperData:
    """
    Provider-reported development activity (CoinGecko `developer_data`).

    Every field is Optional: a provider that doesn't track a coin's
    repositories returns nulls/zeros, and the mapper preserves exactly
    what was reported — the score/UI layers decide how to interpret
    "no data" (see fundamental_calculations.development_data_available).
    """

    forks: Optional[int] = None
    stars: Optional[int] = None
    subscribers: Optional[int] = None
    total_issues: Optional[int] = None
    closed_issues: Optional[int] = None
    pull_requests_merged: Optional[int] = None
    pull_request_contributors: Optional[int] = None
    commit_count_4_weeks: Optional[int] = None
    code_additions_4_weeks: Optional[int] = None
    code_deletions_4_weeks: Optional[int] = None


@dataclass
class NormalizedCommunityData:
    """Provider-reported community reach figures (not sentiment)."""

    reddit_subscribers: Optional[int] = None
    telegram_channel_user_count: Optional[int] = None
    facebook_likes: Optional[int] = None


@dataclass
class NormalizedCoinProfile:
    """
    Slow-changing project/ecosystem information for one coin, from
    CoinGecko's `/coins/{id}` (fetched with market_data disabled — the
    market figures already live in `market_data`).
    """

    coingecko_id: str
    description: Optional[str] = None
    homepage_urls: list[str] = field(default_factory=list)
    whitepaper_url: Optional[str] = None
    blockchain_explorer_urls: list[str] = field(default_factory=list)
    official_forum_urls: list[str] = field(default_factory=list)
    announcement_urls: list[str] = field(default_factory=list)
    chat_urls: list[str] = field(default_factory=list)
    twitter_screen_name: Optional[str] = None
    subreddit_url: Optional[str] = None
    telegram_channel_identifier: Optional[str] = None
    github_repos: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    asset_platform_id: Optional[str] = None
    #: platform id -> contract address (empty-string entries dropped)
    contract_addresses: dict[str, str] = field(default_factory=dict)
    hashing_algorithm: Optional[str] = None
    block_time_in_minutes: Optional[float] = None
    #: "YYYY-MM-DD" as reported; kept as a string, never coerced/guessed.
    genesis_date: Optional[str] = None
    #: Explicit provider flag; None when the provider did not report it.
    max_supply_infinite: Optional[bool] = None
    developer: NormalizedDeveloperData = field(default_factory=NormalizedDeveloperData)
    community: NormalizedCommunityData = field(default_factory=NormalizedCommunityData)
    last_updated: Optional[datetime] = None
