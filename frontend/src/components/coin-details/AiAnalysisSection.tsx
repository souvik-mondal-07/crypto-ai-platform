import { RefreshCw } from "lucide-react";

import { useAiAnalysis } from "../../hooks/useAiAnalysis";
import { useCountdownSeconds } from "../../hooks/useCountdown";
import { AiAnalysisContent } from "../ai-analysis/AiAnalysisContent";
import { AiAnalysisDisclaimer } from "../ai-analysis/AiAnalysisDisclaimer";
import { AiAnalysisSkeleton } from "../ai-analysis/AiAnalysisSkeleton";
import { AiAnalysisUnavailable } from "../ai-analysis/AiAnalysisUnavailable";

/** Display name of the model behind the explanation (the backend decides the actual model id). */
const MODEL_DISPLAY_NAME = "Gemini 3.1 Flash-Lite";

/**
 * AI Analysis (Phase 15). Shows Gemini's plain-language EXPLANATION of the platform's own market,
 * technical, fundamental, sentiment, prediction, risk and decision data. It never decides or changes
 * BUY / HOLD / SELL (that stays with the Phase 14 section) and never produces a price prediction.
 *
 * Loads independently of every other section: if the AI is unavailable this section says so and the
 * rest of Coin Details is untouched. The browser only talks to the backend — never to Gemini.
 */
export function AiAnalysisSection({ coinId }: { coinId: string }) {
  const { data, loading, generating, refreshing, error, note, cooldownUntil, retry, regenerate } = useAiAnalysis(coinId);
  const secondsLeft = useCountdownSeconds(cooldownUntil);
  const regenerateDisabled = refreshing || secondsLeft > 0;

  return (
    <section
      aria-labelledby="coin-ai-analysis-heading"
      className="mt-6 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="coin-ai-analysis-heading" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            AI Analysis
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Powered by {MODEL_DISPLAY_NAME}</p>
        </div>
        {data && (
          <button
            type="button"
            onClick={regenerate}
            disabled={regenerateDisabled}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
            {refreshing ? "Generating…" : secondsLeft > 0 ? `Regenerate Analysis (${secondsLeft}s)` : "Regenerate Analysis"}
          </button>
        )}
      </div>

      {loading && <AiAnalysisSkeleton mode="loading" />}
      {generating && <AiAnalysisSkeleton mode="generating" />}
      {error && <AiAnalysisUnavailable error={error} onRetry={retry} />}
      {note && data && (
        <p role="note" className="mb-3 rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          A new explanation could not be generated: {note} The previous explanation is still shown.
        </p>
      )}
      {data && <AiAnalysisContent data={data} />}

      <AiAnalysisDisclaimer text={data?.disclaimer} />
    </section>
  );
}
