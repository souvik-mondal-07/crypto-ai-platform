/**
 * Test-only builders for decision responses. Fixtures for the test suite — the application never
 * imports this file. All numbers are synthetic.
 */
import type { DataQuality, DecisionResponse, ModuleQuality } from "../types/decisions";

const AVAILABLE: ModuleQuality = { available: true, state: "available", reason: null, as_of: null };

export function unavailableModule(reason: string, state: ModuleQuality["state"] = "unavailable"): ModuleQuality {
  return { available: false, state, reason, as_of: null };
}

export function buildDataQuality(overrides: Partial<DataQuality> = {}): DataQuality {
  return {
    market: AVAILABLE,
    technical: AVAILABLE,
    fundamental: AVAILABLE,
    sentiment: AVAILABLE,
    prediction: AVAILABLE,
    summary: {
      usable_modules: ["technical", "fundamental", "sentiment", "prediction"],
      module_coverage_percent: 100,
      risk_coverage_percent: 100,
      prediction_available: true,
    },
    ...overrides,
  };
}

export function buildDecision(overrides: Partial<DecisionResponse> = {}): DecisionResponse {
  const now = Date.now();
  return {
    coin_id: "507f1f77bcf86cd799439011",
    symbol: "UNC",
    kind: "model_based_decision",
    decision: "BUY",
    status: "VALID",
    status_reason: null,
    decision_score: 68,
    raw_score: 68,
    risk_adjustment: 0,
    confidence: 78,
    confidence_status: "computed",
    risk_score: 34,
    risk_level: "LOW",
    risk: {
      available: true,
      score: 34,
      level: "LOW",
      coverage_percent: 100,
      components: [
        { key: "volatility", label: "Volatility", weight: 0.25, available: true, score: 45, contribution: 11.3, reason: null, factors: [] },
        { key: "prediction", label: "ML prediction", weight: 0.15, available: false, score: null, contribution: null, reason: "No usable ML prediction is available.", factors: [] },
      ],
      positive_factors: ["Strong liquidity: 24h volume is $2.0B"],
      negative_factors: ["Wide Bollinger Bands (30.0% of the middle band) indicate high historical volatility"],
      reason: null,
      config_version: "1.0",
    },
    signals: { technical: "BULLISH", fundamental: "STRONG", sentiment: "POSITIVE", prediction: "BULLISH", risk: "LOW" },
    signal_scores: { technical: 40, fundamental: 50, sentiment: 30, prediction: 45 },
    module_weights: { technical: 0.35, fundamental: 0.2, sentiment: 0.15, prediction: 0.3 },
    positive_factors: ["Positive MACD momentum", "Price is above 5 of 5 key moving averages", "Positive recent news sentiment"],
    negative_factors: ["Wide Bollinger Bands (30.0% of the middle band) indicate high historical volatility"],
    base_decision: "BUY",
    overrides: [],
    agreement: {
      cross_module: 1, intra_module: 1, conflict_share: 0, conflicting: false,
      bullish_modules: 4, bearish_modules: 0, neutral_modules: 0,
    },
    data_quality: buildDataQuality(),
    warnings: [],
    explanation: ["Decision: BUY. The combined signal score is +68.0 (BUY at +25 or higher, SELL at -25 or lower).", "Risk is low (34/100)."],
    generated_at: new Date(now - 60 * 1000).toISOString(),
    expires_at: new Date(now + 4 * 60 * 1000).toISOString(),
    is_stale: false,
    engine_version: "1.0",
    risk_config_version: "1.0",
    disclaimer:
      "This decision is generated from available market, technical, fundamental, sentiment, and machine-learning signals. It is not a guarantee of future performance.",
    ...overrides,
  };
}

export function buildInsufficientDecision(reason = "Only 1 of the 4 analysis modules have usable data; at least 2 are required."): DecisionResponse {
  return buildDecision({
    decision: null,
    status: "INSUFFICIENT_DATA",
    status_reason: reason,
    decision_score: null,
    raw_score: null,
    risk_adjustment: null,
    confidence: null,
    confidence_status: "unavailable",
    risk_score: null,
    risk_level: null,
    risk: { available: false, score: null, level: null, coverage_percent: 60, components: [], positive_factors: [], negative_factors: [], reason, config_version: "1.0" },
    signals: { technical: "BULLISH", fundamental: "UNAVAILABLE", sentiment: "UNAVAILABLE", prediction: "UNAVAILABLE", risk: "UNAVAILABLE" },
    signal_scores: { technical: 40, fundamental: null, sentiment: null, prediction: null },
    positive_factors: [],
    negative_factors: [],
    base_decision: null,
    explanation: [],
    data_quality: buildDataQuality({
      fundamental: unavailableModule("Not enough fundamental data is available for this coin.", "insufficient_data"),
      sentiment: unavailableModule("Too few analysed news articles to describe sentiment (1 analysed, 3 needed).", "insufficient_data"),
      prediction: unavailableModule("The prediction engine is not available on the server right now."),
    }),
  });
}

/** A valid decision made without the ML prediction. */
export function buildDecisionWithoutPrediction(): DecisionResponse {
  return buildDecision({
    signals: { technical: "BULLISH", fundamental: "STRONG", sentiment: "POSITIVE", prediction: "UNAVAILABLE", risk: "LOW" },
    signal_scores: { technical: 40, fundamental: 50, sentiment: 30, prediction: null },
    data_quality: buildDataQuality({
      prediction: unavailableModule("The prediction engine is not available on the server right now."),
      summary: { usable_modules: ["technical", "fundamental", "sentiment"], module_coverage_percent: 70, risk_coverage_percent: 85, prediction_available: false },
    }),
    warnings: ["ML prediction unavailable (The prediction engine is not available on the server right now). Decision calculated using the remaining available signals."],
  });
}
