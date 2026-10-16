/**
 * Formatting for Phase 17. Backend ratios are FRACTIONS (0.0123 == 1.23%). `null` always renders as "N/A":
 * a metric that could not be computed is never shown as 0.
 */
import { formatAbsoluteDateTime, formatUsd } from "./formatters";

export const NOT_AVAILABLE = "N/A";

export function fractionToPercent(value: number | null | undefined, digits = 2, signed = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NOT_AVAILABLE;
  const pct = value * 100;
  const sign = signed && pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(digits)}%`;
}

/** Return errors (MAE/RMSE) are in return units; show them as percentage points. */
export function formatPoints(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NOT_AVAILABLE;
  return `${(value * 100).toFixed(digits)} pp`;
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NOT_AVAILABLE;
  return value.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function formatDay(iso: string | null | undefined): string {
  if (!iso) return NOT_AVAILABLE;
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return NOT_AVAILABLE;
  return parsed.toLocaleDateString("en-US", { dateStyle: "medium", timeZone: "UTC" });
}

export function formatPeriod(start: string | null | undefined, end: string | null | undefined): string {
  if (!start || !end) return NOT_AVAILABLE;
  return `${formatDay(start)} – ${formatDay(end)}`;
}

export const modelVersionKey = (model: string | null | undefined, version: string | null | undefined): string =>
  model ? `${model}|${version ?? ""}` : "";

export const modelVersionLabel = (model: string | null | undefined, version: string | null | undefined): string =>
  model ? `${model}${version ? ` v${version}` : ""}` : "Unknown model";

export function returnClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-slate-900 dark:text-slate-100";
  return value > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
}

export { formatAbsoluteDateTime, formatUsd };
