import { useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { EmptyState } from "../common/EmptyState";
import { ErrorMessage } from "../common/ErrorMessage";
import { Loader } from "../common/Loader";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { getFreshness } from "../../utils/freshness";
import type { FundamentalAnalysisResponse } from "../../types/fundamentals";
import {
  CalculatedMetricsCard,
  EcosystemCard,
  MarketOverviewCard,
  ProjectInfoCard,
  ScoreCard,
  SummaryCard,
  SupplyCard,
  ValuationCard,
} from "./FundamentalCards";

interface FundamentalAnalysisSectionProps {
  fundamentals: FundamentalAnalysisResponse | null;
  /** First load, nothing to show yet. */
  loading: boolean;
  /** Reloading while existing data stays on screen. */
  refreshing: boolean;
  error: string | null;
  /** The backend says this coin has no fundamental data at all (as opposed to a failed request). */
  notAvailable: boolean;
  onRetry: () => void;
  onRefresh: () => void;
}

function Timestamp({ label, iso }: { label: string; iso: string | null }) {
  if (!iso) return <span>{label}: not fetched</span>;
  return (
    <span title={formatAbsoluteDateTime(iso)}>
      {label} {formatRelativeTime(iso)}
    </span>
  );
}

function Notice({ children }: { children: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

/**
 * Fundamental Analysis section for the Coin Details page (Phase 11).
 *
 * Purely descriptive. Provider-reported figures and the platform's own
 * calculated metrics are labelled separately; anything the provider
 * didn't supply renders "Not available" — never an estimate. There is
 * deliberately no BUY/HOLD/SELL framing anywhere: the fundamental score
 * is a structural descriptor, and the decision layer is a later phase.
 */
export function FundamentalAnalysisSection({
  fundamentals,
  loading,
  refreshing,
  error,
  notAvailable,
  onRetry,
  onRefresh,
}: FundamentalAnalysisSectionProps) {
  const [expanded, setExpanded] = useState(true);
  const busy = loading || refreshing;
  // Same 6h rule as the backend's is_stale; the backend's own warnings above stay the primary notice.
  const marketFreshness = getFreshness(fundamentals?.timestamps.market_data_updated_at);

  return (
    <section
      aria-labelledby="fundamental-analysis-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="fundamental-analysis-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Fundamental Analysis
        </h2>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="flex items-center gap-1 text-xs font-medium text-sky-600 hover:underline disabled:opacity-50 dark:text-sky-400"
          >
            <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} aria-hidden="true" />
            Refresh data
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="text-xs font-medium text-slate-500 hover:underline dark:text-slate-400"
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>

      {!expanded ? null : loading ? (
        <div className="flex h-[160px] items-center justify-center">
          <Loader label="Loading fundamental analysis..." />
        </div>
      ) : error && notAvailable ? (
        <EmptyState message="Fundamental data is not available for this coin yet." />
      ) : error && !fundamentals ? (
        <div className="flex flex-col items-center gap-2 py-6">
          <ErrorMessage message={error} />
          <button
            type="button"
            onClick={onRetry}
            className="text-sm font-medium text-sky-600 hover:underline dark:text-sky-400"
          >
            Retry
          </button>
        </div>
      ) : !fundamentals ? (
        <EmptyState message="Fundamental analysis is not available for this coin yet." />
      ) : (
        <>
          <div className="mb-3 space-y-2">
            {error && <Notice>{`Could not refresh: ${error}. Showing the last loaded data.`}</Notice>}
            {/* The backend's warnings are the single source for staleness / partial-data notices. */}
            {fundamentals.warnings.map((warning) => (
              <Notice key={warning}>{warning}</Notice>
            ))}
          </div>

          <div className="mb-3 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400" aria-label="Data quality and freshness">
            <p className="mb-1 font-medium text-slate-700 dark:text-slate-200">Data quality &amp; freshness</p>
            <p>
              Provider data via {fundamentals.source}
              {fundamentals.market_data_source && fundamentals.market_data_source !== fundamentals.source
                ? ` (market data via ${fundamentals.market_data_source})`
                : ""}
              . Not real-time.
            </p>
            <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5">
              <li><Timestamp label="project data fetched" iso={fundamentals.timestamps.fetched_at} /></li>
              <li><Timestamp label="market data updated" iso={fundamentals.timestamps.market_data_updated_at} /></li>
              <li><Timestamp label="calculated" iso={fundamentals.timestamps.calculated_at} /></li>
            </ul>
            {marketFreshness.level !== "fresh" && (
              <p className={`mt-1 font-medium ${marketFreshness.level === "stale" ? "text-amber-700 dark:text-amber-400" : "text-red-700 dark:text-red-400"}`}>
                {marketFreshness.level === "stale" ? "Market data is stale." : "Market data unavailable."}
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            <MarketOverviewCard market={fundamentals.market} />
            <SupplyCard supply={fundamentals.supply} metrics={fundamentals.calculated_metrics} />
            <ValuationCard valuation={fundamentals.valuation} />
            <CalculatedMetricsCard metrics={fundamentals.calculated_metrics} />
            <ProjectInfoCard project={fundamentals.project_info} />
            <EcosystemCard ecosystem={fundamentals.ecosystem} />
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ScoreCard score={fundamentals.score} />
            <SummaryCard summary={fundamentals.summary} />
          </div>
        </>
      )}
    </section>
  );
}
