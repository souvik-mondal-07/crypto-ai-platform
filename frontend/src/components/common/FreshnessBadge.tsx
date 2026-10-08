import { formatAbsoluteDateTime, formatRelativeTime } from "../../utils/formatters";
import { getFreshness, type FreshnessLevel } from "../../utils/freshness";

const DOT: Record<FreshnessLevel, string> = {
  fresh: "bg-emerald-500",
  stale: "bg-amber-500",
  unavailable: "bg-red-500",
};

const TEXT: Record<FreshnessLevel, string> = {
  fresh: "text-emerald-700 dark:text-emerald-400",
  stale: "text-amber-700 dark:text-amber-400",
  unavailable: "text-red-700 dark:text-red-400",
};

interface FreshnessBadgeProps {
  lastUpdated: string | null | undefined;
  /** The backend's own is_stale flag; preferred over the client-side fallback. */
  isStale?: boolean;
  /** Dot only (tables); the label stays available to screen readers. */
  dotOnly?: boolean;
}

/**
 * Data Status indicator. State is conveyed by the label text as well as the
 * dot colour, so it is not colour-only. Timestamps are the backend's real
 * `last_updated` — nothing is invented when it is missing ("unavailable").
 */
export function FreshnessBadge({ lastUpdated, isStale, dotOnly = false }: FreshnessBadgeProps) {
  const { level, label } = getFreshness(lastUpdated, isStale);
  const detail = lastUpdated ? `Last updated ${formatRelativeTime(lastUpdated)}` : "No update timestamp available";
  const title = lastUpdated ? `${label} · ${formatAbsoluteDateTime(lastUpdated)}` : label;

  if (dotOnly) {
    return (
      <span title={title} className="inline-flex items-center">
        <span className={`h-2 w-2 rounded-full ${DOT[level]}`} aria-hidden="true" />
        <span className="sr-only">{label}</span>
      </span>
    );
  }

  return (
    <div className="flex flex-col" title={title}>
      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${TEXT[level]}`}>
        <span className={`h-2 w-2 rounded-full ${DOT[level]}`} aria-hidden="true" />
        {label}
      </span>
      <span className="text-xs text-slate-500 dark:text-slate-400">{detail}</span>
    </div>
  );
}
