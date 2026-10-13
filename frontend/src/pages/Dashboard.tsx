import { useCallback } from "react";

import { AppShell } from "../components/layout/AppShell";
import { AiInsightsPanel } from "../components/dashboard/AiInsightsPanel";
import { DashboardHero } from "../components/dashboard/DashboardHero";
import { LatestNews } from "../components/dashboard/LatestNews";
import { MarketHeatmap } from "../components/dashboard/MarketHeatmap";
import { MarketMovers } from "../components/dashboard/MarketMovers";
import { MarketPerformance } from "../components/dashboard/MarketPerformance";
import { MarketSnapshot } from "../components/dashboard/MarketSnapshot";
import { PortfolioValueCard } from "../components/dashboard/PortfolioValueCard";
import { PortfolioWidget } from "../components/dashboard/PortfolioWidget";
import { QuickActions } from "../components/dashboard/QuickActions";
import { QuickDiscovery } from "../components/dashboard/QuickDiscovery";
import { RecentlyViewed } from "../components/dashboard/RecentlyViewed";
import { WatchedCoins } from "../components/dashboard/WatchedCoins";
import { useAuthStore } from "../store/authStore";
import { useMarketData } from "../hooks/useMarketData";
import { useDashboardData } from "../hooks/useDashboardData";
import { usePortfolio } from "../hooks/usePortfolio";
import { useLoadActiveAlertCount } from "../hooks/useActiveAlertCount";

/**
 * Dashboard — "What is happening in the crypto market right now?"
 *
 * A read-only command center. Left column: welcome banner, the five statistic cards (four global market metrics +
 * the user's Portfolio Value), the Bitcoin/Ethereum price chart and the heatmap. Right column: AI Market Insights.
 * Below: Top Movers, Portfolio, Watchlist, Latest News and Quick Actions (plus Quick Discovery and Recently Viewed).
 * It deliberately has no search box, filters, sort controls or paginated table — exploration lives on /markets.
 * The greeting uses `user.name` from authStore (sourced from GET /auth/me, never a sample value).
 *
 * Layout: one column below xl; from xl the AI column sits beside the left column; the chart and heatmap sit side by
 * side from 1400px and the five cards share one row from 1800px, so no panel is ever squeezed below a usable width.
 *
 * Data: `useMarketData` (overview/global/gainers/losers), `useDashboardData` (heatmap set) and the portfolio store
 * each load once; sections read from stores and never poll on their own.
 */
export function Dashboard() {
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const market = useMarketData();
  const { heatmap, refetch: refetchHeatmap } = useDashboardData();
  usePortfolio();
  useLoadActiveAlertCount();

  const retrySnapshot = useCallback(() => market.refetch(), [market]);

  // The dataset is sorted by market cap, so the first coin is the largest; the AI panel explains that coin.
  const insightCoin = heatmap.data[0] ?? null;
  const aiAnalysisPath = insightCoin ? `/coins/${insightCoin.coin_id}#coin-ai-analysis` : "/markets";

  return (
    <AppShell>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4">
          <DashboardHero
            name={user?.name}
            change24h={market.global?.market_cap_change_percentage_24h}
            lastUpdated={market.overview?.last_updated ?? market.global?.last_updated}
          />

          <MarketSnapshot
            overview={market.overview}
            overviewLoading={market.overviewLoading}
            overviewError={market.overviewError}
            global={market.global}
            globalLoading={market.globalLoading}
            globalError={market.globalError}
            onRetry={retrySnapshot}
            trailing={<PortfolioValueCard />}
          />

          <div className="grid grid-cols-1 gap-4 min-[1400px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
            <MarketPerformance coins={heatmap.data} loading={heatmap.loading} error={heatmap.error} onRetry={refetchHeatmap} />
            <MarketHeatmap compact coins={heatmap.data} loading={heatmap.loading} error={heatmap.error} onRetry={refetchHeatmap} />
          </div>
        </div>

        <div className="min-w-0">
          <AiInsightsPanel
            coin={insightCoin ? { coin_id: insightCoin.coin_id, name: insightCoin.name, symbol: insightCoin.symbol } : null}
            coinsLoading={heatmap.loading}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <MarketMovers />
        <PortfolioWidget />
        <div className="lg:col-span-2 xl:col-span-1">
          <WatchedCoins />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <LatestNews />
        <QuickActions aiAnalysisPath={aiAnalysisPath} canSearch={isAuthenticated} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card card-pad">
          <QuickDiscovery />
        </div>
        <div className="card card-pad">
          <RecentlyViewed />
        </div>
      </div>
    </AppShell>
  );
}
