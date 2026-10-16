import { EmptyState } from "../common/EmptyState";
import { Loader } from "../common/Loader";
import { Notice } from "../common/Notice";
import { RetryError } from "../common/RetryError";
import { EquityCurveChart } from "./EquityCurveChart";
import { MetricTile } from "./MetricTile";
import { TradesTable } from "./TradesTable";
import type { BacktestRunDetail, BacktestTrade, Paged } from "../../types/backtesting";
import { NOT_AVAILABLE, formatNumber, formatPeriod, formatUsd, fractionToPercent, returnClass } from "../../utils/backtestFormat";

interface BacktestResultsProps {
  detail: BacktestRunDetail | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  trades: Paged<BacktestTrade> | null;
  tradesError: string | null;
  onTradesPage: (page: number) => void;
}

/** Cost and execution assumptions — shown in EVERY report, including failed and insufficient-data ones. */
export function AssumptionsPanel({ run }: { run: BacktestRunDetail }) {
  const a = run.assumptions;
  return (
    <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2" aria-label="Cost and execution assumptions">
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Transaction fee</dt><dd>{fractionToPercent(a.fee_rate, 3)} per side</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Slippage</dt><dd>{fractionToPercent(a.slippage_rate, 3)} per fill (adverse)</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Position sizing</dt><dd>{a.sizing_mode === "fixed_fraction" ? `${fractionToPercent(a.position_size, 1)} of equity` : formatUsd(a.position_size)}</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Max allocation per asset</dt><dd>{fractionToPercent(a.max_allocation_pct, 1)}</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Execution</dt><dd>{a.execution === "next_bar_open" ? "Next bar open" : a.execution}</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Bar interval</dt><dd>{a.bar_interval}</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Direction</dt><dd>{a.long_only ? "Long only, no leverage" : "Long/short"}</dd></div>
      <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Engine</dt><dd>v{a.engine_version}</dd></div>
    </dl>
  );
}

/** The results of one backtest run, in whichever state it is in (running, failed, insufficient data, completed). */
export function BacktestResults({ detail, loading, error, onRetry, trades, tradesError, onTradesPage }: BacktestResultsProps) {
  if (error) return <RetryError message={error} onRetry={onRetry} />;
  if (detail === null) {
    return loading ? <Loader label="Loading backtest..." /> : <EmptyState message="Run a backtest or choose one from your recent runs to see its results here." />;
  }

  const s = detail.summary;
  return (
    <div className="space-y-5" data-testid="backtest-results">
      <p className="text-sm text-slate-600 dark:text-slate-300">
        {detail.symbols.join(", ") || "Selected coins"} · {formatPeriod(detail.period_start, detail.period_end)} · starting capital {formatUsd(detail.starting_capital)}
      </p>

      {(detail.status === "queued" || detail.status === "running") && (
        <div role="status" aria-live="polite">
          <Loader label={detail.status === "queued" ? "Backtest queued..." : "Backtest running..."} />
        </div>
      )}

      {detail.status === "failed" && (
        <Notice kind="error" message={`Backtest failed: ${detail.error ?? "an unknown error occurred."}`} />
      )}

      {detail.status === "completed" && detail.result_status === "insufficient_data" && (
        <Notice kind="info" message={detail.reason ?? "There was not enough historical data to produce a reliable result."} />
      )}

      {detail.status === "completed" && s !== null && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Backtest summary">
            <MetricTile label="Total return" value={fractionToPercent(s.total_return, 2, true)} valueClassName={returnClass(s.total_return)}
              hint={`${formatUsd(s.initial_value)} → ${formatUsd(s.final_value)}`} />
            <MetricTile label="Benchmark return" value={fractionToPercent(s.benchmark_return, 2, true)} valueClassName={returnClass(s.benchmark_return)}
              hint={`Final ${formatUsd(s.benchmark_final_value)}`} />
            <MetricTile label="Max drawdown" value={s.max_drawdown === null ? NOT_AVAILABLE : `-${fractionToPercent(s.max_drawdown, 2)}`} />
            <MetricTile label="Win rate" value={fractionToPercent(s.win_rate, 1)}
              hint={s.number_of_trades === 0 ? "No closed trades" : `${s.number_of_trades} closed trade(s)`} />
            <MetricTile label="Trades" value={s.number_of_trades} hint={`${s.number_of_fills} fills`} />
            <MetricTile label="Annualized return" value={fractionToPercent(s.annualized_return, 2, true)}
              hint={s.annualized_return === null ? "Needs a period of at least 30 days" : undefined} />
            <MetricTile label="Avg winning trade" value={fractionToPercent(s.average_win_return, 2, true)} valueClassName={returnClass(s.average_win_return)} />
            <MetricTile label="Avg losing trade" value={fractionToPercent(s.average_loss_return, 2, true)} valueClassName={returnClass(s.average_loss_return)} />
            <MetricTile label="Sharpe ratio" value={s.sharpe_ratio === null ? NOT_AVAILABLE : formatNumber(s.sharpe_ratio, 2)}
              hint={s.sharpe_ratio === null ? s.sharpe_note ?? undefined : "Risk-free rate 0%, per-bar returns annualized"} />
          </div>

          <section aria-label="Cost breakdown" className="card card-pad">
            <h4 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Cost breakdown</h4>
            <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
              <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Fees paid</dt><dd>{formatUsd(s.total_fees)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Estimated slippage</dt><dd>{formatUsd(s.estimated_slippage)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-slate-500 dark:text-slate-400">Total costs</dt><dd>{formatUsd(s.total_costs)}</dd></div>
            </dl>
          </section>

          <section aria-label="Equity curve">
            <h4 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Equity curve</h4>
            <EquityCurveChart strategy={detail.equity_curve} benchmark={detail.benchmark_curve} />
          </section>
        </>
      )}

      <section aria-label="Assumptions" className="card card-pad">
        <h4 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Assumptions</h4>
        <AssumptionsPanel run={detail} />
      </section>

      {detail.data_summary.length > 0 && (
        <ul className="space-y-1 text-xs text-slate-500 dark:text-slate-400" aria-label="Data used">
          {detail.data_summary.map((d) => (
            <li key={d.coin_id}>{d.symbol ?? d.coin_id}: {d.bars} bars, {d.decisions} stored decisions{d.note ? ` — ${d.note}` : ""}</li>
          ))}
        </ul>
      )}
      {detail.warnings.map((warning) => <Notice key={warning} kind="info" message={warning} />)}

      {detail.status === "completed" && detail.trade_count > 0 && (
        <section aria-label="Trade history section">
          <h4 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">Trade history</h4>
          <TradesTable trades={trades} error={tradesError} truncated={detail.trades_truncated} onPage={onTradesPage} onRetry={onRetry} />
        </section>
      )}

      <p className="text-xs text-slate-500 dark:text-slate-400">{detail.disclaimer}</p>
    </div>
  );
}
