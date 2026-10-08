import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { changeColorClass, formatPercent } from "../../utils/formatters";

interface ChangeBadgeProps {
  value: number | null | undefined;
  /** "text" = coloured text only; "pill" = tinted background (movers, tooltips). */
  variant?: "text" | "pill";
  className?: string;
}

/**
 * A percentage change that never relies on colour alone: it always carries a
 * +/- sign (from `formatPercent`) AND a direction arrow. Missing values render
 * "N/A" with no arrow — never a fabricated 0%.
 */
export function ChangeBadge({ value, variant = "text", className = "" }: ChangeBadgeProps) {
  const hasValue = value !== null && value !== undefined;
  const Icon = !hasValue || value === 0 ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight;

  const pill =
    variant === "pill"
      ? !hasValue || value === 0
        ? "rounded-md bg-slate-100 px-1.5 py-0.5 dark:bg-slate-800"
        : value > 0
          ? "rounded-md bg-emerald-50 px-1.5 py-0.5 dark:bg-emerald-950/50"
          : "rounded-md bg-red-50 px-1.5 py-0.5 dark:bg-red-950/50"
      : "";

  return (
    <span className={`inline-flex items-center gap-0.5 font-medium tabular-nums ${changeColorClass(value)} ${pill} ${className}`}>
      <Icon className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
      {formatPercent(value)}
    </span>
  );
}
