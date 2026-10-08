import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { DecisionResponse } from "../../types/decisions";

/**
 * Risk & Decision for a coin. The backend returns a stored decision while it is fresh and
 * recalculates (deterministically, from existing analysis data) when it has expired; this call
 * never trains a model. `forceRefresh` asks for a recalculation now.
 */
export async function fetchDecision(
  coinId: string,
  options: { forceRefresh?: boolean; signal?: AbortSignal } = {},
): Promise<DecisionResponse> {
  const { data } = await apiClient.get<DecisionResponse>(apiConfig.endpoints.coinDecision(coinId), {
    params: options.forceRefresh ? { force_refresh: true } : undefined,
    signal: options.signal,
  });
  return data;
}
