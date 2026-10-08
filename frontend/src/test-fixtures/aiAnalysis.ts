/**
 * Test-only builders for AI analysis responses. Fixtures for the test suite — the application never
 * imports this file. All text and numbers are synthetic.
 */
import type { AiAnalysisContent, AiAnalysisResponse } from "../types/aiAnalysis";

export const AI_DISCLAIMER_TEXT =
  "AI-generated analysis is for informational purposes only and is not a guarantee of future performance or financial advice.";

export function buildAiContent(overrides: Partial<AiAnalysisContent> = {}): AiAnalysisContent {
  return {
    summary: "Synthetic summary: the platform's engine rates this coin BUY with low risk.",
    market_analysis: "Synthetic market interpretation.",
    technical_analysis: "Synthetic technical explanation.",
    fundamental_analysis: "Synthetic fundamental explanation.",
    sentiment_analysis: "Synthetic sentiment explanation.",
    prediction_analysis: "Synthetic prediction explanation.",
    risk_analysis: "Synthetic risk explanation.",
    decision_explanation: "Synthetic explanation of why the official decision is BUY.",
    bullish_factors: ["Synthetic bullish factor"],
    bearish_factors: ["Synthetic bearish factor"],
    key_risks: ["Synthetic key risk"],
    uncertainties: ["Synthetic uncertainty"],
    data_quality: "Synthetic data quality note.",
    disclaimer: AI_DISCLAIMER_TEXT,
    ...overrides,
  };
}

export function buildAiAnalysis(overrides: Partial<AiAnalysisResponse> = {}): AiAnalysisResponse {
  const now = Date.now();
  return {
    coin_id: "507f1f77bcf86cd799439011",
    symbol: "UNC",
    kind: "ai_explanation",
    status: "ready",
    analysis: buildAiContent(),
    decision_snapshot: {
      decision: "BUY",
      status: "VALID",
      risk_level: "LOW",
      risk_score: 34,
      confidence: 78,
      decision_score: 68,
      engine_version: "1.0",
      generated_at: new Date(now - 60_000).toISOString(),
    },
    data_availability: {
      market: { available: true, reason: null },
      technical: { available: true, reason: null },
      prediction: { available: true, reason: null },
    },
    model: "gemini-3.1-flash-lite",
    model_version: null,
    prompt_version: "1.0",
    source_data_timestamp: new Date(now - 60_000).toISOString(),
    generated_at: new Date(now - 30_000).toISOString(),
    expires_at: new Date(now + 1_800_000).toISOString(),
    is_stale: false,
    is_outdated: false,
    cached: true,
    next_regeneration_at: null,
    disclaimer: AI_DISCLAIMER_TEXT,
    ...overrides,
  };
}
