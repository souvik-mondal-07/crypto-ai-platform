import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { Holding, HoldingCreate, HoldingUpdate, Portfolio, TransactionList } from "../../types/userFeatures";

export const portfolioApi = {
  async get(): Promise<Portfolio> {
    const { data } = await apiClient.get<Portfolio>(apiConfig.endpoints.portfolio);
    return data;
  },
  async add(payload: HoldingCreate): Promise<Holding> {
    const { data } = await apiClient.post<Holding>(apiConfig.endpoints.portfolio, payload);
    return data;
  },
  async update(coinId: string, payload: HoldingUpdate): Promise<Holding> {
    const { data } = await apiClient.put<Holding>(apiConfig.endpoints.portfolioHolding(coinId), payload);
    return data;
  },
  async remove(coinId: string): Promise<void> {
    await apiClient.delete(apiConfig.endpoints.portfolioHolding(coinId));
  },
  async transactions(page = 1, limit = 20, coinId?: string): Promise<TransactionList> {
    const { data } = await apiClient.get<TransactionList>(apiConfig.endpoints.portfolioTransactions, {
      params: { page, limit, ...(coinId ? { coin_id: coinId } : {}) },
    });
    return data;
  },
};
