import type { ReactNode } from "react";

interface MetricTileProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  valueClassName?: string;
}

/** One labelled figure. `value` is already formatted — "N/A" when the metric could not be computed. */
export function MetricTile({ label, value, hint, valueClassName = "text-slate-900 dark:text-slate-100" }: MetricTileProps) {
  return (
    <div className="card card-pad min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 break-words text-xl font-semibold ${valueClassName}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  );
}
