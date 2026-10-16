"""Pydantic models for /api/v1/backtesting (Phase 17). Every metric that cannot be computed honestly is null."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.config.backtest_config import MAX_CAPITAL, MAX_COINS_PER_BACKTEST

MetricStatus = Literal["ok", "insufficient_data", "no_data"]
RunStatus = Literal["queued", "running", "completed", "failed"]
ResultStatus = Literal["ok", "insufficient_data"]


# ------------------------------------------------------------------ model accuracy
class AccuracyMetrics(BaseModel):
    status: MetricStatus
    sample_size: int
    min_samples: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    directional_accuracy: Optional[float] = None
    directional_sample_size: int = 0
    flat_predictions_excluded: int = 0
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mean_error: Optional[float] = None
    baseline_zero_mae: Optional[float] = None
    mae_vs_zero_baseline: Optional[float] = None
    mean_predicted_return: Optional[float] = None
    mean_actual_return: Optional[float] = None
    range_coverage: Optional[float] = None
    range_sample_size: int = 0
    nominal_coverage: Optional[float] = None
    message: Optional[str] = None


class HorizonAccuracy(AccuracyMetrics):
    horizon: str


class ModelAccuracy(AccuracyMetrics):
    model: Optional[str] = None
    model_version: Optional[str] = None


class CoinAccuracy(AccuracyMetrics):
    coin_id: str
    symbol: Optional[str] = None


class AccuracyCoverage(BaseModel):
    total_predictions: int
    matured_predictions: int
    matched_outcomes: int
    pending_outcomes: int
    duplicates_removed: int
    unmatched_by_status: dict[str, int] = Field(default_factory=dict)


class ModelVersionOption(BaseModel):
    model: str
    model_version: Optional[str] = None


class CoinOption(BaseModel):
    id: str
    symbol: str = ""


class AccuracyOptions(BaseModel):
    horizons: list[str]
    models: list[str]
    model_versions: list[ModelVersionOption]
    coins: list[CoinOption]


class AccuracyFilters(BaseModel):
    coin_id: Optional[str] = None
    horizon: Optional[str] = None
    model: Optional[str] = None
    model_version: Optional[str] = None


class AccuracyCoinInfo(BaseModel):
    id: str
    symbol: Optional[str] = None
    name: Optional[str] = None


class AccuracyResponse(BaseModel):
    methodology_version: str
    generated_at: datetime
    filters: AccuracyFilters
    coin: Optional[AccuracyCoinInfo] = None
    overall: AccuracyMetrics
    by_horizon: list[HorizonAccuracy]
    by_model: list[ModelAccuracy]
    by_coin: list[CoinAccuracy]
    coverage: AccuracyCoverage
    options: AccuracyOptions
    limitations: list[str]


class RefreshState(BaseModel):
    running: bool
    accepted: bool = False
    message: Optional[str] = None
    last_started_at: Optional[datetime] = None
    last_finished_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_report: Optional[dict[str, Any]] = None


# ------------------------------------------------------------------ decision evaluation
class DecisionCell(BaseModel):
    decision: Literal["BUY", "HOLD", "SELL"]
    horizon: str
    count: int
    status: MetricStatus
    mean_return: Optional[float] = None
    median_return: Optional[float] = None
    directional_agreement: Optional[float] = None
    within_neutral_band_rate: Optional[float] = None


class PooledDirectional(BaseModel):
    horizon: str
    count: int
    status: MetricStatus
    directional_agreement: Optional[float] = None


class DecisionMetricsBlock(BaseModel):
    evaluated_decisions: int
    evaluations: int
    by_decision_horizon: list[DecisionCell]
    pooled_directional: list[PooledDirectional]
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    min_samples: int
    hold_neutral_band: dict[str, float]


class DecisionEvaluationFilters(BaseModel):
    coin_id: Optional[str] = None
    horizon: Optional[str] = None


class DecisionEvaluationResponse(BaseModel):
    methodology_version: str
    generated_at: datetime
    filters: DecisionEvaluationFilters
    horizons: list[str]
    total_decisions_stored: int
    decision_counts: dict[str, int]
    metrics: DecisionMetricsBlock
    limitations: list[str]


# ------------------------------------------------------------------ backtest runs
class BacktestRunCreate(BaseModel):
    """`extra=forbid`: a client-supplied `user_id` (or any unknown field) is rejected, never ignored silently."""

    model_config = ConfigDict(extra="forbid")

    coin_ids: list[str] = Field(..., min_length=1, max_length=MAX_COINS_PER_BACKTEST)
    start: datetime
    end: datetime
    starting_capital: float = Field(..., gt=0, le=MAX_CAPITAL)
    bar_interval: Literal["1h", "4h", "1d"] = "1h"
    sizing_mode: Literal["fixed_fraction", "fixed_amount"] = "fixed_fraction"
    position_size: float = Field(0.25, gt=0)
    max_allocation_pct: float = Field(0.5, gt=0, le=1)
    fee_rate: float = Field(0.001, ge=0, lt=0.1)
    slippage_rate: float = Field(0.0005, ge=0, lt=0.1)
    close_open_positions_at_end: bool = True


class CostAssumptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    engine_version: str
    strategy: str
    strategy_version: str
    bar_interval: str
    sizing_mode: str
    position_size: float
    max_allocation_pct: float
    fee_rate: float
    slippage_rate: float
    execution: str
    long_only: bool
    leverage: float
    close_open_positions_at_end: bool
    risk_free_rate_annual: float
    benchmark: str
    benchmark_costs: str


class BacktestSummaryMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    initial_value: Optional[float] = None
    final_value: Optional[float] = None
    total_return: Optional[float] = None
    annualized_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    number_of_trades: int = 0
    number_of_fills: int = 0
    win_rate: Optional[float] = None
    average_win_return: Optional[float] = None
    average_loss_return: Optional[float] = None
    total_fees: Optional[float] = None
    estimated_slippage: Optional[float] = None
    total_costs: Optional[float] = None
    benchmark_final_value: Optional[float] = None
    benchmark_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sharpe_note: Optional[str] = None
    skipped_signals: dict[str, int] = Field(default_factory=dict)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    bars: Optional[int] = None
    decisions_in_period: Optional[int] = None


class EquityPoint(BaseModel):
    time: datetime
    value: float


class BacktestTrade(BaseModel):
    coin_id: str
    symbol: Optional[str] = None
    side: Literal["BUY", "SELL"]
    reason: str
    decision_id: Optional[str] = None
    decision_time: Optional[datetime] = None
    execution_time: datetime
    price: float
    reference_price: float
    quantity: float
    notional: float
    fee: float
    slippage_cost: float
    cash_after: float


class CoinDataSummary(BaseModel):
    coin_id: str
    symbol: Optional[str] = None
    bars: int
    decisions: int
    note: Optional[str] = None


class BacktestRunSummary(BaseModel):
    run_id: str
    status: RunStatus
    result_status: Optional[ResultStatus] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    engine_version: str
    strategy: str
    coin_ids: list[str]
    symbols: list[str] = Field(default_factory=list)
    period_start: datetime
    period_end: datetime
    starting_capital: float
    total_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    number_of_trades: Optional[int] = None
    error: Optional[str] = None


class BacktestRunDetail(BacktestRunSummary):
    reason: Optional[str] = None
    assumptions: CostAssumptions
    summary: Optional[BacktestSummaryMetrics] = None
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    benchmark_curve: list[EquityPoint] = Field(default_factory=list)
    trade_count: int = 0
    trades_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    data_summary: list[CoinDataSummary] = Field(default_factory=list)
    disclaimer: str


class BacktestRunList(BaseModel):
    items: list[BacktestRunSummary]
    total: int
    page: int
    limit: int


class BacktestTradesPage(BaseModel):
    items: list[BacktestTrade]
    total: int
    page: int
    limit: int


class BacktestLimits(BaseModel):
    max_coins: int
    max_days: int
    min_days: int
    max_capital: float
    max_bars_per_coin: int
    max_concurrent_runs: int
    max_stored_trades: int


class BacktestConfigResponse(BaseModel):
    engine_version: str
    methodology_version: str
    strategy: str
    strategy_description: str
    horizons: list[str]
    decision_horizons: list[str]
    min_sample_size: int
    bar_intervals: list[str]
    sizing_modes: list[str]
    defaults: dict[str, Any]
    limits: BacktestLimits
    disclaimer: str
