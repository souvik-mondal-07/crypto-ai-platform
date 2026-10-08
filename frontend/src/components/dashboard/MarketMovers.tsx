import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { env } from "../../config/environment";
import { usePolling } from "../../hooks/usePolling";
import { MOVERS_SIZE, useDashboardStore } from "../../store/dashboardStore";
import { useMarketStore } from "../../store/marketStore";
import { ChangeBadge } from "../common/ChangeBadge";
import { EmptyState } from "../common/EmptyState";
import { RetryError } from "../common/RetryError";
import { SectionHeading } from "../common/SectionHeading";
import { CoinLogo } from "../market/CoinLogo";
import { SkeletonMoverCard } from "../market/Skeletons";
import { formatCompactUsd, formatPlainPercent, formatUsd } from "../../utils/formatters";
import type { MarketCoin, MoverItem } from "../../types/market";
import type { MarketTabKey } from "../../utils/marketFilters";

type MoverTab = "gainers" | "losers" | "volume" | "volatility";

interface Row {
  id: string;
  name: string;
  symbol: string;
  logo: string | null;
  price: number | null;
  change: number | null;
  volume: number | null;
  volatility: number | null;
}

const fromMover = (item: MoverItem): Row => ({
  id: item.coin_id,
  name: item.name,
  symbol: item.symbol,
  logo: item.logo_url,
  price: item.price_usd,
  change: item.percent_change_24h,
  volume: item.volume_24h_usd ?? null,
  volatility: item.volatility_24h_pct ?? null,
});

const fromMarketCoin = (coin: MarketCoin): Row => ({
  id: coin.coin_id,
  name: coin.name,
  symbol: coin.symbol,
  logo: coin.logo_url,
  price: coin.price_usd,
  change: coin.percent_change_24h,
  volume: coin.volume_24h_usd,
  volatility: coin.volatility_24h_pct ?? null,
});

const TABS: { key: MoverTab; label: string; metric: string; empty: string; marketsTab: MarketTabKey }[] = [
  { key: "gainers", label: "Gainers", metric: "24H Volume", empty: "No gainer data available yet.", marketsTab: "gainers" },
  { key: "losers", label: "Losers", metric: "24H Volume", empty: "No loser data available yet.", marketsTab: "losers" },
  { key: "volume", label: "Highest Volume", metric: "24H Volume", empty: "No volume data available yet.", marketsTab: "volume" },
  { key: "volatility", label: "Highest Volatility", metric: "24H Range", empty: "No volatility data available yet.", marketsTab: "volatility" },
];

/**
 * Market Movers: a concise top-N for four lenses on the market. Gainers and
 * losers reuse the existing `/market/gainers|losers` data already loaded by
 * the Dashboard; volume reuses `/market/top/volume`; volatility is the
 * server-sorted `/market/coins?sort_by=volatility`. It is deliberately NOT a
 * second Markets table — it shows ~8 rows and links through to the explorer.
 *
 * The volume/volatility datasets are fetched (and polled) only while their
 * tab is open, so an unused tab costs no requests.
 */
export function MarketMovers() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<MoverTab>("gainers");

  const gainers = useMarketStore((state) => state.gainers);
  const gainersLoading = useMarketStore((state) => state.gainersLoading);
  const gainersError = useMarketStore((state) => state.gainersError);
  const losers = useMarketStore((state) => state.losers);
  const losersLoading = useMarketStore((state) => state.losersLoading);
  const losersError = useMarketStore((state) => state.losersError);
  const fetchGainers = useMarketStore((state) => state.fetchGainers);
  const fetchLosers = useMarketStore((state) => state.fetchLosers);

  const volume = useDashboardStore((state) => state.volume);
  const volatility = useDashboardStore((state) => state.volatility);
  const fetchVolume = useDashboardStore((state) => state.fetchVolume);
  const fetchVolatility = useDashboardStore((state) => state.fetchVolatility);

  useEffect(() => {
    if (tab === "volume") fetchVolume();
    if (tab === "volatility") fetchVolatility();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  usePolling(
    () => {
      if (tab === "volume") fetchVolume({ silent: true });
      if (tab === "volatility") fetchVolatility({ silent: true });
    },
    env.marketRefreshIntervalMs,
    tab === "volume" || tab === "volatility"
  );

  const { rows, loading, error, retry } = useMemo(() => {
    switch (tab) {
      case "gainers":
        return {
          rows: gainers.map(fromMover),
          loading: gainersLoading,
          error: gainersError,
          retry: () => fetchGainers(),
        };
      case "losers":
        return {
          rows: losers.map(fromMover),
          loading: losersLoading,
          error: losersError,
          retry: () => fetchLosers(),
        };
      case "volume":
        return {
          rows: volume.data.map(fromMover),
          loading: volume.loading,
          error: volume.error,
          retry: () => fetchVolume(),
        };
      default:
        return {
          rows: volatility.data.map(fromMarketCoin),
          loading: volatility.loading,
          error: volatility.error,
          retry: () => fetchVolatility(),
        };
    }
  }, [
    tab, gainers, gainersLoading, gainersError, losers, losersLoading, losersError,
    volume, volatility, fetchGainers, fetchLosers, fetchVolume, fetchVolatility,
  ]);

  const active = TABS.find((candidate) => candidate.key === tab)!;
  const visible = rows.slice(0, MOVERS_SIZE);

  return (
    <section aria-labelledby="market-movers-heading" className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <SectionHeading id="market-movers-heading" title="Market Movers" description="Top 24H activity across the market" />

      <div role="tablist" aria-label="Market movers" className="mb-3 flex flex-wrap gap-0.5 rounded-lg border border-slate-200 p-0.5 dark:border-slate-700">
        {TABS.map((candidate) => (
          <button
            key={candidate.key}
            type="button"
            role="tab"
            aria-selected={candidate.key === tab}
            onClick={() => setTab(candidate.key)}
            className={`flex-1 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              candidate.key === tab
                ? "bg-slate-900 text-white dark:bg-sky-600"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            }`}
          >
            {candidate.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={active.label} className="flex-1">
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, index) => (
              <SkeletonMoverCard key={index} />
            ))}
          </div>
        )}

        {!loading && error && <RetryError message={error} onRetry={retry} compact />}

        {!loading && !error && visible.length === 0 && <EmptyState message={active.empty} />}

        {!loading && !error && visible.length > 0 && (
          <ol className="divide-y divide-slate-100 dark:divide-slate-800">
            {visible.map((row, index) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/coins/${row.id}`)}
                  className="flex w-full items-center gap-3 rounded-md px-1 py-2 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 dark:hover:bg-slate-800/60"
                >
                  <span className="w-4 text-center text-xs tabular-nums text-slate-400">{index + 1}</span>
                  <CoinLogo src={row.logo} alt="" size={28} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">{row.name}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {row.symbol.toUpperCase()}
                      <span className="mx-1 text-slate-300 dark:text-slate-600" aria-hidden="true">·</span>
                      <span title={active.metric}>
                        {tab === "volatility" ? formatPlainPercent(row.volatility, 1) : formatCompactUsd(row.volume)}
                      </span>
                      <span className="sr-only"> {active.metric}</span>
                    </span>
                  </span>
                  <span className="flex-shrink-0 text-right">
                    <span className="block text-sm font-medium tabular-nums text-slate-800 dark:text-slate-100">{formatUsd(row.price)}</span>
                    <ChangeBadge value={row.change} className="text-xs" />
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>

      <Link
        to={`/markets?tab=${active.marketsTab}`}
        className="mt-3 inline-flex items-center gap-1 self-start text-xs font-medium text-sky-600 hover:underline dark:text-sky-400"
      >
        View all in Markets <ArrowRight className="h-3 w-3" aria-hidden="true" />
      </Link>
    </section>
  );
}
