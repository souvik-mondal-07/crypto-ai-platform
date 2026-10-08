import type { PredictionHorizon, PredictionListResponse } from "../types/predictions";

export const HORIZON_LABELS: Record<PredictionHorizon, string> = { "1h": "1H", "4h": "4H", "24h": "24H", "7d": "7D", "30d": "30D" };

export const HORIZON_LONG: Record<PredictionHorizon, string> = {
  "1h": "1 hour",
  "4h": "4 hours",
  "24h": "24 hours",
  "7d": "7 days",
  "30d": "30 days",
};

export const DEFAULT_HORIZON: PredictionHorizon = "24h";

export const PREDICTION_DISCLAIMER =
  "This is a machine-learning estimate based on historical data and available features. It is not a guarantee of future performance.";

const MODEL_NAMES: Record<string, string> = {
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  lstm: "LSTM / GRU",
  ridge: "Ridge (linear baseline)",
  ensemble: "Ensemble",
};

export function modelDisplayName(model: string): string {
  return MODEL_NAMES[model] ?? model;
}

/** Where the current price sits inside (or outside) the predicted range, 0-100. */
export function markerPosition(current: number, lower: number, upper: number): number {
  const lo = Math.min(lower, current);
  const hi = Math.max(upper, current);
  if (hi === lo) return 50;
  return ((current - lo) / (hi - lo)) * 100;
}

/** Which horizon to show: the user's pick if still available, else 24h, else the first available. */
export function chooseHorizon(selected: PredictionHorizon | null, available: PredictionHorizon[]): PredictionHorizon | null {
  if (selected && available.includes(selected)) return selected;
  if (available.includes(DEFAULT_HORIZON)) return DEFAULT_HORIZON;
  return available[0] ?? null;
}

/** Why nothing can be shown: distinguishes "no history" from "no trained model". */
export function describeUnavailable(data: PredictionListResponse): { title: string; reason: string } {
  const insufficient = data.unavailable.find((u) => u.status === "insufficient_data");
  if (insufficient) return { title: "Insufficient historical data", reason: insufficient.reason };
  const model = data.unavailable.find((u) => u.status === "model_unavailable");
  if (model) {
    return {
      title: "Prediction unavailable",
      reason:
        "No validated prediction model is available for this coin yet. Models are trained explicitly and are only used once they pass held-out checks.",
    };
  }
  return { title: "Prediction unavailable", reason: "No prediction could be produced for this coin." };
}
