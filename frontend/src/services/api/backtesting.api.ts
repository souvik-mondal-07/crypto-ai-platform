import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type {
  AccuracyFilters,
  AccuracyResponse,
  BacktestConfig,
  BacktestRequest,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestTrade,
  DecisionEvaluation,
  Paged,
  RefreshState,
} from "../../types/backtesting";

const { endpoints } = apiConfig;

/** `model|version` -> API query params (the version is optional). */
export function splitModelVersion(key: string): { model?: string; model_version?: string } {
  if (!key) return {};
  const [model, version] = key.split("|");
  return { model, ...(version ? { model_version: version } : {}) };
}

export const backtestingApi = {
  async config(): Promise<BacktestConfig> {
    const { data } = await apiClient.get<BacktestConfig>(endpoints.backtestingConfig);
    return data;
  },
  async accuracy(filters: Partial<AccuracyFilters> = {}): Promise<AccuracyResponse> {
    const params = {
      ...(filters.horizon ? { horizon: filters.horizon } : {}),
      ...(filters.coinId ? { coin_id: filters.coinId } : {}),
      ...splitModelVersion(filters.modelVersion ?? ""),
    };
    const { data } = await apiClient.get<AccuracyResponse>(endpoints.backtestingAccuracy, { params });
    return data;
  },
  async refreshOutcomes(): Promise<RefreshState> {
    const { data } = await apiClient.post<RefreshState>(endpoints.backtestingAccuracyRefresh);
    return data;
  },
  async refreshStatus(): Promise<RefreshState> {
    const { data } = await apiClient.get<RefreshState>(endpoints.backtestingAccuracyRefresh);
    return data;
  },
  async decisions(horizon?: string): Promise<DecisionEvaluation> {
    const { data } = await apiClient.get<DecisionEvaluation>(endpoints.backtestingDecisions, {
      params: horizon ? { horizon } : {},
    });
    return data;
  },
  async createRun(body: BacktestRequest): Promise<BacktestRunSummary> {
    const { data } = await apiClient.post<BacktestRunSummary>(endpoints.backtestingRuns, body);
    return data;
  },
  async listRuns(page = 1, limit = 10): Promise<Paged<BacktestRunSummary>> {
    const { data } = await apiClient.get<Paged<BacktestRunSummary>>(endpoints.backtestingRuns, { params: { page, limit } });
    return data;
  },
  async getRun(runId: string): Promise<BacktestRunDetail> {
    const { data } = await apiClient.get<BacktestRunDetail>(endpoints.backtestingRun(runId));
    return data;
  },
  async runTrades(runId: string, page = 1, limit = 25): Promise<Paged<BacktestTrade>> {
    const { data } = await apiClient.get<Paged<BacktestTrade>>(endpoints.backtestingRunTrades(runId), { params: { page, limit } });
    return data;
  },
};
