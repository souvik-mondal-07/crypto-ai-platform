import { RefreshCw } from "lucide-react";

import { EmptyState } from "../common/EmptyState";
import { Notice } from "../common/Notice";
import { RetryError } from "../common/RetryError";
import { MetricSkeleton } from "../ui/Skeleton";
import { MetricTile } from "./MetricTile";
import type { RefreshUiState } from "../../hooks/useModelAccuracy";
import type { AccuracyFilters, AccuracyMetrics, AccuracyResponse } from "../../types/backtesting";
import {
  NOT_AVAILABLE, formatNumber, formatPeriod, formatPoints, fractionToPercent, modelVersionKey, modelVersionLabel,
} from "../../utils/backtestFormat";

export const INSUFFICIENT_MESSAGE = "Insufficient historical predictions to calculate reliable accuracy metrics.";

interface AccuracySectionProps {
  data: AccuracyResponse | null;
  loading: boolean;
  error: string | null;
  filters: AccuracyFilters;
  onFilters: (patch: Partial<AccuracyFilters>) => void;
  onRetry: () => void;
  refresh: RefreshUiState;
  onRefresh: () => void;
}

const SELECT =
  "rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";

function MetricRow({ label, metrics }: { label: string; metrics: AccuracyMetrics }) {
  const ok = metrics.status === "ok";
  return (
    <tr className="table-row">
      <th scope="row" className="px-3 py-2 text-left font-medium text-slate-900 dark:text-slate-100">{label}</th>
      <td className="px-3 py-2 text-right tabular-nums">{metrics.sample_size}</td>
      <td className="px-3 py-2 text-right tabular-nums">{ok ? fractionToPercent(metrics.directional_accuracy, 1) : NOT_AVAILABLE}</td>
      <td className="px-3 py-2 text-right tabular-nums">{ok ? formatPoints(metrics.mae) : NOT_AVAILABLE}</td>
      <td className="px-3 py-2 text-right tabular-nums">{ok ? formatPoints(metrics.rmse) : NOT_AVAILABLE}</td>
      <td className="px-3 py-2 text-right text-xs text-slate-500 dark:text-slate-400">{ok ? "" : metrics.status === "no_data" ? "No data" : "Insufficient data"}</td>
    </tr>
  );
}

function BreakdownTable({ title, firstColumn, rows }: { title: string; firstColumn: string; rows: { key: string; label: string; metrics: AccuracyMetrics }[] }) {
  if (rows.length === 0) return null;
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h4>
      <div className="table-wrap">
        <table className="w-full text-sm">
          <thead className="table-head">
            <tr>
              <th scope="col" className="px-3 py-2 text-left">{firstColumn}</th>
              <th scope="col" className="px-3 py-2 text-right">Samples</th>
              <th scope="col" className="px-3 py-2 text-right">Directional accuracy</th>
              <th scope="col" className="px-3 py-2 text-right">MAE</th>
              <th scope="col" className="px-3 py-2 text-right">RMSE</th>
              <th scope="col" className="px-3 py-2"><span className="sr-only">Status</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => <MetricRow key={row.key} label={row.label} metrics={row.metrics} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Model Accuracy: filters, headline metrics, breakdowns, coverage and honest limitations — real API data only. */
export function AccuracySection({ data, loading, error, filters, onFilters, onRetry, refresh, onRefresh }: AccuracySectionProps) {
  const refreshButton = (
    <button type="button" className="btn-secondary" onClick={onRefresh} disabled={refresh.running}>
      <RefreshCw className={`h-4 w-4 ${refresh.running ? "animate-spin motion-reduce:animate-none" : ""}`} aria-hidden="true" />
      {refresh.running ? "Updating outcomes..." : "Update outcomes"}
    </button>
  );

  const options = data?.options;
  const filterBar = (
    <div className="flex flex-wrap items-end gap-3" role="group" aria-label="Accuracy filters">
      <label className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
        Horizon
        <select className={SELECT} value={filters.horizon} onChange={(event) => onFilters({ horizon: event.target.value })} aria-label="Prediction horizon">
          <option value="">All horizons</option>
          {(options?.horizons ?? []).map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
        Model / version
        <select className={SELECT} value={filters.modelVersion} onChange={(event) => onFilters({ modelVersion: event.target.value })} aria-label="Model and version">
          <option value="">All models</option>
          {(options?.model_versions ?? []).map((mv) => (
            <option key={modelVersionKey(mv.model, mv.model_version)} value={modelVersionKey(mv.model, mv.model_version)}>
              {modelVersionLabel(mv.model, mv.model_version)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
        Coin
        <select className={SELECT} value={filters.coinId} onChange={(event) => onFilters({ coinId: event.target.value })} aria-label="Coin">
          <option value="">All coins</option>
          {(options?.coins ?? []).map((coin) => <option key={coin.id} value={coin.id}>{coin.symbol || coin.id}</option>)}
        </select>
      </label>
      <div className="ml-auto">{refreshButton}</div>
    </div>
  );

  const refreshNotice = refresh.error ? (
    <Notice kind="error" message={refresh.error} />
  ) : refresh.running ? (
    <Notice kind="info" message="Matching matured predictions with real market outcomes. This can take a little while." />
  ) : refresh.message ? (
    <Notice kind="success" message={refresh.message} />
  ) : null;

  let body;
  if (error) {
    body = <RetryError message={error} onRetry={onRetry} />;
  } else if (loading && data === null) {
    body = (
      <div role="status" aria-label="Loading model accuracy" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <MetricSkeleton key={i} />)}
      </div>
    );
  } else if (data === null) {
    body = <EmptyState message="Model accuracy is not available." />;
  } else {
    const { overall, coverage } = data;
    const ok = overall.status === "ok";
    body = (
      <div className="space-y-5">
        {overall.status === "no_data" && (
          <EmptyState message={overall.message ?? "No matured predictions have been matched to market outcomes yet."} />
        )}
        {overall.status === "insufficient_data" && (
          <Notice kind="info" message={`${INSUFFICIENT_MESSAGE} (${overall.sample_size} matched so far; at least ${overall.min_samples} are required.)`} />
        )}
        {overall.status !== "no_data" && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Accuracy summary">
            <MetricTile label="Directional accuracy" value={ok ? fractionToPercent(overall.directional_accuracy, 1) : NOT_AVAILABLE}
              hint={ok ? `${overall.directional_sample_size} directional calls` : undefined} />
            <MetricTile label="MAE" value={ok ? formatPoints(overall.mae) : NOT_AVAILABLE}
              hint={ok ? `Zero-return baseline ${formatPoints(overall.baseline_zero_mae)}` : undefined} />
            <MetricTile label="RMSE" value={ok ? formatPoints(overall.rmse) : NOT_AVAILABLE} />
            <MetricTile label="Evaluation sample" value={overall.sample_size} hint={`Period ${formatPeriod(overall.period_start, overall.period_end)}`} />
            <MetricTile label="Range coverage" value={ok ? fractionToPercent(overall.range_coverage, 1) : NOT_AVAILABLE}
              hint={ok && overall.nominal_coverage !== null ? `Nominal ${fractionToPercent(overall.nominal_coverage, 0)} · ${overall.range_sample_size} ranges` : undefined} />
            <MetricTile label="Mean predicted return" value={ok ? fractionToPercent(overall.mean_predicted_return, 3, true) : NOT_AVAILABLE} />
            <MetricTile label="Mean actual return" value={ok ? fractionToPercent(overall.mean_actual_return, 3, true) : NOT_AVAILABLE} />
            <MetricTile label="MAE vs zero baseline" value={ok ? formatNumber(overall.mae_vs_zero_baseline, 2) : NOT_AVAILABLE}
              hint="Below 1.00 means the model beat always predicting 0" />
          </div>
        )}

        <BreakdownTable title="By prediction horizon" firstColumn="Horizon" rows={data.by_horizon.map((r) => ({ key: r.horizon, label: r.horizon, metrics: r }))} />
        <BreakdownTable title="By model and version" firstColumn="Model" rows={data.by_model.map((r) => ({ key: modelVersionKey(r.model, r.model_version), label: modelVersionLabel(r.model, r.model_version), metrics: r }))} />
        <BreakdownTable title="By coin" firstColumn="Coin" rows={data.by_coin.map((r) => ({ key: r.coin_id, label: r.symbol ?? r.coin_id, metrics: r }))} />

        <p className="text-xs text-slate-500 dark:text-slate-400" data-testid="accuracy-coverage">
          {coverage.total_predictions} stored predictions · {coverage.matured_predictions} matured · {coverage.matched_outcomes} matched to market outcomes ·{" "}
          {coverage.pending_outcomes} awaiting matching
          {coverage.duplicates_removed > 0 ? ` · ${coverage.duplicates_removed} duplicate(s) ignored` : ""}. Methodology v{data.methodology_version}.
        </p>
        {Object.keys(coverage.unmatched_by_status).length > 0 && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Not evaluated (never counted as wrong):{" "}
            {Object.entries(coverage.unmatched_by_status).map(([status, count]) => `${status.replace(/_/g, " ")} ${count}`).join(", ")}.
          </p>
        )}
        {data.limitations.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-300" aria-label="Limitations">
            {data.limitations.map((text) => <li key={text}>{text}</li>)}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {filterBar}
      {refreshNotice}
      {body}
    </div>
  );
}
