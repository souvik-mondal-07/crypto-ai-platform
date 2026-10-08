import { TrendingDown, TrendingUp } from "lucide-react";

import { SkeletonCard } from "./Skeletons";
import { ErrorMessage } from "../common/ErrorMessage";
import { changeColorClass, formatCompactUsd, formatPercent } from "../../utils/formatters";
import type { GlobalMarket, MarketOverview } from "../../types/market";

interface OverviewCardsProps {
  overview: MarketOverview | null;
  overviewLoading: boolean;
  overviewError: string | null;
  global: GlobalMarket | null;
  globalLoading: boolean;
  globalError: string | null;
}

function StatCard({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1.5 text-lg font-semibold text-slate-900 dark:text-slate-100 ${valueClassName ?? ""}`}>
        {value}
      </p>
    </div>
  );
}

/**
 * Only ever renders values the backend actually returned — a null
 * field (e.g. global stats temporarily unavailable) shows "N/A" via
 * the formatters, never a fabricated number.
 */
export function MarketOverviewCards({
  overview,
  overviewLoading,
  overviewError,
  global,
  globalLoading,
  globalError,
}: OverviewCardsProps) {
  const loading = overviewLoading || globalLoading;

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (overviewError || globalError) {
    return <ErrorMessage message={overviewError || globalError || "Unable to load market statistics."} />;
  }

  const marketCapChange = global?.market_cap_change_percentage_24h ?? null;
  const trendLabel = marketCapChange === null ? "N/A" : marketCapChange >= 0 ? "Bullish" : "Bearish";
  const TrendIcon = marketCapChange !== null && marketCapChange < 0 ? TrendingDown : TrendingUp;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatCard label="Total Market Cap" value={formatCompactUsd(global?.total_market_cap_usd ?? null)} />
      <StatCard label="24h Volume" value={formatCompactUsd(global?.total_volume_24h_usd ?? null)} />
      <StatCard
        label="Active Cryptocurrencies"
        value={
          overview?.active_cryptocurrencies !== undefined ? overview.active_cryptocurrencies.toLocaleString() : "N/A"
        }
      />
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Market Trend (24h)</p>
        <p className={`mt-1.5 flex items-center gap-1.5 text-lg font-semibold ${changeColorClass(marketCapChange)}`}>
          <TrendIcon className="h-4 w-4" aria-hidden="true" />
          {trendLabel}
          <span className="text-sm font-normal">({formatPercent(marketCapChange)})</span>
        </p>
      </div>
    </div>
  );
}
