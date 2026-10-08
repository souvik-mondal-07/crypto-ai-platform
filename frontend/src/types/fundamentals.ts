/**
 * Mirrors backend/app/schemas/fundamentals.py exactly — the backend is
 * the source of truth for these shapes.
 *
 * Provider-reported sections (market, supply, valuation, project_info,
 * ecosystem) are kept separate from `calculated_metrics`, which the
 * platform derived itself. Units: `*_ratio` is a fraction (0.045),
 * `*_percent` is on a 0–100 scale.
 */

export interface MarketOverview {
  market_cap_usd: number | null;
  market_cap_rank: number | null;
  volume_24h_usd: number | null;
  fully_diluted_valuation_usd: number | null;
}

export type SupplyType = "capped" | "unlimited" | "not_reported";

export interface SupplyData {
  circulating_supply: number | null;
  total_supply: number | null;
  max_supply: number | null;
  supply_type: SupplyType;
  notes: string[];
}

export interface PerformanceData {
  percent_change_1h: number | null;
  percent_change_24h: number | null;
  percent_change_7d: number | null;
  percent_change_30d: number | null;
  percent_change_1y: number | null;
}

export interface ValuationData {
  current_price_usd: number | null;
  ath_usd: number | null;
  atl_usd: number | null;
  ath_date: string | null;
  atl_date: string | null;
  ath_change_percentage: number | null;
  atl_change_percentage: number | null;
  performance: PerformanceData;
}

export interface ProjectInfo {
  description: string | null;
  homepage_urls: string[];
  whitepaper_url: string | null;
  blockchain_explorer_urls: string[];
  categories: string[];
  asset_platform_id: string | null;
  contract_addresses: Record<string, string>;
  hashing_algorithm: string | null;
  block_time_in_minutes: number | null;
  genesis_date: string | null;
}

export interface DevelopmentData {
  available: boolean;
  repositories: string[];
  forks: number | null;
  stars: number | null;
  subscribers: number | null;
  total_issues: number | null;
  closed_issues: number | null;
  pull_requests_merged: number | null;
  pull_request_contributors: number | null;
  commit_count_4_weeks: number | null;
  code_additions_4_weeks: number | null;
  code_deletions_4_weeks: number | null;
}

export interface CommunityData {
  official_forum_urls: string[];
  announcement_urls: string[];
  chat_urls: string[];
  twitter_screen_name: string | null;
  subreddit_url: string | null;
  telegram_channel_identifier: string | null;
  reddit_subscribers: number | null;
  telegram_channel_user_count: number | null;
}

export interface EcosystemData {
  development: DevelopmentData;
  community: CommunityData;
}

export type MetricUnit = "ratio" | "percent" | "tokens";

export interface CalculatedMetric {
  value: number | null;
  unit: MetricUnit;
  formula: string;
  /** Set exactly when `value` is null. */
  unavailable_reason: string | null;
}

export interface CalculatedMetrics {
  origin: "calculated";
  volume_to_market_cap: CalculatedMetric;
  market_cap_to_fdv: CalculatedMetric;
  circulating_to_max_supply_percent: CalculatedMetric;
  remaining_to_max_supply_percent: CalculatedMetric;
  remaining_supply_to_max: CalculatedMetric;
  circulating_to_total_supply_percent: CalculatedMetric;
  distance_from_ath_percent: CalculatedMetric;
  distance_from_atl_percent: CalculatedMetric;
}

export interface ScoreComponent {
  key: string;
  label: string;
  weight: number;
  available: boolean;
  subscore: number | null;
  points: number | null;
  input_description: string;
  rule: string;
}

export interface FundamentalScore {
  status: "scored" | "not_enough_data";
  /** 0–100, or null when status is "not_enough_data". */
  score: number | null;
  /** Share (0–100) of total score weight backed by real data. */
  coverage_percent: number;
  min_coverage_percent: number;
  components: ScoreComponent[];
  method_version: string;
  message: string | null;
  disclaimer: string;
}

export type SummaryCategory =
  | "market_position"
  | "liquidity"
  | "supply"
  | "valuation"
  | "project"
  | "development";

export interface SummaryItem {
  category: SummaryCategory;
  text: string;
}

export interface FundamentalTimestamps {
  fetched_at: string | null;
  calculated_at: string;
  updated_at: string | null;
  market_data_updated_at: string | null;
}

export interface FundamentalFreshness {
  market_data_is_stale: boolean;
  project_data_is_stale: boolean;
  project_refresh_failed: boolean;
}

export interface FundamentalAnalysisResponse {
  coin_id: string;
  symbol: string;
  name: string;
  source: string;
  market_data_source: string | null;
  market: MarketOverview | null;
  supply: SupplyData | null;
  valuation: ValuationData | null;
  project_info: ProjectInfo | null;
  ecosystem: EcosystemData | null;
  calculated_metrics: CalculatedMetrics;
  score: FundamentalScore;
  summary: SummaryItem[];
  timestamps: FundamentalTimestamps;
  freshness: FundamentalFreshness;
  is_partial: boolean;
  unavailable_sections: string[];
  warnings: string[];
}
