interface AiAnalysisSkeletonProps {
  /** "generating" = the AI is writing a new explanation (can take several seconds). */
  mode?: "loading" | "generating";
}

/** Placeholder with the rough layout of a loaded explanation (never a bare spinner). */
export function AiAnalysisSkeleton({ mode = "loading" }: AiAnalysisSkeletonProps) {
  const label = mode === "generating" ? "Generating AI analysis" : "Loading AI analysis";
  return (
    <div role="status" aria-label={label} aria-busy="true" className="animate-pulse space-y-4">
      <div className="h-24 rounded-lg bg-slate-100 dark:bg-slate-800" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-lg bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="h-24 rounded-lg bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
      {mode === "generating" && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Writing an explanation of the platform&apos;s analysis. This can take a few seconds.
        </p>
      )}
    </div>
  );
}
