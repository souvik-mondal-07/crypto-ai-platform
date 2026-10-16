import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { TableSkeleton } from "../ui/Skeleton";
import type { BacktestRunSummary, Paged, RunStatus } from "../../types/backtesting";
import { formatAbsoluteDateTime, formatPeriod, fractionToPercent, returnClass } from "../../utils/backtestFormat";

interface RunsListProps {
  runs: Paged<BacktestRunSummary> | null;
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (runId: string) => void;
  onRetry: () => void;
}

const STATUS_BADGE: Record<RunStatus, string> = {
  queued: "badge-neutral",
  running: "badge-info",
  completed: "badge-success",
  failed: "badge-danger",
};

/** The signed-in user's recent backtest runs (the API only ever returns their own). */
export function RunsList({ runs, loading, error, selectedId, onSelect, onRetry }: RunsListProps) {
  if (error) return <RetryError message={error} onRetry={onRetry} />;
  if (loading && runs === null) return <TableSkeleton label="Loading your backtests" rows={3} cols={4} />;
  if (runs === null || runs.items.length === 0) return <EmptyState message="You have not run any backtests yet." />;

  return (
    <ul className="space-y-2" aria-label="Recent backtest runs">
      {runs.items.map((run) => (
        <li key={run.run_id}>
          <button
            type="button"
            onClick={() => onSelect(run.run_id)}
            aria-pressed={run.run_id === selectedId}
            className={`card card-pad flex w-full flex-wrap items-center justify-between gap-2 text-left ${run.run_id === selectedId ? "ring-2 ring-brand-500" : ""}`}
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-slate-900 dark:text-slate-100">{run.symbols.join(", ") || "Backtest"}</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">{formatPeriod(run.period_start, run.period_end)} · {formatAbsoluteDateTime(run.created_at)}</span>
            </span>
            <span className="flex items-center gap-3">
              {run.status === "completed" && run.result_status === "insufficient_data" ? (
                <span className="badge-warning">Insufficient data</span>
              ) : (
                <span className={STATUS_BADGE[run.status]}>{run.status}</span>
              )}
              {run.status === "completed" && run.total_return !== null && (
                <span className={`text-sm font-semibold tabular-nums ${returnClass(run.total_return)}`}>{fractionToPercent(run.total_return, 2, true)}</span>
              )}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
