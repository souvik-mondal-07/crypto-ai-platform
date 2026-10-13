import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { WatchlistResponse, WatchlistStatus } from "../../types/userFeatures";

/** Watchlist HTTP calls. The user is identified by the JWT the shared client attaches — never sent in a body. */
export const watchlistApi = {
  async list(page = 1, limit = 250): Promise<WatchlistResponse> {
    const { data } = await apiClient.get<WatchlistResponse>(apiConfig.endpoints.watchlist, { params: { page, limit } });
    return data;
  },
  async add(coinId: string): Promise<void> {
    await apiClient.post(apiConfig.endpoints.watchlist, { coin_id: coinId });
  },
  async remove(coinId: string): Promise<void> {
    await apiClient.delete(apiConfig.endpoints.watchlistCoin(coinId));
  },
  async status(coinId: string): Promise<WatchlistStatus> {
    const { data } = await apiClient.get<WatchlistStatus>(apiConfig.endpoints.watchlistCoin(coinId));
    return data;
  },
};
