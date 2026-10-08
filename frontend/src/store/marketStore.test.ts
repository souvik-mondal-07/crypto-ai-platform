import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMarketStore } from "./marketStore";
import * as coinsApi from "../services/api/coins.api";
import * as marketApi from "../services/api/market.api";

vi.mock("../services/api/coins.api", () => ({
  fetchCoins: vi.fn(),
  searchCoins: vi.fn(),
  fetchCoinById: vi.fn(),
}));

vi.mock("../services/api/market.api", () => ({
  fetchMarketCoins: vi.fn(),
  fetchTopByMarketCap: vi.fn(),
  fetchTopByVolume: vi.fn(),
  fetchBinanceTickers: vi.fn(),
  fetchCoinMarketData: vi.fn(),
  fetchMarketOverview: vi.fn(),
  fetchGainers: vi.fn(),
  fetchLosers: vi.fn(),
  fetchGlobalMarket: vi.fn(),
  fetchTrending: vi.fn(),
}));

const mockedCoinsApi = vi.mocked(coinsApi);
const mockedMarketApi = vi.mocked(marketApi);

function resetStore() {
  useMarketStore.setState({
    marketCoins: [], marketCoinsPage: 1, marketCoinsLimit: 25, marketCoinsTotal: 0,
    marketCoinsPages: 0, marketCoinsLoading: false, marketCoinsError: null,
    marketSortBy: "market_cap", marketSortDirection: "desc", marketFilter: "all",
    coins: [], coinsPage: 1, coinsLimit: 20, coinsTotal: 0, coinsPages: 0, coinsLoading: false, coinsError: null,
    coinMarketData: {}, coinMarketDataLoading: false,
    searchQuery: "", searchResults: null, searchLoading: false, searchError: null,
    sortBy: "market_cap_rank", sortDirection: "asc", filter: "all",
    marketOverview: null, marketOverviewLoading: false, marketOverviewError: null,
    globalMarket: null, globalMarketLoading: false, globalMarketError: null,
    gainers: [], gainersLoading: false, gainersError: null,
    losers: [], losersLoading: false, losersError: null,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  resetStore();
});

describe("marketStore.fetchCoins", () => {
  it("stores the real paginated result from the backend, never fake coins", async () => {
    mockedCoinsApi.fetchCoins.mockResolvedValue({
      items: [
        { id: "1", name: "Real Backend Coin", symbol: "RBC", slug: "real-backend-coin", logo_url: null, market_cap_rank: 1, is_active: true, providers: { coingecko: { id: "x", available: true }, binance: null }, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ],
      page: 1, limit: 20, total: 1, pages: 1,
    });
    mockedMarketApi.fetchCoinMarketData.mockResolvedValue({
      coin_id: "1", price_usd: 100, market_cap_usd: null, volume_24h_usd: null, high_24h_usd: null, low_24h_usd: null,
      percent_change_1h: null, percent_change_24h: 5, percent_change_7d: null, percent_change_30d: null,
      percent_change_1y: null, price_change_24h_usd: null, fully_diluted_valuation_usd: null, ath_date: null, atl_date: null,
      circulating_supply: null, total_supply: null, max_supply: null, ath_usd: null, atl_usd: null,
      ath_change_percentage: null, atl_change_percentage: null, last_updated: null, data_source: "coingecko", is_stale: false,
    });

    await useMarketStore.getState().fetchCoins();

    const state = useMarketStore.getState();
    expect(state.coins).toHaveLength(1);
    expect(state.coins[0].name).toBe("Real Backend Coin");
    expect(state.coinsTotal).toBe(1);
    expect(state.marketCoinsError).toBeNull();
    expect(state.coinsError).toBeNull();
  });

  it("sets a clean error message on failure, without crashing", async () => {
    mockedCoinsApi.fetchCoins.mockRejectedValue(new Error("Unable to load market data."));

    await useMarketStore.getState().fetchCoins();

    const state = useMarketStore.getState();
    expect(state.coins).toEqual([]);
    expect(state.coinsError).toBe("Unable to load market data.");
    expect(state.coinsLoading).toBe(false);
  });
});

describe("marketStore.searchCoins", () => {
  it("clears search results when the query is empty", async () => {
    useMarketStore.setState({ searchResults: [{ id: "1" } as never] });
    await useMarketStore.getState().searchCoins("   ");
    expect(useMarketStore.getState().searchResults).toBeNull();
    expect(mockedCoinsApi.searchCoins).not.toHaveBeenCalled();
  });

  it("calls the backend search endpoint for a real query", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({
      items: [], query: "bitcoin", count: 0,
    });

    await useMarketStore.getState().searchCoins("bitcoin");

    expect(mockedCoinsApi.searchCoins).toHaveBeenCalledWith("bitcoin");
    expect(useMarketStore.getState().searchResults).toEqual([]);
  });
});

describe("marketStore.setSort", () => {
  it("toggles direction when sorting by the same field again", () => {
    useMarketStore.setState({ sortBy: "name", sortDirection: "asc" });
    mockedCoinsApi.fetchCoins.mockResolvedValue({ items: [], page: 1, limit: 20, total: 0, pages: 0 });

    useMarketStore.getState().setSort("name");

    expect(useMarketStore.getState().sortDirection).toBe("desc");
  });
});

describe("marketStore.setFilter", () => {
  it("fetches gainers the first time the gainers filter is selected", () => {
    mockedMarketApi.fetchGainers.mockResolvedValue([]);
    useMarketStore.getState().setFilter("gainers");
    expect(mockedMarketApi.fetchGainers).toHaveBeenCalledTimes(1);
    expect(useMarketStore.getState().filter).toBe("gainers");
  });
});

describe("marketStore.clearError", () => {
  it("clears every error field at once", () => {
    useMarketStore.setState({
      marketCoinsError: "z", coinsError: "a", searchError: "b", marketOverviewError: "c",
      globalMarketError: "d", gainersError: "e", losersError: "f",
    });
    useMarketStore.getState().clearError();
    const state = useMarketStore.getState();
    expect(state.marketCoinsError).toBeNull();
    expect(state.coinsError).toBeNull();
    expect(state.searchError).toBeNull();
    expect(state.marketOverviewError).toBeNull();
    expect(state.globalMarketError).toBeNull();
    expect(state.gainersError).toBeNull();
    expect(state.losersError).toBeNull();
  });
});

describe("marketStore.fetchMarketCoins (Phase 8)", () => {
  it("stores the joined rows and pagination metadata from the backend", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue({
      items: [
        {
          coin_id: "c1", name: "Backend Coin", symbol: "BC", logo_url: null, market_cap_rank: 1,
          price_usd: 10, percent_change_24h: 2, high_24h_usd: 11, low_24h_usd: 9,
          market_cap_usd: 1000, volume_24h_usd: 500, circulating_supply: 100,
          last_updated: "2026-01-01T00:00:00Z",
        },
      ],
      page: 2, limit: 25, total: 60, pages: 3,
      sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    });

    await useMarketStore.getState().fetchMarketCoins(2);

    const state = useMarketStore.getState();
    expect(state.marketCoins[0].name).toBe("Backend Coin");
    expect(state.marketCoinsPage).toBe(2);
    expect(state.marketCoinsTotal).toBe(60);
    expect(state.marketCoinsPages).toBe(3);
    expect(state.marketCoinsError).toBeNull();
  });

  it("records a clean error message on failure without throwing", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new Error("Unable to load market data."));
    await useMarketStore.getState().fetchMarketCoins();
    const state = useMarketStore.getState();
    expect(state.marketCoinsError).toBe("Unable to load market data.");
    expect(state.marketCoinsLoading).toBe(false);
    expect(state.marketCoins).toEqual([]);
  });

  it("setMarketSort starts a new column descending and toggles on repeat", () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue({
      items: [], page: 1, limit: 25, total: 0, pages: 0,
      sort_by: "price", sort_direction: "desc", data_source: "coingecko",
    });

    useMarketStore.getState().setMarketSort("price");
    expect(useMarketStore.getState().marketSortBy).toBe("price");
    expect(useMarketStore.getState().marketSortDirection).toBe("desc");

    useMarketStore.getState().setMarketSort("price");
    expect(useMarketStore.getState().marketSortDirection).toBe("asc");
  });

  it("setMarketFilter resets to page 1 and refetches", () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue({
      items: [], page: 1, limit: 25, total: 0, pages: 0,
      sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    });

    useMarketStore.setState({ marketCoinsPage: 5 });
    useMarketStore.getState().setMarketFilter("losers");

    expect(useMarketStore.getState().marketFilter).toBe("losers");
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
      expect.objectContaining({ filter: "losers", page: 1 })
    );
  });

  // --- Real-time refresh upgrade: silent background refresh ---------------

  it("a silent refresh never flips marketCoinsLoading to true", async () => {
    let resolveFetch: (value: Awaited<ReturnType<typeof marketApi.fetchMarketCoins>>) => void;
    mockedMarketApi.fetchMarketCoins.mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; }),
    );

    const promise = useMarketStore.getState().fetchMarketCoins(undefined, { silent: true });
    // Still in flight — loading must never have been set for a silent call.
    expect(useMarketStore.getState().marketCoinsLoading).toBe(false);

    resolveFetch!({
      items: [], page: 1, limit: 25, total: 0, pages: 0,
      sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    });
    await promise;
    expect(useMarketStore.getState().marketCoinsLoading).toBe(false);
  });

  it("a silent refresh failure keeps the last good rows on screen instead of setting an error", async () => {
    useMarketStore.setState({
      marketCoins: [
        { coin_id: "c1", name: "Existing Coin", symbol: "EX", logo_url: null, market_cap_rank: 1,
          price_usd: 1, percent_change_24h: 1, high_24h_usd: null, low_24h_usd: null,
          market_cap_usd: null, volume_24h_usd: null, circulating_supply: null, last_updated: null },
      ],
    });
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new Error("network blip"));

    await useMarketStore.getState().fetchMarketCoins(undefined, { silent: true });

    const state = useMarketStore.getState();
    expect(state.marketCoins).toHaveLength(1);
    expect(state.marketCoins[0].name).toBe("Existing Coin");
    expect(state.marketCoinsError).toBeNull();
  });
});

describe("marketStore.fetchMarketCoins — explorer extensions", () => {
  const response = (overrides = {}) => ({
    items: [], page: 1, limit: 25, total: 0, pages: 0,
    sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko", ...overrides,
  });

  it("setMarketView applies tab, sort and filters in ONE request", async () => {
    mockedMarketApi.fetchMarketCoins.mockClear();
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(response());

    useMarketStore.getState().setMarketView({
      filter: "gainers", sortBy: "change_24h", sortDirection: "desc", filters: { marketCapMin: 1e9 }, coinIds: null,
    });

    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledTimes(1);
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledWith(
      expect.objectContaining({ filter: "gainers", sortBy: "change_24h", filters: { marketCapMin: 1e9 }, page: 1 })
    );
  });

  it("an explicit empty id set (empty watchlist) never reaches the backend", async () => {
    mockedMarketApi.fetchMarketCoins.mockClear();
    useMarketStore.setState({ marketCoinIds: [], marketCoins: [{ coin_id: "old" } as never] });

    await useMarketStore.getState().fetchMarketCoins(1);

    expect(mockedMarketApi.fetchMarketCoins).not.toHaveBeenCalled();
    expect(useMarketStore.getState().marketCoins).toEqual([]);
    expect(useMarketStore.getState().marketCoinsLoading).toBe(false);
  });

  it("keeps the backend's freshness and universe metadata", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      response({ last_updated: "2026-01-01T00:00:00Z", is_stale: true, coins_with_market_data: 321 })
    );
    useMarketStore.setState({ marketCoinIds: null });
    await useMarketStore.getState().fetchMarketCoins(1);

    const state = useMarketStore.getState();
    expect(state.marketLastUpdated).toBe("2026-01-01T00:00:00Z");
    expect(state.marketIsStale).toBe(true);
    expect(state.marketUniverseTotal).toBe(321);
  });

  it("discards a slow response that was superseded by a newer request", async () => {
    let resolveSlow: (value: ReturnType<typeof response>) => void;
    mockedMarketApi.fetchMarketCoins
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSlow = resolve as never; }))
      .mockResolvedValueOnce(response({ items: [{ coin_id: "new", name: "Newest" }], total: 1, pages: 1 }));
    useMarketStore.setState({ marketCoinIds: null, marketSortBy: "market_cap" });

    const slow = useMarketStore.getState().fetchMarketCoins(1);
    useMarketStore.setState({ marketSortBy: "price" }); // different params => not coalesced
    await useMarketStore.getState().fetchMarketCoins(1);
    resolveSlow!(response({ items: [{ coin_id: "old", name: "Stale" }], total: 1, pages: 1 }));
    await slow;

    expect(useMarketStore.getState().marketCoins[0]).toEqual(expect.objectContaining({ coin_id: "new" }));
  });

  it("a rate-limited response becomes the clean provider message", async () => {
    const { ApiError } = await import("../types/apiError");
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new ApiError("Too many requests", 429));
    useMarketStore.setState({ marketCoinIds: null });
    await useMarketStore.getState().fetchMarketCoins(1);
    expect(useMarketStore.getState().marketCoinsError).toBe(
      "Market data provider is temporarily rate limited. Please try again shortly."
    );
  });
});

describe("marketStore silent refresh — overview/global/gainers/losers", () => {
  it("fetchMarketOverview({silent:true}) never toggles the loading flag", async () => {
    let resolveFetch: (value: Awaited<ReturnType<typeof marketApi.fetchMarketOverview>>) => void;
    mockedMarketApi.fetchMarketOverview.mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; }),
    );

    const promise = useMarketStore.getState().fetchMarketOverview({ silent: true });
    expect(useMarketStore.getState().marketOverviewLoading).toBe(false);

    resolveFetch!({
      active_cryptocurrencies: 1, top_gainers: [], top_losers: [],
      last_updated: null, data_source: "coingecko",
    });
    await promise;
    expect(useMarketStore.getState().marketOverviewLoading).toBe(false);
  });

  it("a non-silent call still sets loading and error normally (unchanged behavior)", async () => {
    mockedMarketApi.fetchGainers.mockRejectedValue(new Error("boom"));
    await useMarketStore.getState().fetchGainers();
    const state = useMarketStore.getState();
    expect(state.gainersError).toBe("boom");
    expect(state.gainersLoading).toBe(false);
  });

  it("fetchGainers({silent:true}) swallows the error and keeps prior data", async () => {
    useMarketStore.setState({ gainers: [{ coin_id: "c1", name: "X", symbol: "X", logo_url: null, market_cap_rank: 1, price_usd: 1, percent_change_24h: 1 }] });
    mockedMarketApi.fetchGainers.mockRejectedValue(new Error("boom"));

    await useMarketStore.getState().fetchGainers(undefined, { silent: true });

    const state = useMarketStore.getState();
    expect(state.gainers).toHaveLength(1);
    expect(state.gainersError).toBeNull();
  });
});
