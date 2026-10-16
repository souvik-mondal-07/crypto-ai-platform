import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { TableSkeleton } from "../ui/Skeleton";
import type { DecisionCell, DecisionEvaluation } from "../../types/backtesting";
import { NOT_AVAILABLE, formatPeriod, fractionToPercent, returnClass } from "../../utils/backtestFormat";

interface DecisionEvaluationSectionProps {
  data: DecisionEvaluation | null;
  loading: boolean;
  error: string | null;
  horizon: string;
  onHorizon: (horizon: string) => void;
  onRetry: () => void;
}

const RULES: Record<DecisionCell["decision"], string> = {
  BUY: "Directionally aligned when the price rose over the horizon.",
  SELL: "Directionally aligned when the price fell over the horizon.",
  HOLD: "Makes no directional claim: shown by forward return and the share of outcomes inside a neutral band.",
};

function agreementText(cell: DecisionCell): string {
  if (cell.status !== "ok") return NOT_AVAILABLE;
  if (cell.decision === "HOLD") {
    return cell.within_neutral_band_rate === null ? NOT_AVAILABLE : `${fractionToPercent(cell.within_neutral_band_rate, 1)} within neutral band`;
  }
  return fractionToPercent(cell.directional_agreement, 1);
}

/** BUY/HOLD/SELL evaluated against the return that followed. No decision is labelled a "success" automatically. */
export function DecisionEvaluationSection({ data, loading, error, horizon, onHorizon, onRetry }: DecisionEvaluationSectionProps) {
  if (error) return <RetryError message={error} onRetry={onRetry} />;
  if (loading && data === null) return <TableSkeleton label="Loading decision evaluation" rows={3} cols={5} />;
  if (data === null) return <EmptyState message="Decision evaluation is not available." />;

  const { metrics } = data;
  const empty = metrics.evaluations === 0;

  return (
    <div className="space-y-4">
      <label className="flex w-fit flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
        Evaluation horizon
        <select
          value={horizon}
          onChange={(event) => onHorizon(event.target.value)}
          aria-label="Decision evaluation horizon"
          className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="">All horizons</option>
          {data.horizons.map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
      </label>

      {empty ? (
        <EmptyState message={data.limitations[0] ?? "No decisions have been evaluated yet."} />
      ) : (
        <div className="table-wrap">
          <table className="w-full text-sm" aria-label="Decision evaluation">
            <thead className="table-head">
              <tr>
                <th scope="col" className="px-3 py-2 text-left">Decision</th>
                <th scope="col" className="px-3 py-2 text-left">Horizon</th>
                <th scope="col" className="px-3 py-2 text-right">Evaluated</th>
                <th scope="col" className="px-3 py-2 text-right">Mean return</th>
                <th scope="col" className="px-3 py-2 text-right">Median return</th>
                <th scope="col" className="px-3 py-2 text-right">Agreement</th>
              </tr>
            </thead>
            <tbody>
              {metrics.by_decision_horizon.map((cell) => (
                <tr key={`${cell.decision}-${cell.horizon}`} className="table-row">
                  <th scope="row" className="px-3 py-2 text-left font-medium text-slate-900 dark:text-slate-100">{cell.decision}</th>
                  <td className="px-3 py-2">{cell.horizon}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{cell.count}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${returnClass(cell.mean_return)}`}>{fractionToPercent(cell.mean_return, 2, true)}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${returnClass(cell.median_return)}`}>{fractionToPercent(cell.median_return, 2, true)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {agreementText(cell)}
                    {cell.status === "insufficient_data" && <span className="ml-1 text-xs text-slate-500 dark:text-slate-400">(insufficient data)</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-500 dark:text-slate-400">
        {metrics.evaluated_decisions} decisions evaluated of {data.total_decisions_stored} stored · {formatPeriod(metrics.period_start, metrics.period_end)} ·
        at least {metrics.min_samples} per cell for metrics.
      </p>
      <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500 dark:text-slate-400" aria-label="Decision evaluation rules">
        {(Object.keys(RULES) as DecisionCell["decision"][]).map((kind) => <li key={kind}><strong>{kind}:</strong> {RULES[kind]}</li>)}
      </ul>
      {data.limitations.slice(empty ? 1 : 0).map((text) => <p key={text} className="text-xs text-slate-500 dark:text-slate-400">{text}</p>)}
    </div>
  );
}
