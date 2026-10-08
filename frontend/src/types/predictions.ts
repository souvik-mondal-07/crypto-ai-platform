/**
 * Prediction types — kept in sync with backend/app/schemas/predictions.py.
 * Every value is a MODEL ESTIMATE, never a market fact.
 */

export type PredictionHorizon = "1h" | "4h" | "24h" | "7d" | "30d";
export type PredictionDirection = "up" | "down" | "flat";
export type ConfidenceStatus = "calibrated" | "unavailable";
export type UnavailableStatus = "model_unavailable" | "insufficient_data";

export interface RangeBounds {
  lower: number;
  upper: number;
}

export interface ModelEvaluation {
  test_mae: number | null;
  baseline_mae: number | null;
  test_directional_accuracy: number | null;
  test_samples: number | null;
  interval_coverage_test: number | null;
}

export interface PredictionResponse {
  coin_id: string;
  symbol: string | null;
  horizon: PredictionHorizon;
  kind: "model_prediction";
  /** Close of the last completed candle the forecast starts from. */
  current_price: number;
  reference_time: string;
  target_time: string;
  /** Fractional return: 0.024 == +2.4%. */
  predicted_return: number;
  predicted_return_range: RangeBounds | null;
  predicted_price_range: RangeBounds | null;
  range_nominal_coverage: number | null;
  direction: PredictionDirection;
  /** Calibrated probability that the predicted direction is correct; null when unavailable. */
  confidence: number | null;
  confidence_status: ConfidenceStatus;
  confidence_note: string | null;
  model: string;
  model_version: string;
  feature_version: string;
  evaluation: ModelEvaluation | null;
  trained_at: string | null;
  generated_at: string;
  expires_at: string;
  is_stale: boolean;
  disclaimer: string;
}

export interface UnavailableHorizon {
  horizon: PredictionHorizon;
  status: UnavailableStatus;
  reason: string;
}

export interface PredictionListResponse {
  coin_id: string;
  symbol: string | null;
  predictions: PredictionResponse[];
  unavailable: UnavailableHorizon[];
  generated_at: string;
  disclaimer: string;
}

export const PREDICTION_HORIZONS: readonly PredictionHorizon[] = ["1h", "4h", "24h", "7d", "30d"];
