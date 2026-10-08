import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { Timeframe } from "../../types/market";
import type { TechnicalAnalysisResponse } from "../../types/technicalAnalysis";

/**
 * RSI/MACD/moving averages/Bollinger Bands/ATR/volume/support-
 * resistance/trend for one coin, computed from real historical OHLC
 * candles server-side (see backend/app/services/technical_analysis_service.py).
 * Results are cached server-side for a few minutes, so calling this
 * again for the same coin/timeframe shortly after is cheap.
 */
export async function fetchTechnicalAnalysis(
  coinId: string,
  timeframe: Timeframe,
  signal?: AbortSignal
): Promise<TechnicalAnalysisResponse> {
  const { data } = await apiClient.get<TechnicalAnalysisResponse>(
    apiConfig.endpoints.coinTechnicalAnalysis(coinId),
    { params: { timeframe }, signal }
  );
  return data;
}
