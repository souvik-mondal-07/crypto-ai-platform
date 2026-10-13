import { Link } from "react-router-dom";

import { EmptyState } from "../../components/common/EmptyState";
import { TableSkeleton } from "../../components/ui/Skeleton";
import { Pagination } from "../../components/common/Pagination";
import { RetryError } from "../../components/common/RetryError";
import { ANALYSIS_LABELS, HistoryTable } from "../../components/history/HistoryTable";
import { AppShell } from "../../components/layout/AppShell";
import { useHistory } from "../../hooks/useHistory";
import type { AnalysisType } from "../../types/userFeatures";

/** /history — the signed-in user's own analysis history, newest first. */
export function History() {
  const { data, loading, error, actionError, setPage, analysisType, changeType, retry, remove } = useHistory();

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Analysis History</h1>
          <p className="page-subtitle">The analyses you have viewed or generated.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <span>Show</span>
          <select
            value={analysisType}
            onChange={(event) => changeType(event.target.value as AnalysisType | "")}
            aria-label="Filter by analysis type"
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">All analyses</option>
            {(Object.keys(ANALYSIS_LABELS) as AnalysisType[]).map((type) => (
              <option key={type} value={type}>{ANALYSIS_LABELS[type]}</option>
            ))}
          </select>
        </label>
      </div>

      {actionError && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{actionError}</p>}

      <div className="mt-6">
        {error ? (
          <RetryError message={error} onRetry={retry} />
        ) : loading && data === null ? (
          <TableSkeleton label="Loading your history..." rows={5} cols={5} />
        ) : data === null || data.items.length === 0 ? (
          <EmptyState
            message={analysisType ? "No history for this analysis type." : "No analysis history yet."}
            action={
              analysisType ? undefined : (
                <Link to="/markets" className="btn-secondary">
                  Open a coin to analyze
                </Link>
              )
            }
          />
        ) : (
          <>
            <HistoryTable entries={data.items} onDelete={(entry) => void remove(entry.id)} />
            <Pagination page={data.page} pages={data.pages} onPageChange={setPage} disabled={loading} label="history" />
          </>
        )}
      </div>
    </AppShell>
  );
}
