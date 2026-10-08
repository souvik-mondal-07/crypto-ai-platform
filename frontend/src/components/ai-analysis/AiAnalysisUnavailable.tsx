import { RefreshCw, Sparkles } from "lucide-react";

import { AI_UNAVAILABLE_MESSAGE, type AiErrorInfo } from "../../utils/aiAnalysisErrors";
import { RetryError } from "../common/RetryError";

interface AiAnalysisUnavailableProps {
  error: AiErrorInfo;
  onRetry: () => void;
}

const BUTTON =
  "inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-sky-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:border-slate-700 dark:text-sky-400 dark:hover:bg-slate-800";

/**
 * What the AI section shows instead of an explanation. The AI is an enhancement: every other section
 * of the page keeps working, and the copy says so.
 */
export function AiAnalysisUnavailable({ error, onRetry }: AiAnalysisUnavailableProps) {
  if (error.kind === "unavailable") {
    return (
      <div role="status" className="space-y-3 rounded-lg border border-dashed border-slate-300 p-4 dark:border-slate-700">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{AI_UNAVAILABLE_MESSAGE}</p>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              The technical, fundamental, sentiment, prediction, risk and decision information on this page is not affected.
            </p>
          </div>
        </div>
        <button type="button" onClick={onRetry} className={BUTTON}>
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          Retry
        </button>
      </div>
    );
  }

  if (error.kind === "insufficient_data") {
    return (
      <div role="status" className="space-y-3 rounded-lg border border-dashed border-slate-300 p-4 dark:border-slate-700">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Not enough data for an AI explanation</p>
        <p className="text-sm text-slate-600 dark:text-slate-300">{error.message}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          No explanation is written rather than guessing from missing information.
        </p>
        <button type="button" onClick={onRetry} className={BUTTON}>
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          Retry
        </button>
      </div>
    );
  }

  return <RetryError message={error.message} onRetry={onRetry} />;
}
