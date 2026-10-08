/** Placeholder with the same rough layout as a loaded decision (never a bare spinner). */
export function DecisionSkeleton() {
  return (
    <div role="status" aria-label="Loading risk and decision" aria-busy="true" className="animate-pulse space-y-4">
      <div className="h-10 w-28 rounded-lg bg-slate-200 dark:bg-slate-700" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-lg bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 rounded-lg bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
    </div>
  );
}
