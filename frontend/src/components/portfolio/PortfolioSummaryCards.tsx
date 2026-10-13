import type { PortfolioSummary } from "../../types/userFeatures";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";

function Card({ label, value, valueClass = "text-slate-900 dark:text-slate-100" }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="card card-pad">
      <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 text-xl font-bold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}

/** Totals exactly as calculated by the backend from the recorded holdings and CURRENT synced prices. */
export function PortfolioSummaryCards({ summary }: { summary: PortfolioSummary }) {
  const pnl = summary.total_unrealized_pnl;
  const pnlText = pnl === null ? "N/A" : `${pnl > 0 ? "+" : ""}${formatUsd(pnl)}`;
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Total value" value={formatUsd(summary.total_current_value)} />
        <Card label="Total invested" value={formatUsd(summary.total_invested)} />
        <Card label="Total P/L" value={pnlText} valueClass={changeColorClass(pnl)} />
        <Card label="P/L %" value={formatPercent(summary.total_unrealized_pnl_pct)} valueClass={changeColorClass(summary.total_unrealized_pnl_pct)} />
      </div>
      {summary.is_partial && (
        <p role="note" className="mt-2 rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          {summary.unpriced_count} of {summary.holdings_count} holdings have no market price yet, so value and P/L cover only the priced holdings.
        </p>
      )}
    </div>
  );
}
