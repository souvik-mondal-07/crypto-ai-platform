import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { AnalysisType, HistoryEntry, HistoryList } from "../../types/userFeatures";

export interface HistoryQuery {
  page?: number;
  limit?: number;
  coinId?: string;
  analysisType?: AnalysisType;
}

export const historyApi = {
  async list(query: HistoryQuery = {}): Promise<HistoryList> {
    const { data } = await apiClient.get<HistoryList>(apiConfig.endpoints.history, {
      params: {
        page: query.page ?? 1,
        limit: query.limit ?? 20,
        ...(query.coinId ? { coin_id: query.coinId } : {}),
        ...(query.analysisType ? { analysis_type: query.analysisType } : {}),
      },
    });
    return data;
  },
  async record(coinId: string, analysisType: AnalysisType): Promise<HistoryEntry> {
    const { data } = await apiClient.post<HistoryEntry>(apiConfig.endpoints.history, {
      coin_id: coinId,
      analysis_type: analysisType,
    });
    return data;
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(apiConfig.endpoints.historyEntry(id));
  },
};
