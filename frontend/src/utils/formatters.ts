/**
 * Shared formatting helpers for market data. Every function handles
 * `null`/`undefined` by returning a clear "N/A" — never a fabricated
 * number, never `NaN` or `undefined` rendered directly into the UI.
 */

const NOT_AVAILABLE = "N/A";

export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  if (value >= 1) {
    return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
  }
  // Sub-$1 coins need more precision to be meaningful.
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 6 });
}

export function formatCompactUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return value.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 });
}

/** Tailwind text color class for a percentage change — green/red/neutral, dark-mode aware. Never used as the only signal (text still shows +/-). */
export function changeColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "text-slate-400 dark:text-slate-500";
  if (value > 0) return "text-emerald-600 dark:text-emerald-400";
  if (value < 0) return "text-red-600 dark:text-red-400";
  return "text-slate-500 dark:text-slate-400";
}

/**
 * Relative time ("2 minutes ago"). Added here rather than in a new
 * formatDate.ts so there's one formatting module, not two.
 */
export function formatRelativeTime(isoTimestamp: string | null | undefined): string {
  if (!isoTimestamp) return NOT_AVAILABLE;
  const parsed = new Date(isoTimestamp);
  if (Number.isNaN(parsed.getTime())) return NOT_AVAILABLE;

  const seconds = Math.round((Date.now() - parsed.getTime()) / 1000);
  if (seconds < 0) return "just now"; // clock skew — don't render "in -3 seconds"
  if (seconds < 60) return "just now";

  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["minute", 60],
    ["hour", 3600],
    ["day", 86400],
    ["month", 2592000],
    ["year", 31536000],
  ];

  let chosen: [Intl.RelativeTimeFormatUnit, number] = units[0];
  for (const unit of units) {
    if (seconds >= unit[1]) chosen = unit;
  }

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  return formatter.format(-Math.floor(seconds / chosen[1]), chosen[0]);
}

/** Absolute date/time, used as a title/tooltip alongside the relative form. */
export function formatAbsoluteDateTime(isoTimestamp: string | null | undefined): string {
  if (!isoTimestamp) return NOT_AVAILABLE;
  const parsed = new Date(isoTimestamp);
  if (Number.isNaN(parsed.getTime())) return NOT_AVAILABLE;
  return parsed.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

/** Plain number with thousands separators — for supply figures, which aren't currency. */
export function formatSupply(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

/** Plain decimal (not currency, not a percent) — for indicator values like RSI or ATR. */
export function formatDecimal(value: number | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return value.toLocaleString("en-US", { maximumFractionDigits });
}

/** Unsigned percentage (e.g. share of supply) — unlike `formatPercent`, never prefixes "+". */
export function formatPlainPercent(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return `${value.toFixed(fractionDigits)}%`;
}

/** A unitless ratio (e.g. 0.0512) as a fixed-precision decimal. */
export function formatRatio(value: number | null | undefined, fractionDigits = 4): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return value.toFixed(fractionDigits);
}
