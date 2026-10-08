import { create } from "zustand";

import { fetchCoins as apiFetchCoins, searchCoins as apiSearchCoins, type ListCoinsParams } from "../services/api/coins.api";
import {
  fetchCoinMarketData as apiFetchCoinMarketData,
  fetchMarketCoins as apiFetchMarketCoins,
  fetchGainers as apiFetchGainers,
  fetchGlobalMarket as apiFetchGlobalMarket,
  fetchLosers as apiFetchLosers,
  fetchMarketOverview as apiFetchMarketOverview,
} from "../services/api/market.api";
import type { Coin, CoinSearchResult } from "../types/coin";
import { dedupe } from "../utils/dedupe";
import { toErrorMessage } from "../utils/apiErrors";
import type {
  GlobalMarket,
  MarketCoin,
  MarketCoinFilter,
  MarketCoinFilters,
  MarketCoinSortField,
  MarketData,
  MarketOverview,
  MoverItem,
} from "../types/market";

export type MarketSortField = "market_cap_rank" | "name" | "symbol" | "updated_at";
export type SortDirection = "asc" | "desc";
export type MarketFilter = "all" | "gainers" | "losers";

interface MarketState {
  // Paginated coin listing ("all" filter)
  coins: Coin[];
  coinsPage: number;
  coinsLimit: number;
  coinsTotal: number;
  coinsPages: number;
  coinsLoading: boolean;
  coinsError: string | null;

  // Per-coin market data for whichever coins are currently visible in
  // the table — enriches the identity-only /coins response with
  // price/24h change. Keyed by internal coin id. See
  // docs/market-data.md / frontend README for why this is fetched
  // per-page rather than in one bulk call (Step 3 didn't build a
  // bulk "coins + market data" endpoint).
  coinMarketData: Record<string, MarketData>;
  coinMarketDataLoading: boolean;

  // Markets table (Phase 8): coins joined with market data, sorted
  // and filtered server-side via /market/coins.
  marketCoins: MarketCoin[];
  marketCoinsPage: number;
  marketCoinsLimit: number;
  marketCoinsTotal: number;
  marketCoinsPages: number;
  marketCoinsLoading: boolean;
  marketCoinsError: string | null;
  marketSortBy: MarketCoinSortField;
  marketSortDirection: SortDirection;
  marketFilter: MarketCoinFilter;
  // Explorer extensions: server-side range filters, an explicit id set
  // (watchlist / trending), and the freshness/universe metadata the same
  // response carries. All additive — defaults reproduce the old behaviour.
  marketFilters: MarketCoinFilters;
  marketCoinIds: string[] | null;
  marketLastUpdated: string | null;
  marketIsStale: boolean;
  marketUniverseTotal: number | null;

  // Search — results already carry their market data, joined
  // server-side by GET /coins/search (Phase 10). No follow-up
  // per-coin market-data fetch is needed or performed.
  searchQuery: string;
  searchResults: CoinSearchResult[] | null;
  searchLoading: boolean;
  searchError: string | null;

  // Sorting / filtering
  sortBy: MarketSortField;
  sortDirection: SortDirection;
  filter: MarketFilter;

  // Market overview / global stats
  marketOverview: MarketOverview | null;
  marketOverviewLoading: boolean;
  marketOverviewError: string | null;

  globalMarket: GlobalMarket | null;
  globalMarketLoading: boolean;
  globalMarketError: string | null;

  // Gainers / losers (also used when filter is "gainers"/"losers")
  gainers: MoverItem[];
  gainersLoading: boolean;
  gainersError: string | null;

  losers: MoverItem[];
  losersLoading: boolean;
  losersError: string | null;

  // Actions
  fetchMarketCoins: (page?: number, options?: { silent?: boolean }) => Promise<void>;
  setMarketSort: (field: MarketCoinSortField) => void;
  setMarketFilter: (filter: MarketCoinFilter) => void;
  setMarketPageSize: (limit: number) => void;
  /** Replace the range filters and reload page 1 (one request). */
  setMarketFilters: (filters: MarketCoinFilters) => void;
  /**
   * Apply a whole view (a category tab) in ONE state update and ONE request,
   * instead of separate sort + filter calls that would each hit the API.
   */
  setMarketView: (view: {
    filter?: MarketCoinFilter;
    sortBy?: MarketCoinSortField;
    sortDirection?: SortDirection;
    filters?: MarketCoinFilters;
    coinIds?: string[] | null;
  }) => void;
  fetchCoins: (page?: number) => Promise<void>;
  fetchCoinMarketDataFor: (coinIds: string[]) => Promise<void>;
  searchCoins: (query: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  setSort: (sortBy: MarketSortField, direction?: SortDirection) => void;
  setFilter: (filter: MarketFilter) => void;
  fetchMarketOverview: (options?: { silent?: boolean }) => Promise<void>;
  fetchGlobalMarket: (options?: { silent?: boolean }) => Promise<void>;
  fetchGainers: (limit?: number, options?: { silent?: boolean }) => Promise<void>;
  fetchLosers: (limit?: number, options?: { silent?: boolean }) => Promise<void>;
  clearError: () => void;
}

const DEFAULT_LIMIT = 20; // kept small since each row needs a follow-up per-coin market-data fetch (see coinMarketData above)

/**
 * Guarantees a loading flag can never remain `true` indefinitely.
 *
 * This is a deliberate safety net on top of (not a replacement for)
 * `apiClient`'s own 10s axios timeout: it bounds the *whole* fetch
 * action, including any work outside the HTTP call itself, so a
 * dashboard card's skeleton is provably bounded even if some lower
 * layer (a stalled tab, a browser edge case, a future regression)
 * ever fails to settle its promise on its own. Racing a timeout in
 * is strictly cheap — it either loses (the real request wins first,
 * the overwhelming common case) or catches a case nothing else would.
 */
const LOADING_GUARD_MS = 15_000;

async function withLoadingGuard<T>(promise: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const guard = new Promise<never>((_, reject) => {
    timer = setTimeout(
      () => reject(new Error("Request took too long to respond.")),
      LOADING_GUARD_MS,
    );
  });
  try {
    return await Promise.race([promise, guard]);
  } finally {
    clearTimeout(timer!);
  }
}

/** Generation counter for fetchMarketCoins — see the comment inside it. */
let marketCoinsRequestId = 0;

export const useMarketStore = create<MarketState>((set, get) => ({
  coins: [],
  coinsPage: 1,
  coinsLimit: DEFAULT_LIMIT,
  coinsTotal: 0,
  coinsPages: 0,
  coinsLoading: false,
  coinsError: null,

  coinMarketData: {},
  coinMarketDataLoading: false,

  marketCoins: [],
  marketCoinsPage: 1,
  marketCoinsLimit: 25,
  marketCoinsTotal: 0,
  marketCoinsPages: 0,
  marketCoinsLoading: false,
  marketCoinsError: null,
  marketSortBy: "market_cap",
  marketSortDirection: "desc",
  marketFilter: "all",
  marketFilters: {},
  marketCoinIds: null,
  marketLastUpdated: null,
  marketIsStale: false,
  marketUniverseTotal: null,

  searchQuery: "",
  searchResults: null,
  searchLoading: false,
  searchError: null,

  sortBy: "market_cap_rank",
  sortDirection: "asc",
  filter: "all",

  marketOverview: null,
  marketOverviewLoading: false,
  marketOverviewError: null,

  globalMarket: null,
  globalMarketLoading: false,
  globalMarketError: null,

  gainers: [],
  gainersLoading: false,
  gainersError: null,

  losers: [],
  losersLoading: false,
  losersError: null,

  fetchMarketCoins: async (page, options) => {
    const silent = options?.silent ?? false;
    const state = get();
    const targetPage = page ?? state.marketCoinsPage;

    // An explicit-but-empty id set (e.g. an empty watchlist) can never match
    // anything — answer locally instead of sending a pointless request.
    if (state.marketCoinIds !== null && state.marketCoinIds.length === 0) {
      marketCoinsRequestId += 1;
      set({
        marketCoins: [],
        marketCoinsPage: 1,
        marketCoinsTotal: 0,
        marketCoinsPages: 0,
        marketCoinsLoading: false,
        marketCoinsError: null,
      });
      return;
    }

    const params = {
      page: targetPage,
      limit: state.marketCoinsLimit,
      sortBy: state.marketSortBy,
      sortDirection: state.marketSortDirection,
      filter: state.marketFilter,
      filters: state.marketFilters,
      coinIds: state.marketCoinIds ?? undefined,
    };

    // Only user-driven loads start a new "generation". A silent poll joins
    // the current one, so its late response is discarded if the user has since
    // changed sort/filter/page — and a poll can never strand a loading flag.
    const requestId = silent ? marketCoinsRequestId : ++marketCoinsRequestId;
    if (!silent) set({ marketCoinsLoading: true, marketCoinsError: null });

    try {
      // Identical concurrent requests (StrictMode double effects, a poll
      // tick landing on a manual retry) share one HTTP call.
      const result = await dedupe(`market-coins:${JSON.stringify(params)}`, () => apiFetchMarketCoins(params));
      if (requestId !== marketCoinsRequestId) return; // superseded by a newer request
      set({
        marketCoins: result.items,
        marketCoinsPage: result.page,
        marketCoinsLimit: result.limit,
        marketCoinsTotal: result.total,
        marketCoinsPages: result.pages,
        marketCoinsLoading: false,
        marketCoinsError: null,
        marketLastUpdated: result.last_updated ?? null,
        marketIsStale: result.is_stale ?? false,
        marketUniverseTotal: result.coins_with_market_data ?? get().marketUniverseTotal,
      });
    } catch (error) {
      if (silent) return; // a background refresh blip keeps the last good page on screen
      if (requestId !== marketCoinsRequestId) return;
      set({
        marketCoinsLoading: false,
        marketCoinsError: toErrorMessage(error, "Market data could not be loaded. Please retry."),
      });
    }
  },

  setMarketSort: (field) => {
    const { marketSortBy, marketSortDirection } = get();
    // Toggle direction when re-sorting the same column; a new column
    // starts descending, which is what "top by X" means for every
    // market field here.
    const nextDirection: SortDirection =
      marketSortBy === field && marketSortDirection === "desc" ? "asc" : "desc";
    set({ marketSortBy: field, marketSortDirection: nextDirection });
    get().fetchMarketCoins(1);
  },

  setMarketFilter: (filter) => {
    set({ marketFilter: filter });
    get().fetchMarketCoins(1);
  },

  setMarketPageSize: (limit) => {
    set({ marketCoinsLimit: limit });
    get().fetchMarketCoins(1);
  },

  setMarketFilters: (filters) => {
    set({ marketFilters: filters });
    get().fetchMarketCoins(1);
  },

  setMarketView: (view) => {
    set((current) => ({
      marketFilter: view.filter ?? "all",
      marketSortBy: view.sortBy ?? current.marketSortBy,
      marketSortDirection: view.sortDirection ?? current.marketSortDirection,
      marketFilters: view.filters ?? current.marketFilters,
      marketCoinIds: view.coinIds === undefined ? null : view.coinIds,
    }));
    get().fetchMarketCoins(1);
  },

  fetchCoins: async (page) => {
    const state = get();
    const targetPage = page ?? state.coinsPage;
    set({ coinsLoading: true, coinsError: null });
    try {
      const params: ListCoinsParams = {
        page: targetPage,
        limit: state.coinsLimit,
        sortBy: state.sortBy,
        sortDirection: state.sortDirection,
      };
      const result = await apiFetchCoins(params);
      set({
        coins: result.items,
        coinsPage: result.page,
        coinsLimit: result.limit,
        coinsTotal: result.total,
        coinsPages: result.pages,
        coinsLoading: false,
      });
      // Enrich the visible page with price/change data — bounded to
      // this one page's worth of coins, never the whole database.
      get().fetchCoinMarketDataFor(result.items.map((c) => c.id));
    } catch (error) {
      set({ coinsLoading: false, coinsError: toErrorMessage(error, "Unable to load market data.") });
    }
  },

  fetchCoinMarketDataFor: async (coinIds) => {
    if (coinIds.length === 0) return;
    set({ coinMarketDataLoading: true });
    const results = await Promise.allSettled(coinIds.map((id) => apiFetchCoinMarketData(id)));
    const updates: Record<string, MarketData> = {};
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        updates[coinIds[index]] = result.value;
      }
      // A rejected entry (e.g. no market data synced yet for that
      // coin) is simply omitted — the table shows "—" for that row
      // rather than blocking the whole page on one failure.
    });
    set((current) => ({
      coinMarketData: { ...current.coinMarketData, ...updates },
      coinMarketDataLoading: false,
    }));
  },

  searchCoins: async (query) => {
    const trimmed = query.trim();
    if (!trimmed) {
      set({ searchResults: null, searchLoading: false, searchError: null });
      return;
    }
    set({ searchLoading: true, searchError: null });
    try {
      const result = await apiSearchCoins(trimmed);
      // Market data (price/24h/7d/market cap/volume) arrives already
      // joined onto each result — no per-coin follow-up fetch needed.
      set({ searchResults: result.items, searchLoading: false });
    } catch (error) {
      set({ searchLoading: false, searchError: toErrorMessage(error, "Search failed.") });
    }
  },

  setSearchQuery: (query) => set({ searchQuery: query }),

  setSort: (sortBy, direction) => {
    const nextDirection = direction ?? (get().sortBy === sortBy && get().sortDirection === "asc" ? "desc" : "asc");
    set({ sortBy, sortDirection: nextDirection });
    get().fetchCoins(1);
  },

  setFilter: (filter) => {
    set({ filter });
    if (filter === "gainers" && get().gainers.length === 0) get().fetchGainers();
    if (filter === "losers" && get().losers.length === 0) get().fetchLosers();
  },

  fetchMarketOverview: async (options) => {
    const silent = options?.silent ?? false;
    if (!silent) set({ marketOverviewLoading: true, marketOverviewError: null });
    try {
      const overview = await withLoadingGuard(dedupe("market-overview", () => apiFetchMarketOverview()));
      set({ marketOverview: overview, marketOverviewLoading: false, marketOverviewError: null });
    } catch (error) {
      if (silent) return; // keep the last good overview on screen through a background blip
      set({
        marketOverviewLoading: false,
        marketOverviewError: toErrorMessage(error, "Unable to load market overview."),
      });
    }
  },

  fetchGlobalMarket: async (options) => {
    const silent = options?.silent ?? false;
    if (!silent) set({ globalMarketLoading: true, globalMarketError: null });
    try {
      const global = await withLoadingGuard(dedupe("market-global", () => apiFetchGlobalMarket()));
      set({ globalMarket: global, globalMarketLoading: false, globalMarketError: null });
    } catch (error) {
      if (silent) return;
      set({
        globalMarketLoading: false,
        globalMarketError: toErrorMessage(error, "Unable to load global market statistics."),
      });
    }
  },

  fetchGainers: async (limit, options) => {
    const silent = options?.silent ?? false;
    if (!silent) set({ gainersLoading: true, gainersError: null });
    try {
      const gainers = await withLoadingGuard(dedupe(`market-gainers:${limit ?? "default"}`, () => apiFetchGainers(limit)));
      set({ gainers, gainersLoading: false, gainersError: null });
    } catch (error) {
      if (silent) return;
      set({ gainersLoading: false, gainersError: toErrorMessage(error, "Unable to load top gainers.") });
    }
  },

  fetchLosers: async (limit, options) => {
    const silent = options?.silent ?? false;
    if (!silent) set({ losersLoading: true, losersError: null });
    try {
      const losers = await withLoadingGuard(dedupe(`market-losers:${limit ?? "default"}`, () => apiFetchLosers(limit)));
      set({ losers, losersLoading: false, losersError: null });
    } catch (error) {
      if (silent) return;
      set({ losersLoading: false, losersError: toErrorMessage(error, "Unable to load top losers.") });
    }
  },

  clearError: () =>
    set({
      marketCoinsError: null,
      coinsError: null,
      searchError: null,
      marketOverviewError: null,
      globalMarketError: null,
      gainersError: null,
      losersError: null,
    }),
}));
