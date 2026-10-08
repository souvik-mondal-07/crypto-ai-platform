import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { Coin, CoinListResponse, CoinSearchResponse } from "../../types/coin";

export interface ListCoinsParams {
  page?: number;
  limit?: number;
  activeOnly?: boolean;
  provider?: "coingecko" | "binance";
  sortBy?: "name" | "symbol" | "market_cap_rank" | "updated_at";
  sortDirection?: "asc" | "desc";
}

/**
 * Paginated coin listing — the full synchronized coin universe, not a
 * hard-coded top-N. Throws (via the apiClient interceptor) on failure;
 * callers translate that into UI error state.
 */
export async function fetchCoins(params: ListCoinsParams = {}): Promise<CoinListResponse> {
  const { data } = await apiClient.get<CoinListResponse>(apiConfig.endpoints.coins, {
    params: {
      page: params.page ?? 1,
      limit: params.limit ?? 100,
      active_only: params.activeOnly ?? true,
      provider: params.provider,
      sort_by: params.sortBy ?? "market_cap_rank",
      sort_direction: params.sortDirection ?? "asc",
    },
  });
  return data;
}

/**
 * Backend-driven search — calls GET /coins/search?q=... on every
 * invocation. Callers are responsible for debouncing keystrokes; this
 * function never filters a local/hard-coded array.
 */
export async function searchCoins(query: string, limit = 20): Promise<CoinSearchResponse> {
  const { data } = await apiClient.get<CoinSearchResponse>(apiConfig.endpoints.coinsSearch, {
    params: { q: query, limit },
  });
  return data;
}

export async function fetchCoinById(coinId: string): Promise<Coin> {
  const { data } = await apiClient.get<Coin>(apiConfig.endpoints.coinById(coinId));
  return data;
}
