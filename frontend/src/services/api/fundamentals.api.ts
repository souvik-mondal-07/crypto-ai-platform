import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { FundamentalAnalysisResponse } from "../../types/fundamentals";

/**
 * Provider-reported fundamentals, platform-calculated metrics, the
 * rule-based fundamental score and a factual summary for one coin (see
 * backend/app/services/fundamental_analysis_service.py).
 *
 * Project/ecosystem data is cached server-side; `forceRefresh` asks the
 * backend to re-fetch it, which the backend still rate-limits per coin.
 */
export async function fetchFundamentals(
  coinId: string,
  options: { forceRefresh?: boolean; signal?: AbortSignal } = {}
): Promise<FundamentalAnalysisResponse> {
  const { data } = await apiClient.get<FundamentalAnalysisResponse>(
    apiConfig.endpoints.coinFundamentals(coinId),
    {
      params: options.forceRefresh ? { force_refresh: true } : undefined,
      signal: options.signal,
    }
  );
  return data;
}
