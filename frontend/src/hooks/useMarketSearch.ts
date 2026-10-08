import { useEffect } from "react";

import { useMarketStore } from "../store/marketStore";
import { useDebouncedValue } from "./useDebouncedValue";

/**
 * The Markets page's search slice (name / symbol / slug via /coins/search).
 * Split from `useCoins` because that hook also loads the plain `/coins`
 * listing, which the redesigned Markets page doesn't use — keeping it would
 * be an extra request on every visit.
 */
export function useMarketSearch() {
  const searchQuery = useMarketStore((state) => state.searchQuery);
  const searchResults = useMarketStore((state) => state.searchResults);
  const searchLoading = useMarketStore((state) => state.searchLoading);
  const searchError = useMarketStore((state) => state.searchError);
  const setSearchQuery = useMarketStore((state) => state.setSearchQuery);
  const searchCoins = useMarketStore((state) => state.searchCoins);

  const debounced = useDebouncedValue(searchQuery, 350);
  const isSearching = debounced.trim().length > 0;

  useEffect(() => {
    searchCoins(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  return {
    searchQuery,
    setSearchQuery,
    isSearching,
    results: searchResults ?? [],
    loading: searchLoading || searchQuery.trim() !== debounced.trim(),
    error: searchError,
    retry: () => searchCoins(debounced),
  };
}
