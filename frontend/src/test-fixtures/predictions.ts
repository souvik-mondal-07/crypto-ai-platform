/**
 * Test-only builders for prediction responses. Fixtures for the test suite — the
 * application never imports this file. All numbers are synthetic.
 */
import type {
  PredictionHorizon, PredictionListResponse, PredictionResponse, UnavailableHorizon,
} from "../types/predictions";

export function buildPrediction(overrides: Partial<PredictionResponse> = {}): PredictionResponse {
  const now = Date.now();
  return {
    coin_id: "507f1f77bcf86cd799439011",
    symbol: "UNC",
    horizon: "24h",
    kind: "model_prediction",
    current_price: 100,
    reference_time: new Date(now - 20 * 60 * 1000).toISOString(),
    target_time: new Date(now + 24 * 3600 * 1000).toISOString(),
    predicted_return: 0.024,
    predicted_return_range: { lower: 0.012, upper: 0.04 },
    predicted_price_range: { lower: 101.2, upper: 104 },
    range_nominal_coverage: 0.8,
    direction: "up",
    confidence: 0.71,
    confidence_status: "calibrated",
    confidence_note: null,
    model: "xgboost",
    model_version: "v3",
    feature_version: "v1",
    evaluation: {
      test_mae: 0.011, baseline_mae: 0.013, test_directional_accuracy: 0.574, test_samples: 412, interval_coverage_test: 0.78,
    },
    trained_at: new Date(now - 86400 * 1000).toISOString(),
    generated_at: new Date(now - 60 * 1000).toISOString(),
    expires_at: new Date(now + 14 * 60 * 1000).toISOString(),
    is_stale: false,
    disclaimer:
      "This is a machine-learning estimate based on historical data and available features. It is not a guarantee of future performance.",
    ...overrides,
  };
}

export function buildPredictionList(
  predictions: PredictionResponse[] = [buildPrediction()],
  unavailable: UnavailableHorizon[] = [],
): PredictionListResponse {
  return {
    coin_id: "507f1f77bcf86cd799439011",
    symbol: "UNC",
    predictions,
    unavailable,
    generated_at: new Date().toISOString(),
    disclaimer: predictions[0]?.disclaimer ?? "",
  };
}

export function buildUnavailable(
  horizon: PredictionHorizon,
  status: UnavailableHorizon["status"],
  reason = "reason",
): UnavailableHorizon {
  return { horizon, status, reason };
}
