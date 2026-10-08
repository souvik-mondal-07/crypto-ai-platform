import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { changeColorClass, formatCompactUsd, formatPlainPercent } from "../../utils/formatters";
import type { GlobalMarket, MarketOverview } from "../../types/market";

interface MarketSnapshotProps {
  overview: MarketOverview | null;
  overviewLoading: boolean;
  overviewError: string | null;
  global: GlobalMarket | null;
  globalLoading: boolean;
  globalError: string | null;
  onRetry: () => void;
}

/** CoinGecko keys dominance by lowercase symbol ("btc"); tolerate either case. */
function dominance(percentages: Record<string, number> | null | undefined, symbol: string): number | null {
  if (!percentages) return null;
  const match = Object.entries(percentages).find(([key]) => key.toLowerCase() === symbol);
  return match && Number.isFinite(match[1]) ? match[1] : null;
}

function Metric({ label, children, footer }: { label: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="px-4 py-3 sm:px-5">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">{children}</dd>
      <div className="mt-0.5 min-h-[1.25rem] text-xs">{footer}</div>
    </div>
  );
}

function SnapshotSkeleton() {
  return (
    <div className="grid grid-cols-2 divide-slate-200 dark:divide-slate-800 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="animate-pulse px-4 py-3 sm:px-5">
          <div className="h-2.5 w-20 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="mt-3 h-5 w-24 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="mt-2 h-2.5 w-12 rounded bg-slate-200 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

/**
 * Global market snapshot — a divided metric strip rather than six separate
 * cards. Only real backend values are shown; a missing metric renders "N/A"
 * (dominance and 24h change are never estimated). Volume has no 24h change in
 * the backend, so none is shown for it.
 */
export function MarketSnapshot({
  overview,
  overviewLoading,
  overviewError,
  global,
  globalLoading,
  globalError,
  onRetry,
}: MarketSnapshotProps) {
  const loading = overviewLoading || globalLoading;
  const error = overviewError || globalError;

  if (loading) return <SnapshotSkeleton />;

  // Both sources failed: nothing real to show, so show the error alone.
  if (overviewError && globalError) {
    return (
      <div className="p-4">
        <RetryError message={overviewError} onRetry={onRetry} compact />
      </div>
    );
  }

  const change = global?.market_cap_change_percentage_24h ?? null;
  const trendLabel = change === null ? "N/A" : change > 0 ? "Bullish" : change < 0 ? "Bearish" : "Neutral";
  const TrendIcon = change === null || change === 0 ? Minus : change > 0 ? TrendingUp : TrendingDown;

  const active = overview?.active_cryptocurrencies ?? global?.active_cryptocurrencies ?? null;
  const btc = dominance(global?.market_cap_percentage, "btc");
  const eth = dominance(global?.market_cap_percentage, "eth");

  return (
    <div>
      <dl className="grid grid-cols-2 divide-slate-200 dark:divide-slate-800 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
        <Metric label="Total Market Cap" footer={<ChangeBadge value={change} />}>
          {formatCompactUsd(global?.total_market_cap_usd ?? null)}
        </Metric>
        <Metric label="24H Volume">{formatCompactUsd(global?.total_volume_24h_usd ?? null)}</Metric>
        <Metric label="Active Cryptocurrencies">{active !== null ? active.toLocaleString() : "N/A"}</Metric>
        <Metric label="BTC Dominance">{formatPlainPercent(btc, 1)}</Metric>
        <Metric label="ETH Dominance">{formatPlainPercent(eth, 1)}</Metric>
        <Metric
          label="Market Trend"
          footer={<span className="text-slate-500 dark:text-slate-400">Total market cap, 24H</span>}
        >
          <span className={`inline-flex items-center gap-1.5 ${changeColorClass(change)}`}>
            <TrendIcon className="h-4 w-4" aria-hidden="true" />
            {trendLabel}
          </span>
        </Metric>
      </dl>
      {error && (
        <div className="border-t border-slate-200 p-3 dark:border-slate-800">
          <RetryError message={error} onRetry={onRetry} compact />
        </div>
      )}
    </div>
  );
}
