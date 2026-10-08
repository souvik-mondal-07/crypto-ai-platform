export const AI_DISCLAIMER_FALLBACK =
  "AI-generated analysis is for informational purposes only and is not a guarantee of future performance or financial advice.";

export const AI_SOURCE_NOTE =
  "AI explanation is generated from the platform's market, technical, fundamental, sentiment, prediction, and risk data.";

interface AiAnalysisDisclaimerProps {
  /** The backend's disclaimer text when an analysis is loaded. */
  text?: string;
}

/** Always rendered — also in the loading, error and unavailable states. */
export function AiAnalysisDisclaimer({ text }: AiAnalysisDisclaimerProps) {
  return (
    <div className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <p>{AI_SOURCE_NOTE}</p>
      <p>{text || AI_DISCLAIMER_FALLBACK}</p>
    </div>
  );
}
