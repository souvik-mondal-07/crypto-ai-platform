import { apiClient } from "./client";
import { apiConfig } from "../../config/api.config";
import type { AiAnalysisResponse } from "../../types/aiAnalysis";

/**
 * The latest STORED AI explanation for a coin. Never triggers Gemini; rejects with a 404
 * `AI_ANALYSIS_NOT_FOUND` ApiError when none has been generated yet.
 */
export async function fetchAiAnalysis(coinId: string, options: { signal?: AbortSignal } = {}): Promise<AiAnalysisResponse> {
  const { data } = await apiClient.get<AiAnalysisResponse>(apiConfig.endpoints.coinAiAnalysis(coinId), {
    signal: options.signal,
  });
  return data;
}

/**
 * Ask the backend for an explanation. It returns a fresh stored one when it has it (no Gemini call),
 * otherwise generates one; `forceRefresh` asks for a new one (the backend enforces a cooldown).
 * Only the backend ever talks to Gemini — the browser never sees an AI key.
 */
export async function generateAiAnalysis(
  coinId: string,
  options: { forceRefresh?: boolean; signal?: AbortSignal } = {},
): Promise<AiAnalysisResponse> {
  const { data } = await apiClient.post<AiAnalysisResponse>(apiConfig.endpoints.coinAiAnalysisGenerate(coinId), undefined, {
    params: options.forceRefresh ? { force_refresh: true } : undefined,
    signal: options.signal,
    timeout: apiConfig.aiGenerationTimeout,
  });
  return data;
}
