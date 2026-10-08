import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { PredictionListResponse } from "../../types/predictions";

/**
 * Every horizon that currently has a valid model prediction for the coin (plus the
 * reasons the others don't). Predictions are generated server-side from trained
 * models; this call never trains anything.
 */
export async function fetchCoinPredictions(coinId: string, signal?: AbortSignal): Promise<PredictionListResponse> {
  const { data } = await apiClient.get<PredictionListResponse>(apiConfig.endpoints.coinPredictions(coinId), { signal });
  return data;
}
