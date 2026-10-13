import { BarChart3, Bitcoin, Coins, Globe, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ChangeBadge } from "../common/ChangeBadge";
import { RetryError } from "../common/RetryError";
import { formatCompactUsd, formatPlainPercent } from "../../utils/formatters";
import type { GlobalMarket, MarketOverview } from "../../types/market";

interface MarketSnapshotProps {
  overview: MarketOverview | null;
  overviewLoading: boolean;
  overviewError: string | null;
  global: GlobalMarket | null;
  globalLoading: boolean;
  globalError: string | null;
  onRetry: () => void;
  /** Optional fifth card (the Dashboard passes the user's Portfolio Value) rendered in the same grid. */
  trailing?: ReactNode;
}

/** Shared grid so the cards, their skeletons and the trailing card line up: 1 → 2 → 3+2 (a 6-column grid) → 5 across on 1800px+ screens. */
export const SNAPSHOT_GRID =
  "grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 md:grid-cols-6 md:[&>*]:col-span-2 md:[&>*:nth-child(n+4)]:col-span-3 3xl:grid-cols-5 3xl:[&>*:nth-child(n+1)]:col-span-1";

/** CoinGecko keys dominance by lowercase symbol ("btc"); tolerate either case. */
function dominance(percentages: Record<string, number> | null | undefined, symbol: string): number | null {
  if (!percentages) return null;
  const match = Object.entries(percentages).find(([key]) => key.toLowerCase() === symbol);
  return match && Number.isFinite(match[1]) ? match[1] : null;
}

/** One metric card. A labelled region, so tests and screen-reader users can address a card by its name. */
export function Metric({ label, icon: Icon, children, footer, tone = "brand" }: { label: string; icon: LucideIcon; children: ReactNode; footer?: ReactNode; tone?: "brand" | "amber" | "violet" | "cyan" }) {
  const TONES = {
    brand: "from-brand-500/25 to-brand-500/5 text-brand-400 ring-brand-500/30",
    amber: "from-amber-500/25 to-amber-500/5 text-amber-400 ring-amber-500/30",
    violet: "from-brand-violet/25 to-brand-violet/5 text-violet-300 ring-brand-violet/30",
    cyan: "from-brand-cyan/25 to-brand-cyan/5 text-cyan-300 ring-brand-cyan/30",
  } as const;
  return (
    <section aria-label={label} className="card hover-lift group relative min-w-0 overflow-hidden p-4">
      <div aria-hidden="true" className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-brand-500/10 blur-2xl transition-opacity duration-300 group-hover:bg-brand-violet/20" />
      <div className="relative flex items-center gap-3">
        <span className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ${TONES[tone]}`}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="truncate text-xl font-semibold tracking-tight tabular-nums text-slate-900 dark:text-white">{children}</p>
        </div>
      </div>
      <div className="relative mt-2 min-h-[1.25rem] text-xs">{footer}</div>
    </section>
  );
}

function SnapshotSkeleton() {
  return (
    <div className={SNAPSHOT_GRID}>
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="card animate-pulse p-4 motion-reduce:animate-none">
          <div className="flex items-center gap-2.5">
            <div className="h-10 w-10 rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="h-2.5 w-16 rounded bg-slate-200 dark:bg-slate-800" />
          </div>
          <div className="mt-4 h-6 w-24 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="mt-2 h-2.5 w-12 rounded bg-slate-200 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

/**
 * Global market snapshot — four metric cards (plus the optional trailing Portfolio Value card). Only real backend values are shown; a missing metric renders "N/A"
 * (dominance and 24h change are never estimated). Volume and the coin count have no 24h change in the backend,
 * so none is shown for them. The market trend (Bullish/Bearish) is shown in the welcome banner.
 */
export function MarketSnapshot({
  overview,
  overviewLoading,
  overviewError,
  global,
  globalLoading,
  globalError,
  onRetry,
  trailing,
}: MarketSnapshotProps) {
  const loading = overviewLoading || globalLoading;
  const error = overviewError || globalError;

  if (loading) return <SnapshotSkeleton />;

  // Both sources failed: nothing real to show, so show the error alone.
  if (overviewError && globalError) {
    return (
      <div className="card p-4">
        <RetryError message={overviewError} onRetry={onRetry} compact />
      </div>
    );
  }

  const change = global?.market_cap_change_percentage_24h ?? null;
  const active = overview?.active_cryptocurrencies ?? global?.active_cryptocurrencies ?? null;
  const btc = dominance(global?.market_cap_percentage, "btc");
  const eth = dominance(global?.market_cap_percentage, "eth");

  return (
    <div>
      <div className={SNAPSHOT_GRID}>
        <Metric label="Total Market Cap" icon={Globe} tone="brand" footer={<ChangeBadge value={change} />}>
          {formatCompactUsd(global?.total_market_cap_usd ?? null)}
        </Metric>
        <Metric label="24H Volume" icon={BarChart3} tone="violet" footer={<span className="text-slate-500 dark:text-slate-400">Global, all coins</span>}>
          {formatCompactUsd(global?.total_volume_24h_usd ?? null)}
        </Metric>
        <Metric
          label="Bitcoin Dominance"
          icon={Bitcoin}
          tone="amber"
          footer={
            <span className="text-slate-500 dark:text-slate-400">
              ETH <span className="font-medium tabular-nums text-slate-700 dark:text-slate-200">{formatPlainPercent(eth, 1)}</span>
            </span>
          }
        >
          {formatPlainPercent(btc, 1)}
        </Metric>
        <Metric label="Tracked Coins" icon={Coins} tone="cyan" footer={<span className="text-slate-500 dark:text-slate-400">Active cryptocurrencies</span>}>
          {active !== null ? active.toLocaleString() : "N/A"}
        </Metric>
        {trailing}
      </div>
      {error && (
        <div className="mt-3">
          <RetryError message={error} onRetry={onRetry} compact />
        </div>
      )}
    </div>
  );
}
