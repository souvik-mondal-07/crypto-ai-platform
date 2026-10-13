import { Link } from "react-router-dom";
import { ArrowRight, Wallet } from "lucide-react";

import { useAuthStore } from "../../store/authStore";
import { usePortfolioStore } from "../../store/portfolioStore";
import { changeColorClass, formatPercent, formatUsd } from "../../utils/formatters";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { Skeleton } from "../ui/Skeleton";

const COLORS = ["#5b8cff", "#a855f7", "#22d3ee", "#f59e0b", "#10b981", "#f43f5e"];
const RADIUS = 40;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** Allocation ring: one arc per priced holding (percentages come from the backend). */
function Donut({ slices, total }: { slices: { key: string; pct: number; color: string }[]; total: string }) {
  let offset = 0;
  return (
    <div className="relative h-32 w-32 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" role="img" aria-label="Portfolio allocation">
        <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="currentColor" strokeWidth="12" className="text-slate-100 dark:text-white/[0.07]" />
        {slices.map((slice) => {
          const length = (slice.pct / 100) * CIRCUMFERENCE;
          const arc = (
            <circle
              key={slice.key}
              cx="50"
              cy="50"
              r={RADIUS}
              fill="none"
              stroke={slice.color}
              strokeWidth="12"
              strokeDasharray={`${Math.max(length - 1.2, 0)} ${CIRCUMFERENCE}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          );
          offset += length;
          return arc;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-[10px] text-slate-500 dark:text-slate-400">Total</span>
        <span className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">{total}</span>
      </div>
    </div>
  );
}

/**
 * The signed-in user's real portfolio (GET /portfolio via the shared portfolio store, loaded once by the Dashboard):
 * total value, P/L and allocation. Never sample data.
 */
export function PortfolioWidget() {
  const userId = useAuthStore((state) => state.user?.id ?? null);
  const portfolio = usePortfolioStore((state) => state.portfolio);
  const status = usePortfolioStore((state) => state.status);
  const loadError = usePortfolioStore((state) => state.error);
  const reload = usePortfolioStore((state) => state.reload);
  const error = status === "error" ? loadError ?? "Your portfolio could not be loaded." : null;

  const priced = portfolio?.holdings.filter((holding) => holding.allocation_pct !== null && holding.allocation_pct > 0) ?? [];
  const top = priced.slice(0, 5);
  const rest = priced.slice(5).reduce((sum, holding) => sum + (holding.allocation_pct ?? 0), 0);
  const slices = [
    ...top.map((holding, index) => ({ key: holding.coin_id, label: holding.symbol.toUpperCase(), pct: holding.allocation_pct ?? 0, color: COLORS[index] })),
    ...(rest > 0 ? [{ key: "other", label: "Others", pct: rest, color: COLORS[5] }] : []),
  ];

  return (
    <section id="portfolio-widget" aria-labelledby="portfolio-widget-heading" className="card card-pad h-full">
      <SectionHeading
        id="portfolio-widget-heading"
        title="Portfolio"
                actions={<Link to="/portfolio" className="inline-flex items-center gap-1 text-xs font-medium text-sky-700 hover:underline dark:text-sky-400">View All <ArrowRight className="h-3 w-3" aria-hidden="true" /></Link>}
      />

      {!userId ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">Sign in to see your portfolio value and allocation here.</p>
      ) : error ? (
        <RetryError message={error} onRetry={() => void reload()} compact />
      ) : portfolio === null ? (
        <div className="flex items-center gap-4" aria-hidden="true">
          <Skeleton className="h-32 w-32 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-24" />
          </div>
        </div>
      ) : portfolio.holdings.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-slate-300 p-4 dark:border-white/15">
          <p className="text-sm text-slate-500 dark:text-slate-400">Your portfolio is empty. Add a holding to see its value and allocation here.</p>
          <Link to="/portfolio" className="btn-secondary !min-h-[2rem] text-xs">
            <Wallet className="h-3.5 w-3.5" aria-hidden="true" />
            Add a holding
          </Link>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-5">
          <Donut slices={slices} total={formatUsd(portfolio.summary.total_current_value)} />
          <div className="min-w-0 flex-1">
            <p className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">{formatUsd(portfolio.summary.total_current_value)}</p>
            <p className={`text-sm font-medium tabular-nums ${changeColorClass(portfolio.summary.total_unrealized_pnl_pct)}`}>
              {portfolio.summary.total_unrealized_pnl === null ? "P/L N/A" : `${portfolio.summary.total_unrealized_pnl > 0 ? "+" : ""}${formatUsd(portfolio.summary.total_unrealized_pnl)}`}{" "}
              <span className="text-xs">({formatPercent(portfolio.summary.total_unrealized_pnl_pct)})</span>
            </p>
            <ul className="mt-3 space-y-1 text-xs">
              {slices.map((slice) => (
                <li key={slice.key} className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ backgroundColor: slice.color }} />
                  <span>{"label" in slice ? slice.label : ""}</span>
                  <span className="ml-auto tabular-nums text-slate-500 dark:text-slate-400">{slice.pct.toFixed(1)}%</span>
                </li>
              ))}
            </ul>
            {portfolio.summary.is_partial && (
              <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">Some holdings have no market price yet.</p>
            )}
          </div>
        </div>
      )}

      <Link to="/portfolio" className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-brand-500/40 bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-600 transition-colors hover:bg-brand-500/20 dark:text-brand-400">
        View Portfolio <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </Link>
    </section>
  );
}
