export interface MarketData {
  coin_id: string;
  price_usd: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  high_24h_usd: number | null;
  low_24h_usd: number | null;
  percent_change_1h: number | null;
  percent_change_24h: number | null;
  percent_change_7d: number | null;
  percent_change_30d: number | null;
  percent_change_1y: number | null;
  /** Absolute USD change over 24h — distinct from percent_change_24h. */
  price_change_24h_usd: number | null;
  circulating_supply: number | null;
  total_supply: number | null;
  max_supply: number | null;
  fully_diluted_valuation_usd: number | null;
  ath_usd: number | null;
  atl_usd: number | null;
  ath_change_percentage: number | null;
  atl_change_percentage: number | null;
  ath_date: string | null;
  atl_date: string | null;
  last_updated: string | null;
  data_source: string;
  is_stale: boolean;
}

export interface MoverItem {
  coin_id: string;
  name: string;
  symbol: string;
  logo_url: string | null;
  market_cap_rank: number | null;
  price_usd: number | null;
  percent_change_24h: number | null;
  /** Added for Market Movers; optional because older responses omit them. */
  market_cap_usd?: number | null;
  volume_24h_usd?: number | null;
  /** (24h high - low) / price * 100, derived by the backend from synced data. */
  volatility_24h_pct?: number | null;
}

export interface MarketOverview {
  active_cryptocurrencies: number;
  top_gainers: MoverItem[];
  top_losers: MoverItem[];
  last_updated: string | null;
  data_source: string;
}

export interface GlobalMarket {
  total_market_cap_usd: number | null;
  total_volume_24h_usd: number | null;
  market_cap_percentage: Record<string, number> | null;
  active_cryptocurrencies: number | null;
  market_cap_change_percentage_24h: number | null;
  last_updated: string | null;
  data_source: string;
}

export interface TrendingCoin {
  coingecko_id: string;
  internal_coin_id: string | null;
  name: string;
  symbol: string;
  market_cap_rank: number | null;
  score: number | null;
}

export interface TrendingResponse {
  items: TrendingCoin[];
  available: boolean;
  data_source: string;
  last_updated: string | null;
}

/**
 * Timeframes the backend actually supports. Kept in sync with
 * backend/app/providers/timeframes.py — the backend is the source of
 * truth. 1H/4H are deliberately absent: CoinGecko's OHLC endpoint
 * doesn't expose sub-daily ranges as distinct requests, and the
 * backend rejects them with a 422 rather than silently substituting.
 */
export type Timeframe = "1D" | "7D" | "30D" | "90D" | "1Y";

export const TIMEFRAMES: Timeframe[] = ["1D", "7D", "30D", "90D", "1Y"];

export interface HistoricalCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  /** Always null for now — CoinGecko's OHLC endpoint carries no volume. */
  volume: number | null;
}

export interface HistoricalPriceResponse {
  coin_id: string;
  timeframe: string;
  /** Provider-chosen candle granularity for this timeframe, e.g. "4h". */
  granularity: string;
  candles: HistoricalCandle[];
  data_source: string;
}

/**
 * Exchange-specific 24h stats for one trading pair (Phase 7).
 * Distinct from MarketData, which is the cross-market aggregate —
 * a Binance pair price is one venue's, not the coin's global price.
 */
export interface ExchangeTicker {
  symbol: string;
  base_asset: string | null;
  quote_asset: string | null;
  last_price: number | null;
  price_change_percent_24h: number | null;
  high_24h: number | null;
  low_24h: number | null;
  volume_24h: number | null;
  quote_volume_24h: number | null;
}

export interface ExchangeTickerResponse {
  exchange: string;
  tickers: ExchangeTicker[];
  count: number;
}

/** Sortable fields for the Markets table — must match backend MARKET_SORT_FIELDS. */
export type MarketCoinSortField =
  | "market_cap"
  | "price"
  | "change_24h"
  | "change_7d"
  | "volume"
  | "fdv"
  | "supply"
  | "volatility";

/** Filters for the Markets table — must match backend MARKET_FILTERS. */
export type MarketCoinFilter = "all" | "gainers" | "losers";

/**
 * A Markets-table row: coin identity joined with its current market
 * snapshot, served by GET /market/coins in one request per page.
 */
export interface MarketCoin {
  coin_id: string;
  name: string;
  symbol: string;
  logo_url: string | null;
  market_cap_rank: number | null;
  price_usd: number | null;
  percent_change_24h: number | null;
  high_24h_usd: number | null;
  low_24h_usd: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  circulating_supply: number | null;
  last_updated: string | null;
  // Optional extension fields (backend: schemas/market.py MarketCoin). `null`
  // = the provider did not supply it; `undefined` = an older response shape.
  percent_change_1h?: number | null;
  percent_change_7d?: number | null;
  percent_change_30d?: number | null;
  fully_diluted_valuation_usd?: number | null;
  total_supply?: number | null;
  max_supply?: number | null;
  ath_usd?: number | null;
  atl_usd?: number | null;
  ath_change_percentage?: number | null;
  atl_change_percentage?: number | null;
  volatility_24h_pct?: number | null;
  data_source?: string | null;
  is_stale?: boolean;
}

export interface MarketCoinListResponse {
  items: MarketCoin[];
  page: number;
  limit: number;
  total: number;
  pages: number;
  sort_by: string;
  sort_direction: string;
  data_source: string;
  /** Coins with ANY synced market snapshot (unfiltered); `total` is the filtered count. */
  coins_with_market_data?: number | null;
  /** Newest market_data write, and whether it exceeds the backend stale threshold. */
  last_updated?: string | null;
  is_stale?: boolean;
}

/**
 * Server-side filters of GET /market/coins beyond the all/gainers/losers
 * switch. Every bound is in the units the backend documents: USD for market
 * cap/volume, percent for 24h change. `undefined` = no constraint.
 */
export interface MarketCoinFilters {
  marketCapMin?: number;
  marketCapMax?: number;
  volumeMin?: number;
  volumeMax?: number;
  changeMin?: number;
  changeMax?: number;
  /** true = capped supply only; false = coins with no reported max supply. */
  hasMaxSupply?: boolean;
}
