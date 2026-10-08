import { useCallback } from "react";

import { AppShell } from "../components/layout/AppShell";
import { MarketSnapshot } from "../components/dashboard/MarketSnapshot";
import { MarketPerformance } from "../components/dashboard/MarketPerformance";
import { MarketMovers } from "../components/dashboard/MarketMovers";
import { MarketHeatmap } from "../components/dashboard/MarketHeatmap";
import { QuickDiscovery } from "../components/dashboard/QuickDiscovery";
import { RecentlyViewed } from "../components/dashboard/RecentlyViewed";
import { LatestNews } from "../components/dashboard/LatestNews";
import { FreshnessBadge } from "../components/common/FreshnessBadge";
import { useAuthStore } from "../store/authStore";
import { useMarketData } from "../hooks/useMarketData";
import { useDashboardData } from "../hooks/useDashboardData";

/**
 * Dashboard — "What is happening in the crypto market right now?"
 *
 * A read-only command center: global snapshot, performance chart, movers,
 * heatmap and shortcuts. It deliberately has no search box, filters, sort
 * controls or paginated table — exploration lives on /markets. The greeting
 * uses `user.name` from authStore (sourced from GET /auth/me, never a sample
 * value — see docs/authentication.md).
 *
 * Data: `useMarketData` (overview/global/gainers/losers) and
 * `useDashboardData` (heatmap set) each poll once on the shared interval;
 * sections read from stores and never poll on their own.
 */
export function Dashboard() {
  const user = useAuthStore((state) => state.user);
  const market = useMarketData();
  const { heatmap, refetch: refetchHeatmap } = useDashboardData();

  const retrySnapshot = useCallback(() => market.refetch(), [market]);

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {user?.name ? `Welcome back, ${user.name}. ` : ""}Here&apos;s what&apos;s happening in the crypto market.
          </p>
        </div>
        <FreshnessBadge lastUpdated={market.overview?.last_updated ?? market.global?.last_updated} />
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <MarketSnapshot
          overview={market.overview}
          overviewLoading={market.overviewLoading}
          overviewError={market.overviewError}
          global={market.global}
          globalLoading={market.globalLoading}
          globalError={market.globalError}
          onRetry={retrySnapshot}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <MarketPerformance
            coins={heatmap.data}
            loading={heatmap.loading}
            error={heatmap.error}
            onRetry={refetchHeatmap}
          />
        </div>
        <MarketMovers />
      </div>

      <div className="mt-6">
        <MarketHeatmap coins={heatmap.data} loading={heatmap.loading} error={heatmap.error} onRetry={refetchHeatmap} />
      </div>

      <div className="mt-6">
        <QuickDiscovery />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RecentlyViewed />
        <LatestNews />
      </div>
    </AppShell>
  );
}
