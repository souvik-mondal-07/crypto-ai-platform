import { useEffect } from "react";

import { env } from "../config/environment";
import { useMarketStore } from "../store/marketStore";
import { usePolling } from "./usePolling";

/**
 * Clean component-facing interface over the overview/global/gainers/
 * losers slice of marketStore. Fetches all four on mount, then
 * automatically re-fetches them silently on an interval (added by the
 * real-time refresh upgrade) so
 * the Dashboard tracks live market data without a manual reload —
 * silent meaning no loading-skeleton flicker and no error banner for
 * a single missed background tick; the last good values simply stay
 * on screen until the next successful refresh.
 */
export function useMarketData() {
  const {
    marketOverview,
    marketOverviewLoading,
    marketOverviewError,
    globalMarket,
    globalMarketLoading,
    globalMarketError,
    gainers,
    gainersLoading,
    gainersError,
    losers,
    losersLoading,
    losersError,
    fetchMarketOverview,
    fetchGlobalMarket,
    fetchGainers,
    fetchLosers,
  } = useMarketStore();

  useEffect(() => {
    fetchMarketOverview();
    fetchGlobalMarket();
    fetchGainers();
    fetchLosers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  usePolling(() => {
    fetchMarketOverview({ silent: true });
    fetchGlobalMarket({ silent: true });
    fetchGainers(undefined, { silent: true });
    fetchLosers(undefined, { silent: true });
  }, env.marketRefreshIntervalMs);

  return {
    overview: marketOverview,
    overviewLoading: marketOverviewLoading,
    overviewError: marketOverviewError,
    global: globalMarket,
    globalLoading: globalMarketLoading,
    globalError: globalMarketError,
    gainers,
    gainersLoading,
    gainersError,
    losers,
    losersLoading,
    losersError,
    refetch: () => {
      fetchMarketOverview();
      fetchGlobalMarket();
      fetchGainers();
      fetchLosers();
    },
  };
}
