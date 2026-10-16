/** Mirrors backend/app/schemas/backtesting.py. Every metric that cannot be computed honestly is `null`. */

export type MetricStatus = "ok" | "insufficient_data" | "no_data";
export type RunStatus = "queued" | "running" | "completed" | "failed";
export type ResultStatus = "ok" | "insufficient_data";
export type BarInterval = "1h" | "4h" | "1d";
export type SizingMode = "fixed_fraction" | "fixed_amount";
export type DecisionKind = "BUY" | "HOLD" | "SELL";

// ------------------------------------------------------------------ model accuracy
export interface AccuracyMetrics {
  status: MetricStatus;
  sample_size: number;
  min_samples: number;
  period_start: string | null;
  period_end: string | null;
  directional_accuracy: number | null;
  directional_sample_size: number;
  flat_predictions_excluded: number;
  mae: number | null;
  rmse: number | null;
  mean_error: number | null;
  baseline_zero_mae: number | null;
  mae_vs_zero_baseline: number | null;
  mean_predicted_return: number | null;
  mean_actual_return: number | null;
  range_coverage: number | null;
  range_sample_size: number;
  nominal_coverage: number | null;
  message: string | null;
}

export interface HorizonAccuracy extends AccuracyMetrics {
  horizon: string;
}
export interface ModelAccuracy extends AccuracyMetrics {
  model: string | null;
  model_version: string | null;
}
export interface CoinAccuracy extends AccuracyMetrics {
  coin_id: string;
  symbol: string | null;
}

export interface AccuracyCoverage {
  total_predictions: number;
  matured_predictions: number;
  matched_outcomes: number;
  pending_outcomes: number;
  duplicates_removed: number;
  unmatched_by_status: Record<string, number>;
}

export interface AccuracyOptions {
  horizons: string[];
  models: string[];
  model_versions: { model: string; model_version: string | null }[];
  coins: { id: string; symbol: string }[];
}

export interface AccuracyResponse {
  methodology_version: string;
  generated_at: string;
  filters: { coin_id: string | null; horizon: string | null; model: string | null; model_version: string | null };
  coin: { id: string; symbol: string | null; name: string | null } | null;
  overall: AccuracyMetrics;
  by_horizon: HorizonAccuracy[];
  by_model: ModelAccuracy[];
  by_coin: CoinAccuracy[];
  coverage: AccuracyCoverage;
  options: AccuracyOptions;
  limitations: string[];
}

export interface AccuracyFilters {
  horizon: string;
  /** `model|version` as built by `modelVersionKey`, or "" for all. */
  modelVersion: string;
  coinId: string;
}

export interface RefreshState {
  running: boolean;
  accepted: boolean;
  message: string | null;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_error: string | null;
  last_report: Record<string, unknown> | null;
}

// ------------------------------------------------------------------ decision evaluation
export interface DecisionCell {
  decision: DecisionKind;
  horizon: string;
  count: number;
  status: MetricStatus;
  mean_return: number | null;
  median_return: number | null;
  directional_agreement: number | null;
  within_neutral_band_rate: number | null;
}
export interface PooledDirectional {
  horizon: string;
  count: number;
  status: MetricStatus;
  directional_agreement: number | null;
}
export interface DecisionEvaluation {
  methodology_version: string;
  generated_at: string;
  filters: { coin_id: string | null; horizon: string | null };
  horizons: string[];
  total_decisions_stored: number;
  decision_counts: Record<string, number>;
  metrics: {
    evaluated_decisions: number;
    evaluations: number;
    by_decision_horizon: DecisionCell[];
    pooled_directional: PooledDirectional[];
    period_start: string | null;
    period_end: string | null;
    min_samples: number;
    hold_neutral_band: Record<string, number>;
  };
  limitations: string[];
}

// ------------------------------------------------------------------ backtests
export interface BacktestRequest {
  coin_ids: string[];
  start: string;
  end: string;
  starting_capital: number;
  bar_interval: BarInterval;
  sizing_mode: SizingMode;
  position_size: number;
  max_allocation_pct: number;
  fee_rate: number;
  slippage_rate: number;
  close_open_positions_at_end: boolean;
}

export interface CostAssumptions {
  engine_version: string;
  strategy: string;
  strategy_version: string;
  bar_interval: string;
  sizing_mode: string;
  position_size: number;
  max_allocation_pct: number;
  fee_rate: number;
  slippage_rate: number;
  execution: string;
  long_only: boolean;
  leverage: number;
  close_open_positions_at_end: boolean;
  risk_free_rate_annual: number;
  benchmark: string;
  benchmark_costs: string;
}

export interface BacktestSummaryMetrics {
  initial_value: number | null;
  final_value: number | null;
  total_return: number | null;
  annualized_return: number | null;
  max_drawdown: number | null;
  number_of_trades: number;
  number_of_fills: number;
  win_rate: number | null;
  average_win_return: number | null;
  average_loss_return: number | null;
  total_fees: number | null;
  estimated_slippage: number | null;
  total_costs: number | null;
  benchmark_final_value: number | null;
  benchmark_return: number | null;
  sharpe_ratio: number | null;
  sharpe_note: string | null;
  skipped_signals: Record<string, number>;
  period_start: string | null;
  period_end: string | null;
  bars: number | null;
  decisions_in_period: number | null;
}

export interface EquityPoint {
  time: string;
  value: number;
}

export interface BacktestTrade {
  coin_id: string;
  symbol: string | null;
  side: "BUY" | "SELL";
  reason: string;
  decision_id: string | null;
  decision_time: string | null;
  execution_time: string;
  price: number;
  reference_price: number;
  quantity: number;
  notional: number;
  fee: number;
  slippage_cost: number;
  cash_after: number;
}

export interface CoinDataSummary {
  coin_id: string;
  symbol: string | null;
  bars: number;
  decisions: number;
  note: string | null;
}

export interface BacktestRunSummary {
  run_id: string;
  status: RunStatus;
  result_status: ResultStatus | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  engine_version: string;
  strategy: string;
  coin_ids: string[];
  symbols: string[];
  period_start: string;
  period_end: string;
  starting_capital: number;
  total_return: number | null;
  max_drawdown: number | null;
  number_of_trades: number | null;
  error: string | null;
}

export interface BacktestRunDetail extends BacktestRunSummary {
  reason: string | null;
  assumptions: CostAssumptions;
  summary: BacktestSummaryMetrics | null;
  equity_curve: EquityPoint[];
  benchmark_curve: EquityPoint[];
  trade_count: number;
  trades_truncated: boolean;
  warnings: string[];
  data_summary: CoinDataSummary[];
  disclaimer: string;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface BacktestConfig {
  engine_version: string;
  methodology_version: string;
  strategy: string;
  strategy_description: string;
  horizons: string[];
  decision_horizons: string[];
  min_sample_size: number;
  bar_intervals: BarInterval[];
  sizing_modes: SizingMode[];
  defaults: {
    starting_capital: number;
    bar_interval: BarInterval;
    sizing_mode: SizingMode;
    position_size: number;
    max_allocation_pct: number;
    fee_rate: number;
    slippage_rate: number;
    close_open_positions_at_end: boolean;
    benchmark: string;
  };
  limits: {
    max_coins: number;
    max_days: number;
    min_days: number;
    max_capital: number;
    max_bars_per_coin: number;
    max_concurrent_runs: number;
    max_stored_trades: number;
  };
  disclaimer: string;
}
