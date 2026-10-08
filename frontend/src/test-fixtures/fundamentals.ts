/**
 * Test-only builders for FundamentalAnalysisResponse. These are fixtures
 * for the test suite — the application never imports this file.
 */
import type {
  CalculatedMetric,
  CalculatedMetrics,
  FundamentalAnalysisResponse,
  MetricUnit,
} from "../types/fundamentals";

export function metric(value: number | null, unit: MetricUnit, reason: string | null = null): CalculatedMetric {
  return { value, unit, formula: `formula for ${unit}`, unavailable_reason: value === null ? reason ?? "Input not available." : null };
}

export function buildMetrics(overrides: Partial<CalculatedMetrics> = {}): CalculatedMetrics {
  return {
    origin: "calculated",
    volume_to_market_cap: metric(0.0371, "ratio"),
    market_cap_to_fdv: metric(0.7455, "ratio"),
    circulating_to_max_supply_percent: metric(71.43, "percent"),
    remaining_to_max_supply_percent: metric(28.57, "percent"),
    remaining_supply_to_max: metric(6_000_000, "tokens"),
    circulating_to_total_supply_percent: metric(83.33, "percent"),
    distance_from_ath_percent: metric(-75, "percent"),
    distance_from_atl_percent: metric(400, "percent"),
    ...overrides,
  };
}

export function buildFundamentals(overrides: Partial<FundamentalAnalysisResponse> = {}): FundamentalAnalysisResponse {
  return {
    coin_id: "507f1f77bcf86cd799439011",
    symbol: "EXC",
    name: "Examplecoin",
    source: "coingecko",
    market_data_source: "coingecko",
    market: {
      market_cap_usd: 1_230_000_000,
      market_cap_rank: 12,
      volume_24h_usd: 45_670_000,
      fully_diluted_valuation_usd: 1_650_000_000,
    },
    supply: {
      circulating_supply: 15_000_000,
      total_supply: 18_000_000,
      max_supply: 21_000_000,
      supply_type: "capped",
      notes: [],
    },
    valuation: {
      current_price_usd: 50,
      ath_usd: 200,
      atl_usd: 10,
      ath_date: "2021-11-10T00:00:00Z",
      atl_date: "2015-10-20T00:00:00Z",
      ath_change_percentage: -74.9,
      atl_change_percentage: 399,
      performance: {
        percent_change_1h: 0.1,
        percent_change_24h: 1.5,
        percent_change_7d: 2,
        percent_change_30d: 3,
        percent_change_1y: 30,
      },
    },
    project_info: {
      description: "A <b>peer-to-peer</b> test asset. <a href=\"javascript:alert(1)\">click</a>",
      homepage_urls: ["https://www.example.org"],
      whitepaper_url: "https://docs.example.org/whitepaper.pdf",
      blockchain_explorer_urls: ["https://explorer.example.org"],
      categories: ["Layer 1 (L1)", "Smart Contract Platform"],
      asset_platform_id: "ethereum",
      contract_addresses: { ethereum: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" },
      hashing_algorithm: "Ethash",
      block_time_in_minutes: 0.2,
      genesis_date: "2015-07-30",
    },
    ecosystem: {
      development: {
        available: true,
        repositories: ["https://github.com/example/core"],
        forks: 20_000,
        stars: 45_000,
        subscribers: 3_000,
        total_issues: 9_000,
        closed_issues: 8_500,
        pull_requests_merged: 12_000,
        pull_request_contributors: 850,
        commit_count_4_weeks: 120,
        code_additions_4_weeks: 4_500,
        code_deletions_4_weeks: 2_100,
      },
      community: {
        official_forum_urls: ["https://forum.example.org"],
        announcement_urls: [],
        chat_urls: [],
        twitter_screen_name: "examplecoin",
        subreddit_url: "https://www.reddit.com/r/examplecoin",
        telegram_channel_identifier: null,
        reddit_subscribers: 2_500_000,
        telegram_channel_user_count: null,
      },
    },
    calculated_metrics: buildMetrics(),
    score: {
      status: "scored",
      score: 88,
      coverage_percent: 100,
      min_coverage_percent: 50,
      components: [
        { key: "market_size", label: "Market size", weight: 25, available: true, subscore: 80, points: 20, input_description: "Market cap $1.23B", rule: "Market cap bands rule." },
        { key: "liquidity", label: "Trading liquidity", weight: 20, available: true, subscore: 100, points: 20, input_description: "24h volume is 3.71% of market cap", rule: "Liquidity bands rule." },
        { key: "supply_dilution", label: "Supply in circulation", weight: 20, available: true, subscore: 65, points: 13, input_description: "71.4% of maximum supply is circulating", rule: "Supply bands rule." },
        { key: "development_activity", label: "Development activity", weight: 15, available: true, subscore: 100, points: 15, input_description: "120 commits in the last 4 weeks", rule: "Commit bands rule." },
        { key: "project_maturity", label: "Project maturity", weight: 10, available: true, subscore: 100, points: 10, input_description: "11.2 years since genesis", rule: "Age bands rule." },
        { key: "information_completeness", label: "Project information", weight: 10, available: true, subscore: 100, points: 10, input_description: "6 of 6 items provided", rule: "Completeness rule." },
      ],
      method_version: "1.0",
      message: null,
      disclaimer: "A descriptive, rule-based summary of structural characteristics. It is not investment advice, does not predict price movements, and is not a trading signal or decision.",
    },
    summary: [
      { category: "market_position", text: "Ranked #12 by market capitalization, with a market cap of $1.23B." },
      { category: "supply", text: "Supply is capped at 21,000,000 units; 71.4% is currently in circulation (calculated)." },
      { category: "valuation", text: "Price is 75.0% below its recorded all-time high (calculated)." },
    ],
    timestamps: {
      fetched_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
      calculated_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      market_data_updated_at: new Date(Date.now() - 60_000).toISOString(),
    },
    freshness: { market_data_is_stale: false, project_data_is_stale: false, project_refresh_failed: false },
    is_partial: false,
    unavailable_sections: [],
    warnings: [],
    ...overrides,
  };
}
