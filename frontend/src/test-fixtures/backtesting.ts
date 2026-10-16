/** Test-only builders with explicit, hand-checkable values (the application never imports this file). */
import type {
  AccuracyMetrics, AccuracyResponse, BacktestConfig, BacktestRunDetail, BacktestRunSummary, BacktestTrade, DecisionCell,
  DecisionEvaluation, EquityPoint,
} from "../types/backtesting";

export const T0 = "2026-09-01T00:00:00Z";

export const metrics = (over: Partial<AccuracyMetrics> = {}): AccuracyMetrics => ({
  status: "ok", sample_size: 120, min_samples: 30, period_start: "2026-08-01T00:00:00Z", period_end: "2026-09-01T00:00:00Z",
  directional_accuracy: 0.625, directional_sample_size: 110, flat_predictions_excluded: 10, mae: 0.008, rmse: 0.011,
  mean_error: 0.0005, baseline_zero_mae: 0.01, mae_vs_zero_baseline: 0.8, mean_predicted_return: 0.002, mean_actual_return: 0.0015,
  range_coverage: 0.79, range_sample_size: 118, nominal_coverage: 0.8, message: null, ...over,
});

export const insufficientMetrics = (): AccuracyMetrics =>
  metrics({
    status: "insufficient_data", sample_size: 5, directional_accuracy: null, directional_sample_size: 0, flat_predictions_excluded: 0,
    mae: null, rmse: null, mean_error: null, baseline_zero_mae: null, mae_vs_zero_baseline: null, mean_predicted_return: null,
    mean_actual_return: null, range_coverage: null, range_sample_size: 0, nominal_coverage: null,
    message: "Insufficient historical predictions to calculate reliable accuracy metrics.",
  });

export const noDataMetrics = (): AccuracyMetrics =>
  ({ ...insufficientMetrics(), status: "no_data", sample_size: 0, period_start: null, period_end: null,
     message: "No matured predictions have been matched to market outcomes yet." });

export const accuracy = (over: Partial<AccuracyResponse> = {}): AccuracyResponse => ({
  methodology_version: "1.0.0", generated_at: T0,
  filters: { coin_id: null, horizon: null, model: null, model_version: null }, coin: null,
  overall: metrics(),
  by_horizon: [{ ...metrics({ sample_size: 80 }), horizon: "24h" }, { ...metrics({ sample_size: 40, directional_accuracy: 0.5 }), horizon: "7d" }],
  by_model: [{ ...metrics(), model: "xgboost", model_version: "3" }],
  by_coin: [{ ...metrics(), coin_id: "a".repeat(24), symbol: "BTC" }],
  coverage: { total_predictions: 150, matured_predictions: 125, matched_outcomes: 120, pending_outcomes: 3, duplicates_removed: 2, unmatched_by_status: { missing_future_price: 2 } },
  options: { horizons: ["24h", "7d"], models: ["xgboost"], model_versions: [{ model: "xgboost", model_version: "3" }], coins: [{ id: "a".repeat(24), symbol: "BTC" }] },
  limitations: [], ...over,
});

export const cell = (over: Partial<DecisionCell> = {}): DecisionCell => ({
  decision: "BUY", horizon: "24h", count: 40, status: "ok", mean_return: 0.012, median_return: 0.008, directional_agreement: 0.6,
  within_neutral_band_rate: null, ...over,
});

export const decisionEvaluation = (over: Partial<DecisionEvaluation> = {}): DecisionEvaluation => ({
  methodology_version: "1.0.0", generated_at: T0, filters: { coin_id: null, horizon: null }, horizons: ["24h", "7d", "30d"],
  total_decisions_stored: 90, decision_counts: { BUY: 40, SELL: 25, HOLD: 25 },
  metrics: {
    evaluated_decisions: 90, evaluations: 90,
    by_decision_horizon: [
      cell(),
      cell({ decision: "SELL", count: 25, mean_return: -0.004, median_return: -0.003, directional_agreement: 0.56 }),
      cell({ decision: "HOLD", count: 25, mean_return: 0.001, median_return: 0.0, directional_agreement: null, within_neutral_band_rate: 0.72 }),
      cell({ decision: "BUY", horizon: "7d", count: 5, status: "insufficient_data", mean_return: null, median_return: null, directional_agreement: null }),
    ],
    pooled_directional: [{ horizon: "24h", count: 65, status: "ok", directional_agreement: 0.58 }],
    period_start: "2026-08-01T00:00:00Z", period_end: "2026-09-01T00:00:00Z", min_samples: 20, hold_neutral_band: { "24h": 0.02, "7d": 0.05, "30d": 0.1 },
  },
  limitations: ["HOLD makes no directional claim: it is reported by forward return and neutral-band rate, not as success or failure."], ...over,
});

export const emptyDecisionEvaluation = (): DecisionEvaluation =>
  decisionEvaluation({
    total_decisions_stored: 0, decision_counts: {},
    metrics: { evaluated_decisions: 0, evaluations: 0, by_decision_horizon: [], pooled_directional: [], period_start: null, period_end: null, min_samples: 20, hold_neutral_band: {} },
    limitations: ["No decisions have been stored yet, so none can be evaluated."],
  });

export const config = (): BacktestConfig => ({
  engine_version: "1.0.0", methodology_version: "1.0.0", strategy: "phase14_decisions",
  strategy_description: "Long-only replay of the stored Phase 14 BUY/HOLD/SELL decisions.",
  horizons: ["1h", "4h", "24h", "7d", "30d"], decision_horizons: ["24h", "7d", "30d"], min_sample_size: 30,
  bar_intervals: ["1h", "4h", "1d"], sizing_modes: ["fixed_fraction", "fixed_amount"],
  defaults: { starting_capital: 10000, bar_interval: "1h", sizing_mode: "fixed_fraction", position_size: 0.25, max_allocation_pct: 0.5, fee_rate: 0.001, slippage_rate: 0.0005, close_open_positions_at_end: true, benchmark: "equal_weight_buy_and_hold" },
  limits: { max_coins: 10, max_days: 365, min_days: 1, max_capital: 1_000_000_000, max_bars_per_coin: 5000, max_concurrent_runs: 2, max_stored_trades: 5000 },
  disclaimer: "Simulated results on historical data.",
});

export const runSummary = (over: Partial<BacktestRunSummary> = {}): BacktestRunSummary => ({
  run_id: "r".repeat(32), status: "completed", result_status: "ok", created_at: "2026-09-02T10:00:00Z", started_at: "2026-09-02T10:00:01Z",
  finished_at: "2026-09-02T10:00:05Z", engine_version: "1.0.0", strategy: "phase14_decisions", coin_ids: ["a".repeat(24)], symbols: ["BTC"],
  period_start: "2026-08-01T00:00:00Z", period_end: "2026-08-31T00:00:00Z", starting_capital: 10000, total_return: 0.125, max_drawdown: 0.08,
  number_of_trades: 4, error: null, ...over,
});

export const curve = (values: number[]): EquityPoint[] =>
  values.map((value, i) => ({ time: new Date(Date.UTC(2026, 7, 1 + i)).toISOString(), value }));

export const runDetail = (over: Partial<BacktestRunDetail> = {}): BacktestRunDetail => ({
  ...runSummary(),
  reason: null,
  assumptions: {
    engine_version: "1.0.0", strategy: "phase14_decisions", strategy_version: "1.0.0", bar_interval: "1h", sizing_mode: "fixed_fraction",
    position_size: 0.25, max_allocation_pct: 0.5, fee_rate: 0.001, slippage_rate: 0.0005, execution: "next_bar_open", long_only: true,
    leverage: 1, close_open_positions_at_end: true, risk_free_rate_annual: 0, benchmark: "equal_weight_buy_and_hold", benchmark_costs: "same fee and slippage",
  },
  summary: {
    initial_value: 10000, final_value: 11250, total_return: 0.125, annualized_return: null, max_drawdown: 0.08, number_of_trades: 4, number_of_fills: 8,
    win_rate: 0.75, average_win_return: 0.06, average_loss_return: -0.02, total_fees: 42.5, estimated_slippage: 21.25, total_costs: 63.75,
    benchmark_final_value: 10800, benchmark_return: 0.08, sharpe_ratio: null, sharpe_note: "Needs at least 30 return observations (have 5).",
    skipped_signals: {}, period_start: "2026-08-01T00:00:00Z", period_end: "2026-08-31T00:00:00Z", bars: 720, decisions_in_period: 9,
  },
  equity_curve: curve([10000, 10400, 10100, 11000, 11250]), benchmark_curve: curve([10000, 10200, 10300, 10600, 10800]),
  trade_count: 8, trades_truncated: false, warnings: ["Only 4 closed trade(s): win rate and average returns are statistically unreliable."],
  data_summary: [{ coin_id: "a".repeat(24), symbol: "BTC", bars: 720, decisions: 9, note: null }], disclaimer: "Simulated results on historical data.", ...over,
});

export const trade = (over: Partial<BacktestTrade> = {}): BacktestTrade => ({
  coin_id: "a".repeat(24), symbol: "BTC", side: "BUY", reason: "decision", decision_id: "d1", decision_time: "2026-08-02T00:00:00Z",
  execution_time: "2026-08-02T00:00:00Z", price: 100.05, reference_price: 100, quantity: 2.5, notional: 250.125, fee: 0.25, slippage_cost: 0.125, cash_after: 9749.6, ...over,
});

export const paged = <T,>(items: T[], over: Partial<{ total: number; page: number; limit: number }> = {}) => ({ items, total: items.length, page: 1, limit: 25, ...over });
