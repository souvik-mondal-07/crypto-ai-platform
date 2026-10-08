/** Placeholder with the same rough layout as a loaded prediction (never a bare spinner). */
export function PredictionSkeleton() {
  return (
    <div role="status" aria-label="Loading prediction" aria-busy="true" className="animate-pulse space-y-4">
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-7 w-12 rounded-md bg-slate-200 dark:bg-slate-700" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 rounded-lg bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
      <div className="h-10 rounded-lg bg-slate-100 dark:bg-slate-800" />
      <div className="h-4 w-2/3 rounded bg-slate-100 dark:bg-slate-800" />
    </div>
  );
}
