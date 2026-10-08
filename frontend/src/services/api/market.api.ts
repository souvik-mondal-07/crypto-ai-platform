import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type {
  ExchangeTickerResponse,
  GlobalMarket,
  HistoricalPriceResponse,
  MarketCoinFilter,
  MarketCoinFilters,
  MarketCoinListResponse,
  MarketCoinSortField,
  MarketData,
  MarketOverview,
  MoverItem,
  Timeframe,
  TrendingResponse,
} from "../../types/market";

export async function fetchCoinMarketData(coinId: string): Promise<MarketData> {
  const { data } = await apiClient.get<MarketData>(apiConfig.endpoints.coinMarket(coinId));
  return data;
}

export async function fetchMarketOverview(moversLimit = 5): Promise<MarketOverview> {
  const { data } = await apiClient.get<MarketOverview>(apiConfig.endpoints.marketOverview, {
    params: { movers_limit: moversLimit },
  });
  return data;
}

export async function fetchGainers(limit = 10): Promise<MoverItem[]> {
  const { data } = await apiClient.get<MoverItem[]>(apiConfig.endpoints.marketGainers, {
    params: { limit },
  });
  return data;
}

export async function fetchLosers(limit = 10): Promise<MoverItem[]> {
  const { data } = await apiClient.get<MoverItem[]>(apiConfig.endpoints.marketLosers, {
    params: { limit },
  });
  return data;
}

export async function fetchGlobalMarket(): Promise<GlobalMarket> {
  const { data } = await apiClient.get<GlobalMarket>(apiConfig.endpoints.marketGlobal);
  return data;
}

/** Returns `{ available: false }` (not an error) if the current provider doesn't support trending. */
export async function fetchTrending(): Promise<TrendingResponse> {
  const { data } = await apiClient.get<TrendingResponse>(apiConfig.endpoints.marketTrending);
  return data;
}

/**
 * Historical OHLC candles for one coin. `signal` lets the caller
 * abort a stale request when the user switches timeframe quickly.
 */
export async function fetchCoinHistory(
  coinId: string,
  timeframe: Timeframe,
  signal?: AbortSignal
): Promise<HistoricalPriceResponse> {
  const { data } = await apiClient.get<HistoricalPriceResponse>(apiConfig.endpoints.coinHistory(coinId), {
    params: { timeframe },
    signal,
  });
  return data;
}

/** Highest market-cap coins from synced market data (Phase 7). */
export async function fetchTopByMarketCap(limit = 20): Promise<MoverItem[]> {
  const { data } = await apiClient.get<MoverItem[]>(apiConfig.endpoints.marketTopMarketCap, {
    params: { limit },
  });
  return data;
}

/** Highest 24h-volume coins from synced market data (Phase 7). */
export async function fetchTopByVolume(limit = 20): Promise<MoverItem[]> {
  const { data } = await apiClient.get<MoverItem[]>(apiConfig.endpoints.marketTopVolume, {
    params: { limit },
  });
  return data;
}

/**
 * Binance's own 24h pair stats (Phase 7). Exchange-specific — not a
 * substitute for a coin's cross-market price.
 */
export async function fetchBinanceTickers(limit = 50): Promise<ExchangeTickerResponse> {
  const { data } = await apiClient.get<ExchangeTickerResponse>(apiConfig.endpoints.marketBinanceTickers, {
    params: { limit },
  });
  return data;
}

export interface ListMarketCoinsParams {
  page?: number;
  limit?: number;
  sortBy?: MarketCoinSortField;
  sortDirection?: "asc" | "desc";
  filter?: MarketCoinFilter;
  filters?: MarketCoinFilters;
  /** Restrict to these internal coin ids (watchlist, comparison, trending). */
  coinIds?: string[];
}

/**
 * Paginated Markets-table rows (Phase 8). Sorting and filtering are
 * applied server-side, so the browser never holds the whole coin
 * universe just to paginate it.
 */
export async function fetchMarketCoins(
  params: ListMarketCoinsParams = {}
): Promise<MarketCoinListResponse> {
  const { data } = await apiClient.get<MarketCoinListResponse>(apiConfig.endpoints.marketCoins, {
    params: {
      page: params.page ?? 1,
      limit: params.limit ?? 25,
      sort_by: params.sortBy ?? "market_cap",
      sort_direction: params.sortDirection ?? "desc",
      filter: params.filter ?? "all",
      // Optional filters are only sent when set, so default requests are
      // byte-for-byte what they were before the explorer redesign.
      market_cap_min: params.filters?.marketCapMin,
      market_cap_max: params.filters?.marketCapMax,
      volume_min: params.filters?.volumeMin,
      volume_max: params.filters?.volumeMax,
      change_min: params.filters?.changeMin,
      change_max: params.filters?.changeMax,
      has_max_supply: params.filters?.hasMaxSupply,
      coin_ids: params.coinIds ? params.coinIds.join(",") : undefined,
    },
  });
  return data;
}
