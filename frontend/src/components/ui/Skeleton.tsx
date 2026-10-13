/** Placeholder block that matches the layout it stands in for. Pulses unless the user prefers reduced motion. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-slate-200 motion-reduce:animate-none dark:bg-slate-800 ${className}`} />;
}

/** Table-shaped loading placeholder (header row + `rows` body rows of `cols` cells). */
export function TableSkeleton({ rows = 6, cols = 6, label = "Loading" }: { rows?: number; cols?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="table-wrap">
      <span className="sr-only">{label}</span>
      <div className="space-y-3 p-4" aria-hidden="true">
        <Skeleton className="h-3 w-1/3" />
        {Array.from({ length: rows }).map((_, row) => (
          <div key={row} className="flex items-center gap-4">
            <Skeleton className="h-7 w-7 flex-shrink-0 rounded-full" />
            {Array.from({ length: cols - 1 }).map((__, col) => (
              <Skeleton key={col} className="h-3 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Card-shaped loading placeholder for a metric. */
export function MetricSkeleton() {
  return (
    <div className="card card-pad" aria-hidden="true">
      <Skeleton className="h-2.5 w-20" />
      <Skeleton className="mt-3 h-6 w-28" />
      <Skeleton className="mt-2 h-2.5 w-14" />
    </div>
  );
}
