/**
 * Risk & Decision types — kept in sync with backend/app/schemas/decisions.py.
 * A decision is MODEL-BASED decision support, never a guarantee and never an order.
 */

export type DecisionValue = "BUY" | "HOLD" | "SELL";
export type RiskLevel = "VERY_LOW" | "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";
export type DecisionStatus =
  | "VALID"
  | "INSUFFICIENT_DATA"
  | "STALE_DATA"
  | "PREDICTION_UNAVAILABLE"
  | "ANALYSIS_UNAVAILABLE";
export type ModuleState = "available" | "missing" | "stale" | "insufficient_data" | "unavailable";
export type ConfidenceStatusValue = "computed" | "unavailable";

export interface RiskSubFactor {
  key: string;
  label: string;
  /** Raw input behind the sub-score (null for categorical inputs). */
  value: number | null;
  /** 0-100, higher = riskier. */
  score: number;
  weight: number;
}

export interface RiskComponent {
  key: string;
  label: string;
  weight: number;
  available: boolean;
  score: number | null;
  /** Points this component adds to the final risk score. */
  contribution: number | null;
  reason: string | null;
  factors: RiskSubFactor[];
}

export interface RiskDetail {
  available: boolean;
  score: number | null;
  level: RiskLevel | null;
  coverage_percent: number;
  components: RiskComponent[];
  positive_factors: string[];
  negative_factors: string[];
  reason: string | null;
  config_version: string;
}

export interface DecisionSignals {
  /** BULLISH | NEUTRAL | BEARISH | UNAVAILABLE */
  technical: string;
  /** STRONG | NEUTRAL | WEAK | UNAVAILABLE */
  fundamental: string;
  /** POSITIVE | NEUTRAL | NEGATIVE | UNAVAILABLE */
  sentiment: string;
  /** BULLISH | NEUTRAL | BEARISH | UNAVAILABLE */
  prediction: string;
  /** VERY_LOW | LOW | MODERATE | HIGH | VERY_HIGH | UNAVAILABLE */
  risk: string;
}

export interface SignalScores {
  technical: number | null;
  fundamental: number | null;
  sentiment: number | null;
  prediction: number | null;
}

export interface DecisionOverride {
  rule: string;
  description: string;
}

export interface SignalAgreement {
  cross_module: number | null;
  intra_module: number | null;
  conflict_share: number;
  conflicting: boolean;
  bullish_modules: number;
  bearish_modules: number;
  neutral_modules: number;
}

export interface ModuleQuality {
  available: boolean;
  state: ModuleState;
  reason: string | null;
  as_of: string | null;
}

export interface DataQuality {
  market: ModuleQuality;
  technical: ModuleQuality;
  fundamental: ModuleQuality;
  sentiment: ModuleQuality;
  prediction: ModuleQuality;
  summary: {
    usable_modules: string[];
    module_coverage_percent: number;
    risk_coverage_percent: number;
    prediction_available: boolean;
  };
}

export interface DecisionResponse {
  coin_id: string;
  symbol: string | null;
  kind: "model_based_decision";
  /** Null (with an explanatory `status`) when the data cannot support an honest decision. */
  decision: DecisionValue | null;
  status: DecisionStatus;
  status_reason: string | null;
  /** Risk-adjusted combined score, -100..+100. */
  decision_score: number | null;
  raw_score: number | null;
  risk_adjustment: number | null;
  /** 0-100; null with confidence_status "unavailable" when it cannot be established. */
  confidence: number | null;
  confidence_status: ConfidenceStatusValue;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  risk: RiskDetail;
  signals: DecisionSignals;
  signal_scores: SignalScores;
  module_weights: Record<string, number>;
  positive_factors: string[];
  negative_factors: string[];
  base_decision: DecisionValue | null;
  overrides: DecisionOverride[];
  agreement: SignalAgreement;
  data_quality: DataQuality;
  warnings: string[];
  explanation: string[];
  generated_at: string;
  expires_at: string;
  /** True when expires_at has passed (only possible on /latest). */
  is_stale: boolean;
  engine_version: string;
  risk_config_version: string;
  disclaimer: string;
}
