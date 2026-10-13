import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";

import type { AnalysisType, HistoryEntry } from "../../types/userFeatures";
import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";

export const ANALYSIS_LABELS: Record<AnalysisType, string> = {
  coin_analysis: "Coin analysis",
  prediction: "ML prediction",
  risk_decision: "Risk & Decision",
  ai_analysis: "AI analysis",
};

/** Where on Coin Details each kind of analysis lives. */
const SECTION_ANCHORS: Record<AnalysisType, string> = {
  coin_analysis: "coin-technical",
  prediction: "coin-prediction",
  risk_decision: "coin-risk-decision",
  ai_analysis: "coin-ai-analysis",
};

export function historyLink(entry: Pick<HistoryEntry, "coin_id" | "analysis_type">): string {
  return `/coins/${entry.coin_id}#${SECTION_ANCHORS[entry.analysis_type]}`;
}

const DECISION_STYLES: Record<string, string> = {
  BUY: "text-emerald-700 dark:text-emerald-400",
  SELL: "text-red-700 dark:text-red-400",
  HOLD: "text-amber-700 dark:text-amber-400",
};

interface HistoryTableProps {
  entries: HistoryEntry[];
  onDelete: (entry: HistoryEntry) => void;
}

export function HistoryTable({ entries, onDelete }: HistoryTableProps) {
  return (
    <div className="overflow-x-auto card">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th className="px-4 py-3 font-medium">Coin</th>
            <th className="px-3 py-3 font-medium">Analysis</th>
            <th className="px-3 py-3 font-medium">Decision</th>
            <th className="px-3 py-3 font-medium">Risk</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 font-medium">When</th>
            <th className="px-3 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-b border-slate-50 last:border-0 dark:border-slate-800">
              <td className="px-4 py-3">
                <Link to={historyLink(entry)} className="font-medium text-slate-800 hover:underline dark:text-slate-100">
                  {entry.coin_name ?? "Unknown coin"}
                  {entry.symbol && <span className="ml-1 text-xs text-slate-400">{entry.symbol.toUpperCase()}</span>}
                </Link>
              </td>
              <td className="px-3 py-3 text-slate-600 dark:text-slate-300">{ANALYSIS_LABELS[entry.analysis_type]}</td>
              <td className={`px-3 py-3 font-medium ${entry.decision ? (DECISION_STYLES[entry.decision] ?? "") : "text-slate-400"}`}>{entry.decision ?? "—"}</td>
              <td className="px-3 py-3 text-slate-600 dark:text-slate-300">{entry.risk_level ?? "—"}</td>
              <td className="px-3 py-3">
                <span className={`rounded-full px-2 py-0.5 text-xs ${entry.status === "COMPLETED" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>
                  {entry.status === "COMPLETED" ? "Completed" : "Unavailable"}
                </span>
              </td>
              <td className="px-3 py-3 text-xs text-slate-500 dark:text-slate-400" title={formatAbsoluteDateTime(entry.created_at)}>
                {formatRelativeTime(entry.created_at)}
              </td>
              <td className="px-3 py-3 text-right">
                <button type="button" onClick={() => onDelete(entry)} aria-label={`Delete ${entry.coin_name ?? "history"} entry`} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:bg-slate-800">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
