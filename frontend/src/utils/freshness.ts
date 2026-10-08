/**
 * Data-freshness classification for the UI.
 *
 * The staleness threshold is NOT chosen here: it mirrors the backend's
 * `STALE_AFTER` (6 hours, backend/app/schemas/converters.py), and the
 * backend's own `is_stale` flag is preferred whenever a response carries it.
 * Do not raise this value to make warnings disappear — fix the data refresh
 * instead.
 */
export const BACKEND_STALE_AFTER_MS = 6 * 60 * 60 * 1000;

export type FreshnessLevel = "fresh" | "stale" | "unavailable";

export interface Freshness {
  level: FreshnessLevel;
  label: string;
}

export function getFreshness(
  lastUpdated: string | null | undefined,
  backendIsStale?: boolean,
  now: number = Date.now()
): Freshness {
  if (!lastUpdated) return { level: "unavailable", label: "Market data unavailable" };

  const parsed = Date.parse(lastUpdated);
  if (Number.isNaN(parsed)) return { level: "unavailable", label: "Market data unavailable" };

  const stale = backendIsStale ?? now - parsed > BACKEND_STALE_AFTER_MS;
  return stale
    ? { level: "stale", label: "Market data is stale" }
    : { level: "fresh", label: "Updated recently" };
}
