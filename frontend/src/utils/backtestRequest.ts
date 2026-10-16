import type { PickedCoin } from "../components/common/CoinPicker";
import type { BacktestConfig, BacktestRequest, BarInterval, SizingMode } from "../types/backtesting";

/** Builds the API request from the form's raw text values, or returns the first validation message. */
export function buildBacktestRequest(
  values: {
    coins: PickedCoin[]; start: string; end: string; capital: string; interval: BarInterval; sizingMode: SizingMode;
    positionSize: string; maxAllocationPct: string; feePct: string; slippagePct: string; closeAtEnd: boolean;
  },
  config: BacktestConfig,
  today: Date = new Date()
): { request: BacktestRequest } | { error: string } {
  const { limits } = config;
  if (values.coins.length === 0) return { error: "Choose at least one coin." };
  if (values.coins.length > limits.max_coins) return { error: `Choose at most ${limits.max_coins} coins.` };
  const start = new Date(`${values.start}T00:00:00Z`);
  const end = new Date(`${values.end}T00:00:00Z`);
  if (!values.start || !values.end || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return { error: "Enter a valid start and end date." };
  if (start >= end) return { error: "The start date must be before the end date." };
  if (end.getTime() > today.getTime()) return { error: "The end date cannot be in the future: backtests use historical data only." };
  const days = (end.getTime() - start.getTime()) / 86_400_000;
  if (days < limits.min_days) return { error: `The period must be at least ${limits.min_days} day(s).` };
  if (days > limits.max_days) return { error: `The period cannot exceed ${limits.max_days} days.` };
  const barSeconds = { "1h": 3600, "4h": 14_400, "1d": 86_400 }[values.interval];
  if ((days * 86_400) / barSeconds > limits.max_bars_per_coin) return { error: `That is more than ${limits.max_bars_per_coin} bars per coin; choose a coarser bar interval or a shorter period.` };

  const capital = Number(values.capital);
  if (!Number.isFinite(capital) || capital <= 0) return { error: "Starting capital must be greater than 0." };
  if (capital > limits.max_capital) return { error: "Starting capital is too large." };
  const size = Number(values.positionSize);
  if (!Number.isFinite(size) || size <= 0) return { error: "Position size must be greater than 0." };
  const positionSize = values.sizingMode === "fixed_fraction" ? size / 100 : size;
  if (values.sizingMode === "fixed_fraction" && positionSize > 1) return { error: "Position size cannot exceed 100% of equity." };
  if (values.sizingMode === "fixed_amount" && positionSize > capital) return { error: "Position size cannot exceed the starting capital." };
  const maxAlloc = Number(values.maxAllocationPct) / 100;
  if (!Number.isFinite(maxAlloc) || maxAlloc <= 0 || maxAlloc > 1) return { error: "Maximum allocation must be between 0% and 100%." };
  const fee = Number(values.feePct) / 100;
  if (!Number.isFinite(fee) || fee < 0 || fee >= 0.1) return { error: "Transaction fee must be between 0% and 10%." };
  const slippage = Number(values.slippagePct) / 100;
  if (!Number.isFinite(slippage) || slippage < 0 || slippage >= 0.1) return { error: "Slippage must be between 0% and 10%." };

  return {
    request: {
      coin_ids: values.coins.map((coin) => coin.id), start: start.toISOString(), end: end.toISOString(), starting_capital: capital,
      bar_interval: values.interval, sizing_mode: values.sizingMode, position_size: positionSize, max_allocation_pct: maxAlloc,
      fee_rate: fee, slippage_rate: slippage, close_open_positions_at_end: values.closeAtEnd,
    },
  };
}
