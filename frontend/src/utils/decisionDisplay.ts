import type { DecisionResponse, DecisionStatus, DecisionValue, RiskLevel } from "../types/decisions";

export const DECISION_DISCLAIMER =
  "This decision is generated from available market, technical, fundamental, sentiment, and machine-learning signals. It is not a guarantee of future performance.";

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  VERY_LOW: "Very low",
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  VERY_HIGH: "Very high",
};

export type Tone = "positive" | "negative" | "neutral" | "muted";

export function riskLevelLabel(level: string | null | undefined): string {
  if (!level) return "Unavailable";
  return RISK_LEVEL_LABELS[level as RiskLevel] ?? level;
}

export function riskTone(level: string | null | undefined): Tone {
  if (level === "VERY_LOW" || level === "LOW") return "positive";
  if (level === "HIGH" || level === "VERY_HIGH") return "negative";
  if (level === "MODERATE") return "neutral";
  return "muted";
}

export function decisionTone(decision: DecisionValue | null): Tone {
  if (decision === "BUY") return "positive";
  if (decision === "SELL") return "negative";
  if (decision === "HOLD") return "neutral";
  return "muted";
}

const POSITIVE_SIGNALS = new Set(["BULLISH", "STRONG", "POSITIVE"]);
const NEGATIVE_SIGNALS = new Set(["BEARISH", "WEAK", "NEGATIVE"]);

export function signalTone(signal: string): Tone {
  if (POSITIVE_SIGNALS.has(signal)) return "positive";
  if (NEGATIVE_SIGNALS.has(signal)) return "negative";
  if (signal === "UNAVAILABLE") return "muted";
  return "neutral";
}

/** "BULLISH" -> "Bullish", "VERY_HIGH" -> "Very high", "UNAVAILABLE" -> "Unavailable". */
export function signalLabel(signal: string): string {
  const text = signal.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const TONE_TEXT: Record<Tone, string> = {
  positive: "text-emerald-700 dark:text-emerald-400",
  negative: "text-red-700 dark:text-red-400",
  neutral: "text-amber-700 dark:text-amber-400",
  muted: "text-slate-500 dark:text-slate-400",
};

export const TONE_BADGE: Record<Tone, string> = {
  positive: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
  negative: "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300",
  neutral: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
  muted: "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

export const TONE_BAR: Record<Tone, string> = {
  positive: "bg-emerald-500 dark:bg-emerald-400",
  negative: "bg-red-500 dark:bg-red-400",
  neutral: "bg-amber-500 dark:bg-amber-400",
  muted: "bg-slate-400 dark:bg-slate-500",
};

/** Tone for a 0-100 risk sub-score bar (same bands as the overall risk levels). */
export function riskScoreTone(score: number): Tone {
  if (score >= 61) return "negative";
  if (score >= 41) return "neutral";
  return "positive";
}

/** Signed score for display: +68, -12, 0. */
export function formatSignedScore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unavailable";
  const rounded = Math.round(value);
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

export function formatWholeNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unavailable";
  return String(Math.round(value));
}

export const STATUS_TITLES: Record<Exclude<DecisionStatus, "VALID">, string> = {
  INSUFFICIENT_DATA: "Insufficient data",
  STALE_DATA: "Data is out of date",
  PREDICTION_UNAVAILABLE: "ML prediction unavailable",
  ANALYSIS_UNAVAILABLE: "Analysis unavailable",
};

export function statusTitle(status: DecisionStatus): string {
  return status === "VALID" ? "Decision available" : STATUS_TITLES[status];
}

const MODULE_LABELS: Record<string, string> = {
  market: "Market data",
  technical: "Technical analysis",
  fundamental: "Fundamental analysis",
  sentiment: "Sentiment",
  prediction: "ML prediction",
};

export function moduleLabel(key: string): string {
  return MODULE_LABELS[key] ?? key;
}

/** Inputs that could not be used, with the backend's reason — shown when no decision can be made. */
export function unusableInputs(data: DecisionResponse): { key: string; label: string; reason: string }[] {
  const keys = ["market", "technical", "fundamental", "sentiment", "prediction"] as const;
  return keys
    .filter((key) => !data.data_quality[key].available)
    .map((key) => ({
      key,
      label: moduleLabel(key),
      reason: data.data_quality[key].reason ?? "No usable data.",
    }));
}

/** The prediction was not used, but a decision was still produced from the remaining signals. */
export function predictionMissingButDecided(data: DecisionResponse): boolean {
  return data.status === "VALID" && !data.data_quality.prediction.available;
}

export const PREDICTION_FALLBACK_NOTE = "ML prediction unavailable. Decision calculated using the remaining available signals.";
