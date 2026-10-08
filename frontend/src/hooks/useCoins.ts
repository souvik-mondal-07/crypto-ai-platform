import { useEffect } from "react";

import { useMarketStore } from "../store/marketStore";
import { useDebouncedValue } from "./useDebouncedValue";

/**
 * Clean component-facing interface over the coin-listing/search slice
 * of marketStore. Handles debouncing search input internally so
 * components never need to wire up useDebouncedValue themselves.
 */
export function useCoins() {
  const {
    coins,
    coinsPage,
    coinsPages,
    coinsTotal,
    coinsLoading,
    coinsError,
    coinMarketData,
    searchQuery,
    searchResults,
    searchLoading,
    searchError,
    sortBy,
    sortDirection,
    fetchCoins,
    setSearchQuery,
    setSort,
  } = useMarketStore();

  const debouncedQuery = useDebouncedValue(searchQuery, 350);
  const searchCoinsAction = useMarketStore((state) => state.searchCoins);

  const isSearching = debouncedQuery.trim().length > 0;

  useEffect(() => {
    searchCoinsAction(debouncedQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery]);

  useEffect(() => {
    if (!isSearching) {
      fetchCoins(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSearching]);

  return {
    // Whichever list is relevant right now — search results while
    // actively searching, otherwise the paginated coin list.
    coins: isSearching ? searchResults ?? [] : coins,
    isSearching,
    coinMarketData,
    loading: isSearching ? searchLoading : coinsLoading,
    error: isSearching ? searchError : coinsError,
    page: coinsPage,
    pages: coinsPages,
    total: coinsTotal,
    sortBy,
    sortDirection,
    searchQuery,
    setSearchQuery,
    setSort,
    goToPage: fetchCoins,
    refetch: () => (isSearching ? searchCoinsAction(debouncedQuery) : fetchCoins()),
  };
}
