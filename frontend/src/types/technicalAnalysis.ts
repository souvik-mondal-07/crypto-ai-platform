/**
 * Mirrors backend/app/schemas/technical_analysis.py exactly — the
 * backend is the source of truth for these shapes.
 */

export type RsiZone = "overbought" | "oversold" | "neutral";

export interface RsiData {
  period: number;
  current: number | null;
  zone: RsiZone | null;
  history: (number | null)[];
}

export interface MacdPoint {
  timestamp: string;
  macd: number | null;
  signal: number | null;
  histogram: number | null;
}

export type MacdCrossover = "bullish_crossover" | "bearish_crossover" | "none";

export interface MacdData {
  fast_period: number;
  slow_period: number;
  signal_period: number;
  current: MacdPoint;
  crossover: MacdCrossover;
  history: MacdPoint[];
}

export interface MovingAverages {
  /** Keyed by period, e.g. { "20": 65000, "50": 64200, "200": null }. */
  sma: Record<string, number | null>;
  ema: Record<string, number | null>;
}

export interface BollingerBandsData {
  period: number;
  num_std_dev: number;
  upper: number | null;
  middle: number | null;
  lower: number | null;
}

export interface AtrData {
  period: number;
  current: number | null;
  history: (number | null)[];
}

export interface VolumeAnalysis {
  current_volume_24h_usd: number | null;
  historical_volume: { timestamp: string; volume: number }[];
  average_volume: number | null;
  volume_change_percent: number | null;
  trend: "increasing" | "decreasing" | "neutral" | "unavailable";
  historical_volume_source: string | null;
}
export interface SupportResistanceData {
  support_levels: number[];
  resistance_levels: number[];
}

export type TrendLabel = "bullish" | "bearish" | "neutral";

export interface TrendAnalysis {
  trend: TrendLabel;
  signals_considered: number;
}

export interface TechnicalAnalysisResponse {
  coin_id: string;
  symbol: string;
  timeframe: string;
  calculated_at: string;
  candle_count: number;
  rsi: RsiData;
  macd: MacdData;
  moving_averages: MovingAverages;
  bollinger_bands: BollingerBandsData;
  atr: AtrData;
  volume: VolumeAnalysis;
  support_resistance: SupportResistanceData;
  trend: TrendAnalysis;
  data_source: string;
}
