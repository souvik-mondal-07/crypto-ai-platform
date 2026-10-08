import { useEffect } from "react";

import { env } from "../config/environment";
import { useMarketStore } from "../store/marketStore";
import { usePolling } from "./usePolling";

/**
 * Component-facing interface over the Markets-table slice of
 * marketStore. Sorting, filtering, and pagination all round-trip to
 * the backend (`/market/coins`) — the browser never holds more than
 * the current page.
 *
 * Silently re-fetches the *current* page/sort/filter on an interval
 * (added by the real-time refresh upgrade), so prices update in place without resetting the user's
 * page, sort, filter, or search state and without a loading flicker.
 */
export function useMarketCoins(options: { autoLoad?: boolean } = {}) {
  const autoLoad = options.autoLoad ?? true;
  const {
    marketCoins,
    marketCoinsPage,
    marketCoinsPages,
    marketCoinsTotal,
    marketCoinsLimit,
    marketCoinsLoading,
    marketCoinsError,
    marketSortBy,
    marketSortDirection,
    marketFilter,
    marketFilters,
    marketCoinIds,
    marketLastUpdated,
    marketIsStale,
    marketUniverseTotal,
    fetchMarketCoins,
    setMarketFilters,
    setMarketView,
    setMarketSort,
    setMarketFilter,
    setMarketPageSize,
  } = useMarketStore();

  useEffect(() => {
    // The Markets page applies its own initial view (tab / URL filters) in a
    // single request, so it opts out of this default load to avoid a duplicate.
    if (autoLoad) fetchMarketCoins(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  usePolling(() => {
    fetchMarketCoins(undefined, { silent: true });
  }, env.marketRefreshIntervalMs);

  return {
    coins: marketCoins,
    page: marketCoinsPage,
    pages: marketCoinsPages,
    total: marketCoinsTotal,
    limit: marketCoinsLimit,
    loading: marketCoinsLoading,
    error: marketCoinsError,
    sortBy: marketSortBy,
    sortDirection: marketSortDirection,
    filter: marketFilter,
    filters: marketFilters,
    coinIds: marketCoinIds,
    lastUpdated: marketLastUpdated,
    isStale: marketIsStale,
    universeTotal: marketUniverseTotal,
    setFilters: setMarketFilters,
    setView: setMarketView,
    setSort: setMarketSort,
    setFilter: setMarketFilter,
    setPageSize: setMarketPageSize,
    goToPage: fetchMarketCoins,
    refetch: () => fetchMarketCoins(),
  };
}
