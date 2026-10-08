import { describe, expect, it, beforeEach, vi } from "vitest";
import { render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { Dashboard } from "./Dashboard";
import { ThemeProvider } from "../context/ThemeContext";
import { useAuthStore } from "../store/authStore";
import { useMarketStore } from "../store/marketStore";
import { useUserListsStore } from "../store/userListsStore";
import * as coinsApi from "../services/api/coins.api";
import * as marketApi from "../services/api/market.api";
import * as newsApi from "../services/api/news.api";
import { buildArticle, buildNewsList } from "../test-fixtures/news";

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
  fetchCoinHistory: vi.fn(),
}));

vi.mock("../services/api/news.api", () => ({
  fetchNews: vi.fn(),
  fetchNewsSources: vi.fn(),
  fetchCoinSentiment: vi.fn(),
}));

const mockedNewsApi = vi.mocked(newsApi);
const mockedCoinsApi = vi.mocked(coinsApi);
const mockedMarketApi = vi.mocked(marketApi);

// The shared Header reads the theme, so every render needs the provider the real app mounts in App.tsx.
function render(ui: ReactElement) {
  return rtlRender(ui, { wrapper: ThemeProvider });
}

function resetStores() {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
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
  resetStores();
  mockedCoinsApi.fetchCoins.mockResolvedValue({ items: [], page: 1, limit: 20, total: 0, pages: 0 });
  mockedMarketApi.fetchMarketOverview.mockResolvedValue({
    active_cryptocurrencies: 0, top_gainers: [], top_losers: [], last_updated: null, data_source: "coingecko",
  });
  mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
    total_market_cap_usd: null, total_volume_24h_usd: null, market_cap_percentage: null,
    active_cryptocurrencies: null, market_cap_change_percentage_24h: null, last_updated: null, data_source: "coingecko",
  });
  mockedMarketApi.fetchGainers.mockResolvedValue([]);
  mockedMarketApi.fetchLosers.mockResolvedValue([]);
  mockedMarketApi.fetchTopByVolume.mockResolvedValue([]);
  mockedMarketApi.fetchMarketCoins.mockResolvedValue({
    items: [], page: 1, limit: 60, total: 0, pages: 0,
    sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
  });
  mockedNewsApi.fetchNews.mockResolvedValue(buildNewsList([]));
  localStorage.clear();
  useUserListsStore.setState({ userId: null, watchlist: [], recent: [], compare: [] });
});

describe("Dashboard", () => {
  it("greets the actual authenticated user by name, never a sample value", async () => {
    useAuthStore.setState({
      isAuthenticated: true,
      isLoading: false,
      user: {
        id: "abc123",
        name: "Uniquely Registered Person",
        email: "uniquely.registered@example.com",
        role: "user",
        created_at: "2026-01-01T00:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    // The name is also shown in the Header's user menu, so assert the dashboard's own greeting.
    expect(await screen.findByText(/Welcome back, Uniquely Registered Person/)).toBeInTheDocument();

    for (const fakeName of ["John Doe", "Demo User", "Sample User", "Guest User", "Test User"]) {
      expect(screen.queryByText(fakeName)).not.toBeInTheDocument();
    }
  });

  it("renders real gainer data returned by the backend, never fake sample coins", async () => {
    mockedMarketApi.fetchGainers.mockResolvedValue([
      {
        coin_id: "1", name: "Real Coin From Backend", symbol: "RCB",
        logo_url: null, market_cap_rank: 5, price_usd: 12.34, percent_change_24h: 8.5,
      },
    ]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText("Real Coin From Backend")).toBeInTheDocument();
    expect(screen.queryByText("Bitcoin")).not.toBeInTheDocument();
    expect(screen.queryByText("Ethereum")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no market data, not fake data", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => expect(mockedMarketApi.fetchGainers).toHaveBeenCalled());
    expect(await screen.findByText(/no gainer data available/i)).toBeInTheDocument();
  });

  it("shows an error state with retry when the backend call fails", async () => {
    mockedMarketApi.fetchMarketOverview.mockRejectedValue(new Error("Unable to load market overview."));
    mockedMarketApi.fetchGlobalMarket.mockRejectedValue(new Error("Unable to load global market statistics."));

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText(/unable to load/i)).toBeInTheDocument();
  });

  it("loads overview data, maps backend fields to all four cards, and removes skeletons", async () => {
    mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
      total_market_cap_usd: 1234567890000, total_volume_24h_usd: 98765432100,
      market_cap_percentage: null, active_cryptocurrencies: 43210,
      market_cap_change_percentage_24h: 2.5, last_updated: null, data_source: "coingecko",
    });
    mockedMarketApi.fetchMarketOverview.mockResolvedValue({
      active_cryptocurrencies: 43210, top_gainers: [], top_losers: [], last_updated: null, data_source: "coingecko",
    });
    const { container } = render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
    expect(await screen.findByText("$1.23T")).toBeInTheDocument();
    expect(screen.getByText("$98.77B")).toBeInTheDocument();
    expect(screen.getByText("43,210")).toBeInTheDocument();
    expect(screen.getByText(/Bullish/)).toBeInTheDocument();
    expect(screen.getByText(/\+2\.50%/)).toBeInTheDocument();
    expect(mockedMarketApi.fetchGlobalMarket).toHaveBeenCalled();
    expect(mockedMarketApi.fetchMarketOverview).toHaveBeenCalled();
    await waitFor(() => expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBe(0));
  });

  it("ends dashboard card loading and shows error on failed overview calls", async () => {
    mockedMarketApi.fetchGlobalMarket.mockRejectedValue(new Error("overview down"));
    mockedMarketApi.fetchMarketOverview.mockRejectedValue(new Error("overview down"));
    const { container } = render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText(/overview down/i)).toBeInTheDocument();
    await waitFor(() => expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBe(0));
  });


  it("is a read-only command center: no search box, filters or paginated table", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => expect(mockedMarketApi.fetchGainers).toHaveBeenCalled());
    expect(screen.queryByLabelText(/search cryptocurrencies/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /filters/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows N/A for dominance when the backend doesn't provide it, never an invented value", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText("BTC Dominance")).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(2);
  });

  it("shows BTC and ETH dominance when the backend provides them", async () => {
    mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
      total_market_cap_usd: 1e12, total_volume_24h_usd: 1e10,
      market_cap_percentage: { btc: 52.34, eth: 17.8 }, active_cryptocurrencies: 100,
      market_cap_change_percentage_24h: -1.2, last_updated: null, data_source: "coingecko",
    });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText("52.3%")).toBeInTheDocument();
    expect(screen.getByText("17.8%")).toBeInTheDocument();
    expect(screen.getByText(/Bearish/)).toBeInTheDocument();
  });

  it("builds the heatmap from the real market dataset and links tiles to Coin Details", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue({
      items: [
        { coin_id: "h1", name: "Heat One", symbol: "H1", logo_url: null, market_cap_rank: 1, price_usd: 10,
          percent_change_24h: 4, high_24h_usd: null, low_24h_usd: null, market_cap_usd: 9e9, volume_24h_usd: 1e8,
          circulating_supply: null, last_updated: null },
        { coin_id: "h2", name: "Heat Two", symbol: "H2", logo_url: null, market_cap_rank: 2, price_usd: 5,
          percent_change_24h: -4, high_24h_usd: null, low_24h_usd: null, market_cap_usd: 1e9, volume_24h_usd: 1e7,
          circulating_supply: null, last_updated: null },
        { coin_id: "h3", name: "No Cap Coin", symbol: "NC", logo_url: null, market_cap_rank: null, price_usd: 1,
          percent_change_24h: 1, high_24h_usd: null, low_24h_usd: null, market_cap_usd: null, volume_24h_usd: null,
          circulating_supply: null, last_updated: null },
      ],
      page: 1, limit: 60, total: 3, pages: 1, sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/coins/:coinId" element={<div>Coin Details Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    const list = await screen.findByRole("list", { name: /coins by market cap/i });
    const tiles = within(list).getAllByRole("listitem");
    expect(tiles).toHaveLength(2); // the coin without market cap is omitted, not given an invented size
    expect(screen.getByText(/1 coin without market-cap data not shown/i)).toBeInTheDocument();

    await user.click(tiles[0]);
    expect(await screen.findByText("Coin Details Page")).toBeInTheDocument();
  });

  it("only offers the real market-history ranges; 1H and Total Market are disabled, not faked", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await screen.findByText("Market Performance");
    expect(screen.getByRole("button", { name: "1H" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Total Market" })).toBeDisabled();
    for (const label of ["24H", "7D", "30D", "90D", "1Y"]) {
      expect(screen.getByRole("button", { name: label })).toBeEnabled();
    }
  });

  it("charts real BTC history from the backend when BTC is in the dataset", async () => {
    mockedMarketApi.fetchMarketCoins.mockResolvedValue({
      items: [
        { coin_id: "btc-id", name: "Bitcoin", symbol: "BTC", logo_url: null, market_cap_rank: 1, price_usd: 50000,
          percent_change_24h: 1, high_24h_usd: null, low_24h_usd: null, market_cap_usd: 1e12, volume_24h_usd: 1e10,
          circulating_supply: null, last_updated: null },
      ],
      page: 1, limit: 60, total: 1, pages: 1, sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
    });
    mockedMarketApi.fetchCoinHistory.mockResolvedValue({ candles: [], timeframe: "7D", granularity: "1h" } as never);
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => expect(mockedMarketApi.fetchCoinHistory).toHaveBeenCalledWith("btc-id", "7D"));
    expect(await screen.findByText(/no price history is available/i)).toBeInTheDocument();
  });

  it("switches Market Movers tabs and loads volume data only when asked", async () => {
    mockedMarketApi.fetchTopByVolume.mockResolvedValue([
      { coin_id: "v1", name: "Volume Leader", symbol: "VL", logo_url: null, market_cap_rank: 1, price_usd: 3,
        percent_change_24h: 0.5, market_cap_usd: 1e9, volume_24h_usd: 4.2e9, volatility_24h_pct: null },
    ]);
    const user = userEvent.setup();
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => expect(mockedMarketApi.fetchGainers).toHaveBeenCalled());
    expect(mockedMarketApi.fetchTopByVolume).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "Highest Volume" }));
    expect(await screen.findByText("Volume Leader")).toBeInTheDocument();
    expect(screen.getByText("$4.2B")).toBeInTheDocument();
  });

  it("Quick Discovery links pre-filter the Markets explorer", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const section = (await screen.findByText("Quick Discovery")).closest("section") as HTMLElement;
    expect(within(section).getByRole("link", { name: /highest volume/i })).toHaveAttribute("href", "/markets?tab=volume");
    expect(within(section).getByRole("link", { name: /large cap/i })).toHaveAttribute("href", "/markets?cap=gt10b");
    expect(within(section).getByRole("link", { name: /small cap/i })).toHaveAttribute("href", "/markets?cap=lt1b");
  });

  it("lists recently viewed coins from this device and opens them, with no fake entries when empty", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText(/coins you open will appear here/i)).toBeInTheDocument();
  });

  it("shows recently viewed coins that were really opened", async () => {
    // Record through the real action so the view is persisted like a real visit: AppShell reloads the
    // lists from storage on mount, which would discard state that was only set in memory.
    useUserListsStore.getState().recordView({ coin_id: "r1", name: "Opened Coin", symbol: "OPN", logo_url: null });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByRole("link", { name: /opened coin/i })).toHaveAttribute("href", "/coins/r1");
  });

  it("shows the latest real articles, linking to the original source", async () => {
    mockedNewsApi.fetchNews.mockResolvedValue(
      buildNewsList([buildArticle({ title: "Dashboard headline", source_url: "https://publisher.example/d1" })])
    );
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const link = await screen.findByRole("link", { name: /dashboard headline/i });
    expect(link).toHaveAttribute("href", "https://publisher.example/d1");
    expect(screen.getByRole("link", { name: /all news/i })).toHaveAttribute("href", "/news");
  });

  it("says plainly when no news is stored and shows no articles", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByText(/no news articles are stored yet/i)).toBeInTheDocument();
  });

  it("shows a retryable error when the heatmap dataset fails, with a clean message", async () => {
    const { ApiError } = await import("../types/apiError");
    mockedMarketApi.fetchMarketCoins.mockRejectedValue(new ApiError("Too many", 429));
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const messages = await screen.findAllByText("Market data provider is temporarily rate limited. Please try again shortly.");
    expect(messages.length).toBeGreaterThan(0);
  });

  it("does not request the same dataset twice on first load", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await waitFor(() => expect(mockedMarketApi.fetchGainers).toHaveBeenCalled());
    expect(mockedMarketApi.fetchMarketCoins).toHaveBeenCalledTimes(1);
    expect(mockedMarketApi.fetchGlobalMarket).toHaveBeenCalledTimes(1);
    expect(mockedMarketApi.fetchMarketOverview).toHaveBeenCalledTimes(1);
  });
});
