export interface CoinGeckoMapping {
  id: string;
  available: boolean;
}

export interface BinanceMapping {
  symbol: string;
  available: boolean;
}

export interface CoinProviders {
  coingecko: CoinGeckoMapping | null;
  binance: BinanceMapping | null;
}

export interface Coin {
  id: string;
  name: string;
  symbol: string;
  slug: string | null;
  logo_url: string | null;
  market_cap_rank: number | null;
  is_active: boolean;
  providers: CoinProviders;
  created_at: string;
  updated_at: string;
}

export interface CoinListResponse {
  items: Coin[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

/**
 * One search-result row: coin identity joined with its current market
 * snapshot server-side (GET /coins/search) — no per-row follow-up
 * request is needed. A `null` market field means no market_data has
 * been synced yet for that coin, not that it was left out.
 */
export interface CoinSearchResult extends Coin {
  price_usd: number | null;
  percent_change_24h: number | null;
  percent_change_7d: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  high_24h_usd: number | null;
  low_24h_usd: number | null;
}

export interface CoinSearchResponse {
  items: CoinSearchResult[];
  query: string;
  count: number;
}
