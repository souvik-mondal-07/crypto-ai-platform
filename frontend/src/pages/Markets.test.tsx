import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Markets } from "./Markets";
import { ThemeProvider } from "../context/ThemeContext";
import { useAuthStore } from "../store/authStore";
import { useMarketStore } from "../store/marketStore";
import * as coinsApi from "../services/api/coins.api";
import { ApiError } from "../types/apiError";
import { useUserListsStore } from "../store/userListsStore";
import * as marketApi from "../services/api/market.api";

vi.mock("../services/api/coins.api", () => ({
  fetchCoins: vi.fn(),
  searchCoins: vi.fn(),
  fetchCoinById: vi.fn(),
}));

vi.mock("../services/api/market.api", () => ({
  fetchMarketCoins: vi.fn(),
  fetchCoinMarketData: vi.fn(),
  fetchCoinHistory: vi.fn(),
  fetchMarketOverview: vi.fn(),
  fetchGainers: vi.fn(),
  fetchLosers: vi.fn(),
  fetchGlobalMarket: vi.fn(),
  fetchTrending: vi.fn(),
  fetchTopByMarketCap: vi.fn(),
  fetchTopByVolume: vi.fn(),
  fetchBinanceTickers: vi.fn(),
}));

const mockedCoinsApi = vi.mocked(coinsApi);
const mockedMarketApi = vi.mocked(marketApi);

function marketCoin(overrides = {}) {
  return {
    coin_id: "coin-1",
    name: "Uniquely Named Coin",
    symbol: "UNC",
    logo_url: null,
    market_cap_rank: 1,
    price_usd: 1234.56,
    percent_change_24h: 5.25,
    high_24h_usd: 1300,
    low_24h_usd: 1200,
    market_cap_usd: 9_000_000,
    volume_24h_usd: 500_000,
    circulating_supply: 1_000_000,
    last_updated: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function emptyMarketResponse(overrides = {}) {
  return {
    items: [], page: 1, limit: 25, total: 0, pages: 0,
    sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    ...overrides,
  };
}

function resetStores() {
  useAuthStore.setState({
    user: { id: "1", name: "Real User", email: "real@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
    isAuthenticated: true, isLoading: false, error: null,
  });
  useMarketStore.setState({
    marketCoins: [], marketCoinsPage: 1, marketCoinsLimit: 25, marketCoinsTotal: 0,
    marketCoinsPages: 0, marketCoinsLoading: false, marketCoinsError: null,
    marketSortBy: "market_cap", marketSortDirection: "desc", marketFilter: "all",
    coins: [], coinsPage: 1, coinsLimit: 20, coinsTotal: 0, coinsPages: 0,
    coinsLoading: false, coinsError: null, coinMarketData: {}, coinMarketDataLoading: false,
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
  localStorage.clear();
  useUserListsStore.setState({ userId: "1", watchlist: [], recent: [], compare: [] });
  resetStores();
  mockedCoinsApi.fetchCoins.mockResolvedValue({ items: [], page: 1, limit: 20, total: 0, pages: 0 });
  mockedMarketApi.fetchMarketCoins.mockResolvedValue(emptyMarketResponse());
  mockedMarketApi.fetchMarketOverview.mockResolvedValue({
    active_cryptocurrencies: 0, top_gainers: [], top_losers: [], last_updated: null, data_source: "coingecko",
  });
  mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
    total_market_cap_usd: null, total_volume_24h_usd: null, market_cap_percentage: null,
    active_cryptocurrencies: null, market_cap_change_percentage_24h: null,
    last_updated: null, data_source: "coingecko",
  });
  mockedMarketApi.fetchGainers.mockResolvedValue([]);
  mockedMarketApi.fetchLosers.mockResolvedValue([]);
});

function renderMarkets(initialEntry = "/markets") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ThemeProvider>
        <Routes>
          <Route path="/markets" element={<Markets />} />
          <Route path="/coins/:coinId" element={<div>Coin Details Page</div>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

describe("Markets — table data", () => {
  it("renders real backend rows with all market columns, never hard-coded coins", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 })
    );

    renderMarkets();

    expect(await screen.findByText("Uniquely Named Coin")).toBeInTheDocument();
    expect(screen.getByText("UNC")).toBeInTheDocument();
    expect(screen.getByText(/1,234\.56/)).toBeInTheDocument();
    expect(screen.getByText("+5.25%")).toBeInTheDocument();
    expect(screen.queryByText("Bitcoin")).not.toBeInTheDocument();
    expect(screen.queryByText("Ethereum")).not.toBeInTheDocument();
  });

  it("shows an empty state rather than fabricating rows", async () => {
    renderMarkets();
    expect(await screen.findByText(/no market data available yet/i)).toBeInTheDocument();
  });

  it("shows a retry-capable error state when the request fails", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new Error("Unable to load market data."));
    renderMarkets();
    expect(await screen.findByText("Unable to load market data.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /retry/i }).length).toBeGreaterThan(0);
  });
});

describe("Markets — sorting", () => {
  it("re-requests from the backend with the chosen sort field", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await screen.findByText("Uniquely Named Coin");
    await user.click(screen.getByRole("button", { name: /24h volume/i }));

    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "volume", page: 1 })
      )
    );
  });

  it("toggles direction when the same column is sorted twice", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await screen.findByText("Uniquely Named Coin");
    // market_cap starts as the default (desc); clicking it flips to asc.
    await user.click(screen.getByRole("button", { name: /market cap/i }));

    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "market_cap", sortDirection: "asc" })
      )
    );
  });
});

describe("Markets — filtering", () => {
  it("re-requests with the selected filter", async () => {
    const user = userEvent.setup();
    renderMarkets();

    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    await user.click(screen.getByRole("tab", { name: "Gainers" }));

    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
        expect.objectContaining({ filter: "gainers", page: 1 })
      )
    );
  });
});

describe("Markets — pagination", () => {
  it("requests the next page from the backend", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 60, pages: 3 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await screen.findByText("Uniquely Named Coin");
    await user.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 })
    ));
  });

  it("changes page size through the backend rather than slicing locally", async () => {
    const user = userEvent.setup();
    renderMarkets();

    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    await user.selectOptions(screen.getByRole("combobox", { name: /rows per page/i }), "50");

    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 50, page: 1 })
      )
    );
  });
});

describe("Markets — search", () => {
  it("calls the backend search endpoint (debounced), not a local array filter", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "bit", count: 0 });
    const user = userEvent.setup();
    renderMarkets();

    await user.type(screen.getByLabelText(/search cryptocurrencies/i), "bit");

    await waitFor(() => expect(mockedCoinsApi.searchCoins).toHaveBeenCalledWith("bit"), { timeout: 2000 });
  });

  it("shows an empty state when a search returns nothing", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "zzzz", count: 0 });
    const user = userEvent.setup();
    renderMarkets();

    await user.type(screen.getByLabelText(/search cryptocurrencies/i), "zzzz");

    expect(await screen.findByText(/no coins matched "zzzz"/i, {}, { timeout: 2000 })).toBeInTheDocument();
  });

  it("seeds the search box from a ?q= query parameter", async () => {
    mockedCoinsApi.searchCoins.mockResolvedValue({ items: [], query: "eth", count: 0 });
    renderMarkets("/markets?q=eth");
    expect(await screen.findByDisplayValue("eth")).toBeInTheDocument();
  });
});

describe("Markets — is an explorer, not a second dashboard", () => {
  it("does not render the dashboard's snapshot, movers or heatmap sections", async () => {
    renderMarkets();
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    expect(screen.queryByText("Market Movers")).not.toBeInTheDocument();
    expect(screen.queryByText("Market Heatmap")).not.toBeInTheDocument();
    expect(screen.queryByText("Total Market Cap")).not.toBeInTheDocument();
    // ...and never pulls the dashboard-only datasets.
    expect(mockedMarketApi.fetchGainers).not.toHaveBeenCalled();
    expect(mockedMarketApi.fetchGlobalMarket).not.toHaveBeenCalled();
  });

  it("shows the real universe size and freshness from the backend", async () => {
    mockedMarketApi.fetchMarketOverview.mockResolvedValue({
      active_cryptocurrencies: 17000, top_gainers: [], top_losers: [], last_updated: null, data_source: "coingecko",
    });
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1, coins_with_market_data: 12345, last_updated: new Date().toISOString(), is_stale: false })
    );
    renderMarkets();
    expect(await screen.findByText(/17,000 coins tracked/)).toBeInTheDocument();
    expect(await screen.findByText(/12,345 with market data/)).toBeInTheDocument();
    expect(screen.getByText("Updated recently")).toBeInTheDocument();
  });

  it("warns when the backend reports stale market data, without hiding the rows", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1, last_updated: "2020-01-01T00:00:00Z", is_stale: true })
    );
    renderMarkets();
    expect(await screen.findByText("Uniquely Named Coin")).toBeInTheDocument();
    expect(screen.getAllByText(/market data is stale/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/hasn.t been refreshed recently/i)).toBeInTheDocument();
  });

  it("applies the initial view in a single request (no default load followed by a filtered one)", async () => {
    renderMarkets("/markets?cap=gt10b");
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledTimes(1);
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledWith(
      expect.objectContaining({ filters: expect.objectContaining({ marketCapMin: 1e10 }) })
    );
  });
});

describe("Markets — category tabs and filters", () => {
  it.each([
    ["Losers", { filter: "losers", sortBy: "change_24h", sortDirection: "asc" }],
    ["Highest Volume", { sortBy: "volume", sortDirection: "desc" }],
    ["Highest Volatility", { sortBy: "volatility", sortDirection: "desc" }],
  ])("%s tab asks the backend for that view", async (label, expected) => {
    const user = userEvent.setup();
    renderMarkets();
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    await user.click(screen.getByRole("tab", { name: label }));
    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(expect.objectContaining({ ...expected, page: 1 }))
    );
  });

  it("opens the Gainers tab straight from ?tab=gainers", async () => {
    renderMarkets("/markets?tab=gainers");
    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(expect.objectContaining({ filter: "gainers" }))
    );
    expect(screen.getByRole("tab", { name: "Gainers", selected: true })).toBeInTheDocument();
  });

  it("sends market-cap filter bounds to the backend instead of filtering in the browser", async () => {
    const user = userEvent.setup();
    renderMarkets();
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /filters/i }));
    await user.selectOptions(screen.getByLabelText("Market cap"), "1b-10b");

    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(
        expect.objectContaining({ filters: expect.objectContaining({ marketCapMin: 1e9, marketCapMax: 1e10 }) })
      )
    );
  });

  it("the Trending tab only requests coins the provider reports as trending and that we have synced", async () => {
    mockedMarketApi.fetchTrending.mockResolvedValue({
      items: [
        { coingecko_id: "a", internal_coin_id: "id-a", name: "A", symbol: "A", market_cap_rank: 1, score: 0 },
        { coingecko_id: "b", internal_coin_id: null, name: "B", symbol: "B", market_cap_rank: 2, score: 1 },
      ],
      available: true, data_source: "coingecko", last_updated: null,
    });
    const user = userEvent.setup();
    renderMarkets();
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    await user.click(screen.getByRole("tab", { name: "Trending" }));
    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(expect.objectContaining({ coinIds: ["id-a"] }))
    );
  });
});

describe("Markets — error handling", () => {
  it("explains a 429 as a provider rate limit and offers retry", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new ApiError("Too many requests", 429));
    renderMarkets();
    expect(
      await screen.findByText("Market data provider is temporarily rate limited. Please try again shortly.")
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /retry/i }).length).toBeGreaterThan(0);
  });

  it("shows a clean message for a 500, never the raw server text", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new ApiError("Traceback (most recent call last)...", 500));
    renderMarkets();
    expect(await screen.findByText("Market data could not be loaded. Please retry.")).toBeInTheDocument();
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument();
  });

  it("tells a network failure apart from an API error", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new ApiError("Network Error"));
    renderMarkets();
    expect(await screen.findByText(/unable to reach the server/i)).toBeInTheDocument();
  });

  it("retry reloads the table", async () => {
    mockedMarketApi.fetchMarketCoins.mockRejectedValueOnce(new ApiError("boom", 500));
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 }));
    const user = userEvent.setup();
    renderMarkets();
    await user.click((await screen.findAllByRole("button", { name: /retry/i }))[0]);
    expect(await screen.findByText("Uniquely Named Coin")).toBeInTheDocument();
  });
});

describe("Markets — watchlist and comparison", () => {
  it("stars a coin without navigating away, and remembers it", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin({ coin_id: "star-me" })], total: 1, pages: 1 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await user.click(await screen.findByRole("button", { name: /add uniquely named coin to watchlist/i }));

    expect(screen.queryByText("Coin Details Page")).not.toBeInTheDocument();
    expect(useUserListsStore.getState().watchlist).toEqual(["star-me"]);
    expect(screen.getByRole("button", { name: /remove uniquely named coin from watchlist/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("the Watchlist tab with nothing starred shows an empty state and sends no request", async () => {
    const user = userEvent.setup();
    renderMarkets();
    await waitFor(() => expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalled());
    mockedMarketApi.fetchMarketCoins.mockClear();

    await user.click(screen.getByRole("tab", { name: /watchlist/i }));

    expect(await screen.findByText(/your watchlist is empty/i)).toBeInTheDocument();
    expect(mockedMarketApi.fetchMarketCoins).not.toHaveBeenCalled();
  });

  it("the Watchlist tab requests exactly the starred coin ids", async () => {
    useUserListsStore.setState({ watchlist: ["w1", "w2"] });
    renderMarkets("/markets?tab=watchlist");
    await waitFor(() =>
      expect(mockedMarketApi.fetchMarketCoins).toHaveBeenLastCalledWith(expect.objectContaining({ coinIds: ["w1", "w2"] }))
    );
  });

  it("compares selected coins using real market fields and N/A for missing ones", async () => {
    const a = marketCoin({ coin_id: "a", name: "Alpha", symbol: "ALP", price_usd: 10 });
    const b = marketCoin({ coin_id: "b", name: "Beta", symbol: "BET", price_usd: 20, ath_usd: null });
    mockedMarketApi.fetchMarketCoins.mockImplementation(async (params: { coinIds?: string[] }) =>
      params.coinIds
        ? emptyMarketResponse({ items: [a, b], total: 2, pages: 1 })
        : emptyMarketResponse({ items: [a, b], total: 2, pages: 1 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await user.click(await screen.findByRole("checkbox", { name: "Compare Alpha" }));
    await user.click(screen.getByRole("checkbox", { name: "Compare Beta" }));

    const panel = await screen.findByRole("region", { name: /coin comparison/i });
    await waitFor(() => expect(within(panel).getByText("$20.00")).toBeInTheDocument());
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledWith(expect.objectContaining({ coinIds: ["a", "b"] }));
    expect(within(panel).getAllByText("N/A").length).toBeGreaterThan(0);
  });

  it("asks for at least two coins before comparing", async () => {
    renderMarkets("/markets?compare=1");
    expect(await screen.findByText(/tick at least two coins/i)).toBeInTheDocument();
  });
});

describe("Markets — columns", () => {
  it("lets the user hide an optional column", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 }));
    const user = userEvent.setup();
    renderMarkets();
    await screen.findByText("Uniquely Named Coin");
    expect(screen.getByRole("button", { name: /^fdv/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /columns/i }));
    await user.click(screen.getByRole("checkbox", { name: "FDV" }));

    expect(screen.queryByRole("button", { name: /^fdv/i })).not.toBeInTheDocument();
  });
});

describe("Markets — navigation", () => {
  it("navigates to the coin details route using the backend coin_id", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin({ coin_id: "real-backend-id" })], total: 1, pages: 1 })
    );
    const user = userEvent.setup();
    renderMarkets();

    await user.click(await screen.findByText("Uniquely Named Coin"));
    expect(await screen.findByText("Coin Details Page")).toBeInTheDocument();
  });
});

describe("Markets — theme compatibility", () => {
  it("renders table rows with dark-mode classes alongside light ones", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue(
      emptyMarketResponse({ items: [marketCoin()], total: 1, pages: 1 })
    );
    renderMarkets();

    const nameCell = await screen.findByText("Uniquely Named Coin");
    const row = nameCell.closest("tr");
    expect(row).not.toBeNull();
    expect(row?.getAttribute("class") ?? "").toContain("dark:");
    expect(within(row as HTMLElement).getByText("UNC")).toBeInTheDocument();
  });
});
