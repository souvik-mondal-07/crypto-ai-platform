"""
Pydantic response models for fundamental-analysis endpoints (Phase 11).

Structure encodes provenance: `market`, `supply`, `valuation`,
`project_info` and `ecosystem` hold PROVIDER-REPORTED values;
`calculated_metrics` holds values THIS platform derived (each with its
formula). They are separate objects on purpose so a calculated number
can never be mistaken for a provider-reported one.

Unit convention: a `*_ratio` is a plain fraction (0.045), a
`*_percent` is on a 0-100 scale (4.5).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---- Provider-reported sections -------------------------------------------


class MarketOverview(BaseModel):
    market_cap_usd: Optional[float] = None
    market_cap_rank: Optional[int] = None
    volume_24h_usd: Optional[float] = None
    fully_diluted_valuation_usd: Optional[float] = None


class SupplyData(BaseModel):
    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    #: capped = max supply reported; unlimited = provider explicitly says
    #: infinite; not_reported = unknown (never assumed to be unlimited).
    supply_type: Literal["capped", "unlimited", "not_reported"] = "not_reported"
    notes: list[str] = Field(default_factory=list)


class PerformanceData(BaseModel):
    percent_change_1h: Optional[float] = None
    percent_change_24h: Optional[float] = None
    percent_change_7d: Optional[float] = None
    percent_change_30d: Optional[float] = None
    percent_change_1y: Optional[float] = None


class ValuationData(BaseModel):
    current_price_usd: Optional[float] = None
    ath_usd: Optional[float] = None
    atl_usd: Optional[float] = None
    ath_date: Optional[datetime] = None
    atl_date: Optional[datetime] = None
    #: Provider-reported (as of the provider's last sync) — compare with
    #: the calculated distance_from_ath_percent, which uses the latest price.
    ath_change_percentage: Optional[float] = None
    atl_change_percentage: Optional[float] = None
    performance: PerformanceData = Field(default_factory=PerformanceData)


class ProjectInfo(BaseModel):
    description: Optional[str] = None
    homepage_urls: list[str] = Field(default_factory=list)
    whitepaper_url: Optional[str] = None
    blockchain_explorer_urls: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    asset_platform_id: Optional[str] = None
    contract_addresses: dict[str, str] = Field(default_factory=dict)
    hashing_algorithm: Optional[str] = None
    block_time_in_minutes: Optional[float] = None
    genesis_date: Optional[str] = None


class DevelopmentData(BaseModel):
    #: False when the provider has no usable development data for this coin
    #: (no repository linked, or an all-zero/empty developer block).
    available: bool = False
    repositories: list[str] = Field(default_factory=list)
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


class CommunityData(BaseModel):
    """Community links and reach figures (not sentiment)."""

    official_forum_urls: list[str] = Field(default_factory=list)
    announcement_urls: list[str] = Field(default_factory=list)
    chat_urls: list[str] = Field(default_factory=list)
    twitter_screen_name: Optional[str] = None
    subreddit_url: Optional[str] = None
    telegram_channel_identifier: Optional[str] = None
    reddit_subscribers: Optional[int] = None
    telegram_channel_user_count: Optional[int] = None


class EcosystemData(BaseModel):
    development: DevelopmentData = Field(default_factory=DevelopmentData)
    community: CommunityData = Field(default_factory=CommunityData)


# ---- Calculated sections --------------------------------------------------


class CalculatedMetric(BaseModel):
    value: Optional[float] = None
    unit: Literal["ratio", "percent", "tokens"]
    formula: str
    #: Set exactly when `value` is null.
    unavailable_reason: Optional[str] = None


class CalculatedMetrics(BaseModel):
    origin: Literal["calculated"] = "calculated"
    volume_to_market_cap: CalculatedMetric
    market_cap_to_fdv: CalculatedMetric
    circulating_to_max_supply_percent: CalculatedMetric
    remaining_to_max_supply_percent: CalculatedMetric
    remaining_supply_to_max: CalculatedMetric
    circulating_to_total_supply_percent: CalculatedMetric
    distance_from_ath_percent: CalculatedMetric
    distance_from_atl_percent: CalculatedMetric


class ScoreComponent(BaseModel):
    key: str
    label: str
    weight: int
    available: bool
    subscore: Optional[float] = None
    points: Optional[float] = None
    input_description: str
    rule: str


class FundamentalScore(BaseModel):
    status: Literal["scored", "not_enough_data"]
    #: 0-100, or null when status is "not_enough_data".
    score: Optional[float] = None
    #: Share (0-100) of total score weight backed by real data.
    coverage_percent: float
    min_coverage_percent: float
    components: list[ScoreComponent]
    method_version: str
    message: Optional[str] = None
    disclaimer: str


class SummaryItem(BaseModel):
    category: Literal["market_position", "liquidity", "supply", "valuation", "project", "development"]
    text: str


# ---- Freshness ------------------------------------------------------------


class FundamentalTimestamps(BaseModel):
    #: When project/ecosystem data was last fetched from the provider (null if never).
    fetched_at: Optional[datetime] = None
    #: When the derived metrics/score in this response were calculated.
    calculated_at: datetime
    #: When the stored analysis record was last written.
    updated_at: Optional[datetime] = None
    #: Timestamp of the market snapshot the calculations used.
    market_data_updated_at: Optional[datetime] = None


class FundamentalFreshness(BaseModel):
    market_data_is_stale: bool = False
    #: Project data is older than the refresh window (only possible when a refresh failed).
    project_data_is_stale: bool = False
    #: A provider refresh was attempted and failed; older stored data (if any) was served.
    project_refresh_failed: bool = False


class FundamentalAnalysisResponse(BaseModel):
    coin_id: str
    symbol: str
    name: str
    #: Provider of the project/ecosystem data ("coingecko"); market values use `market_data_source`.
    source: str
    market_data_source: Optional[str] = None

    market: Optional[MarketOverview] = None
    supply: Optional[SupplyData] = None
    valuation: Optional[ValuationData] = None
    project_info: Optional[ProjectInfo] = None
    ecosystem: Optional[EcosystemData] = None

    calculated_metrics: CalculatedMetrics
    score: FundamentalScore
    summary: list[SummaryItem] = Field(default_factory=list)

    timestamps: FundamentalTimestamps
    freshness: FundamentalFreshness
    #: True when any section could not be populated.
    is_partial: bool = False
    #: Sections with no data: "market", "project_info", "ecosystem".
    unavailable_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
