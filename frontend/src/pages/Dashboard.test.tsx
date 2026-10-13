import { describe, expect, it, beforeEach, vi } from "vitest";
import { render as rtlRender, screen, waitFor, within, type RenderOptions } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../context/ThemeContext";
import { Dashboard } from "./Dashboard";
import { useAuthStore } from "../store/authStore";
import { useMarketStore } from "../store/marketStore";
import { useUserListsStore } from "../store/userListsStore";
import * as coinsApi from "../services/api/coins.api";
import * as marketApi from "../services/api/market.api";
import * as newsApi from "../services/api/news.api";
import * as aiApi from "../services/api/aiAnalysis.api";
import { portfolioApi } from "../services/api/portfolio.api";
import { buildArticle, buildNewsList } from "../test-fixtures/news";
import { portfolio as buildPortfolio, USER } from "../test-fixtures/userFeatures";
import { usePortfolioStore } from "../store/portfolioStore";
import { useAlertBadgeStore } from "../store/alertBadgeStore";
import { useDashboardStore } from "../store/dashboardStore";

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

vi.mock("../services/api/aiAnalysis.api", async () => {
  const { ApiError } = await import("../types/apiError");
  return {
    // The dashboard only READS stored explanations; "none stored yet" is the neutral default for these tests.
    fetchAiAnalysis: vi.fn(() => Promise.reject(new ApiError("none", 404, "AI_ANALYSIS_NOT_FOUND"))),
    generateAiAnalysis: vi.fn(),
  };
});

vi.mock("../services/api/portfolio.api", () => ({
  portfolioApi: {
    get: vi.fn(() =>
      Promise.resolve({
        currency: "USD",
        holdings: [],
        summary: { total_current_value: 0, total_invested: 0, priced_invested: 0, total_unrealized_pnl: null, total_unrealized_pnl_pct: null, holdings_count: 0, unpriced_count: 0, is_partial: false },
      })
    ),
    add: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    transactions: vi.fn(),
  },
}));

// The Dashboard loads the active-alert count for the sidebar badge.
vi.mock("../services/api/alerts.api", () => ({
  alertsApi: { list: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, limit: 1, pages: 0 })), create: vi.fn(), update: vi.fn(), remove: vi.fn(), check: vi.fn() },
}));

vi.mock("../services/api/settings.api", () => ({
  settingsApi: { get: vi.fn(() => Promise.resolve({ theme: null, notifications: { price_alerts: true } })), update: vi.fn() },
}));

vi.mock("../services/api/watchlist.api", () => ({
  watchlistApi: { list: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, limit: 250, pages: 0 })), add: vi.fn(), remove: vi.fn(), status: vi.fn() },
}));

vi.mock("../services/api/news.api", () => ({
  fetchNews: vi.fn(),
  fetchNewsSources: vi.fn(),
  fetchCoinSentiment: vi.fn(),
}));

// The page renders the real header and charts, which read the theme: always render inside the provider.
function render(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return rtlRender(ui, { wrapper: ThemeProvider, ...options });
}

const mockedNewsApi = vi.mocked(newsApi);
const mockedCoinsApi = vi.mocked(coinsApi);
const mockedMarketApi = vi.mocked(marketApi);

/**
 * Query helpers that address a piece of the page by its accessible name, so every assertion is scoped to the
 * element it is about. The same figure legitimately appears in several places on a dashboard (a market cap in a card
 * and, say, a portfolio total); a bare `screen.getByText("$1.23T")` would pass or fail depending on unrelated panels.
 */
const statCard = (name: string) => screen.getByRole("region", { name });
const welcomeBanner = () => screen.getByRole("region", { name: /^good (morning|afternoon|evening|night)/i });

function marketCoin(rank: number, over: Record<string, unknown> = {}) {
  return {
    coin_id: `c${rank}`, name: `Coin ${rank}`, symbol: `C${rank}`, logo_url: null, market_cap_rank: rank, price_usd: 100 - rank,
    percent_change_24h: rank % 2 === 0 ? 2 : -2, high_24h_usd: null, low_24h_usd: null, market_cap_usd: 1e12 / rank, volume_24h_usd: 1e9,
    circulating_supply: null, last_updated: null, ...over,
  };
}
const coinsPage = (items: ReturnType<typeof marketCoin>[]) => ({
  items, page: 1, limit: 60, total: items.length, pages: 1, sort_by: "market_cap", sort_direction: "desc", data_source: "coingecko",
}) as never;

function resetStores() {
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
  usePortfolioStore.setState({ userId: null, portfolio: null, status: "idle", error: null, saving: false, actionError: null });
  useAlertBadgeStore.setState({ userId: null, count: 0 });
  // The dashboard datasets live in a module-level store, so without this reset a test starts with the PREVIOUS test's
  // coins already present (the AI panel would then fetch for that stale coin first and use up the mocked response).
  useDashboardStore.setState({
    heatmap: { data: [], loading: false, error: null },
    volume: { data: [], loading: false, error: null },
    volatility: { data: [], loading: false, error: null },
  });
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
  useUserListsStore.setState({ userId: null, recent: [], compare: [] });
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

    // The name also appears in the header's account menu, so assert the greeting itself.
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

  it("loads overview data, maps each backend field to its own statistic card, and removes skeletons", async () => {
    mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
      total_market_cap_usd: 1234567890000, total_volume_24h_usd: 98765432100,
      market_cap_percentage: { btc: 52.34, eth: 17.8 }, active_cryptocurrencies: 43210,
      market_cap_change_percentage_24h: 2.5, last_updated: null, data_source: "coingecko",
    });
    mockedMarketApi.fetchMarketOverview.mockResolvedValue({
      active_cryptocurrencies: 43210, top_gainers: [], top_losers: [], last_updated: null, data_source: "coingecko",
    });
    const { container } = render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);

    // Each figure is asserted INSIDE the card it belongs to — a market cap that shows up in the wrong card (or twice
    // in one card) fails, which a page-wide query could not detect.
    const marketCap = within(await screen.findByRole("region", { name: "Total Market Cap" }));
    expect(marketCap.getByText("$1.23T")).toBeInTheDocument();
    expect(marketCap.getByText("+2.50%")).toBeInTheDocument();
    expect(within(statCard("24H Volume")).getByText("$98.77B")).toBeInTheDocument();
    expect(within(statCard("Bitcoin Dominance")).getByText("52.3%")).toBeInTheDocument();
    expect(within(statCard("Tracked Coins")).getByText("43,210")).toBeInTheDocument();
    expect(within(welcomeBanner()).getByText("Bullish")).toBeInTheDocument();

    // And the figures are not leaking into the wrong cards.
    expect(within(statCard("24H Volume")).queryByText("$1.23T")).not.toBeInTheDocument();
    expect(within(statCard("Tracked Coins")).queryByText("+2.50%")).not.toBeInTheDocument();

    expect(mockedMarketApi.fetchGlobalMarket).toHaveBeenCalled();
    expect(mockedMarketApi.fetchMarketOverview).toHaveBeenCalled();
    await waitFor(() => expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBe(0));
  });

  it("renders the five statistic cards, each with a label and a value", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    for (const name of ["Total Market Cap", "24H Volume", "Bitcoin Dominance", "Tracked Coins", "Portfolio Value"]) {
      expect(await screen.findByRole("region", { name })).toBeInTheDocument();
    }
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

  it("shows N/A for market figures the backend doesn't provide, never an invented value", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const dominanceCard = within(await screen.findByRole("region", { name: "Bitcoin Dominance" }));
    // BTC dominance and the ETH figure beside it are both unknown: two N/A in this card, nothing invented.
    expect(dominanceCard.getAllByText("N/A")).toHaveLength(2);
    // Total Market Cap: the value and its 24H-change badge are both unknown. 24H Volume: just the value.
    expect(within(statCard("Total Market Cap")).getAllByText("N/A")).toHaveLength(2);
    expect(within(statCard("24H Volume")).getAllByText("N/A")).toHaveLength(1);
  });

  it("shows BTC and ETH dominance when the backend provides them", async () => {
    mockedMarketApi.fetchGlobalMarket.mockResolvedValue({
      total_market_cap_usd: 1e12, total_volume_24h_usd: 1e10,
      market_cap_percentage: { btc: 52.34, eth: 17.8 }, active_cryptocurrencies: 100,
      market_cap_change_percentage_24h: -1.2, last_updated: null, data_source: "coingecko",
    });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    const dominanceCard = within(await screen.findByRole("region", { name: "Bitcoin Dominance" }));
    expect(dominanceCard.getByText("52.3%")).toBeInTheDocument();
    expect(dominanceCard.getByText("17.8%")).toBeInTheDocument(); // ETH, shown beside BTC
    expect(within(welcomeBanner()).getByText("Bearish")).toBeInTheDocument();
    expect(within(statCard("Total Market Cap")).getByText("-1.20%")).toBeInTheDocument();
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

  it("only offers the real market-history ranges; ALL and Total Market are disabled, not faked", async () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await screen.findByText("Market Performance");
    const ranges = within(screen.getByRole("group", { name: "Time range" }));
    expect(ranges.getByRole("button", { name: "ALL" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Total Market" })).toBeDisabled();
    for (const label of ["1D", "7D", "1M", "3M", "1Y"]) {
      expect(ranges.getByRole("button", { name: label })).toBeEnabled();
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
    // The chart header names the coin and shows its real price.
    const chart = within(screen.getByRole("region", { name: "Market Performance" }));
    expect(chart.getByText("Bitcoin (BTC)")).toBeInTheDocument();
    expect(chart.getByText("$50,000.00")).toBeInTheDocument();
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
    // Signed in as user "1" with that user's lists already loaded, so AppShell's sync keeps them
    // (with no signed-in user it would reload — and empty — the device-local list).
    useAuthStore.setState({
      user: { id: "1", name: "Viewer", email: "v@example.com", role: "user", created_at: "2026-01-01T00:00:00Z" },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
    useUserListsStore.setState({
      userId: "1",
      recent: [{ coin_id: "r1", name: "Opened Coin", symbol: "OPN", logo_url: null, viewed_at: new Date().toISOString() }],
    });
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

  describe("redesigned layout", () => {
    it("shows the sidebar navigation alongside the dashboard, with every item a real link", async () => {
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const nav = await screen.findByRole("navigation", { name: "Main" });
      const hrefs = within(nav).getAllByRole("link").map((link) => link.getAttribute("href"));
      expect(hrefs).toEqual(["/dashboard", "/markets", "/portfolio", "/watchlist", "/alerts", "/news", "/history"]);
      expect(within(nav).getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    });

    it("badges the sidebar's Alerts link with the real active-alert count", async () => {
      useAuthStore.setState({ user: USER, isAuthenticated: true, isLoading: false, error: null });
      useUserListsStore.setState({ userId: USER.id, recent: [] });
      const { alertsApi } = await import("../services/api/alerts.api");
      vi.mocked(alertsApi.list).mockResolvedValueOnce({ items: [], total: 4, page: 1, limit: 1, pages: 4 });
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const nav = await screen.findByRole("navigation", { name: "Main" });
      expect(await within(nav).findByRole("link", { name: "Alerts (4 active)" })).toHaveAttribute("href", "/alerts");
      expect(alertsApi.list).toHaveBeenCalledWith(1, 1, "ACTIVE");
    });

    it("welcome banner shows the real date, Market Open, and no trend when the market change is unknown", async () => {
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const banner = within(await screen.findByRole("region", { name: /^good (morning|afternoon|evening|night)/i }));
      expect(banner.getByText("Market Open")).toBeInTheDocument();
      const today = new Date().toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
      expect(banner.getByText(today)).toBeInTheDocument();
      expect(banner.queryByText(/bullish|bearish|neutral/i)).not.toBeInTheDocument();
    });

    it("Portfolio Value says to sign in rather than showing a number when signed out", async () => {
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const card = within(await screen.findByRole("region", { name: "Portfolio Value" }));
      expect(card.getByText("N/A")).toBeInTheDocument();
      expect(card.getByText(/sign in to see your portfolio/i)).toBeInTheDocument();
    });

    it("Portfolio Value and the Portfolio panel show the backend's totals for a signed-in user", async () => {
      useAuthStore.setState({ user: USER, isAuthenticated: true, isLoading: false, error: null });
      useUserListsStore.setState({ userId: USER.id, recent: [] });
      vi.mocked(portfolioApi.get).mockResolvedValue(buildPortfolio());
      render(<MemoryRouter><Dashboard /></MemoryRouter>);

      const card = within(await screen.findByRole("region", { name: "Portfolio Value" }));
      expect(await card.findByText("$200.00")).toBeInTheDocument();
      expect(card.getByText("+100.00% P/L")).toBeInTheDocument();

      const panel = within(screen.getByRole("region", { name: "Portfolio" }));
      expect(panel.getAllByText("$200.00").length).toBeGreaterThan(0); // donut centre + headline total, both from the same value
      expect(panel.getByRole("link", { name: /view portfolio/i })).toHaveAttribute("href", "/portfolio");
    });

    it("builds a compact heatmap: the 9 largest coins plus one Others tile that links to Markets", async () => {
      mockedMarketApi.fetchMarketCoins.mockResolvedValue(coinsPage(Array.from({ length: 12 }, (_, index) => marketCoin(index + 1))));
      const user = userEvent.setup();
      render(
        <MemoryRouter initialEntries={["/dashboard"]}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/markets" element={<div>Markets Page</div>} />
          </Routes>
        </MemoryRouter>
      );
      const list = await screen.findByRole("list", { name: /coins by market cap/i });
      const tiles = within(list).getAllByRole("listitem");
      expect(tiles).toHaveLength(10);
      const others = within(list).getByRole("listitem", { name: /other coins \(3\)/i });
      expect(within(list).queryByRole("listitem", { name: /Coin 10 /i })).not.toBeInTheDocument(); // folded into Others
      await user.click(others);
      expect(await screen.findByText("Markets Page")).toBeInTheDocument();
    });

    it("AI Market Insights reads the stored explanation and separates AI text from the decision engine's result", async () => {
      mockedMarketApi.fetchMarketCoins.mockResolvedValue(coinsPage([marketCoin(1, { name: "Bitcoin", symbol: "BTC", coin_id: "btc-id" })]));
      vi.mocked(aiApi.fetchAiAnalysis).mockResolvedValueOnce({
        coin_id: "btc-id", symbol: "BTC", kind: "ai_explanation", status: "ready",
        analysis: {
          summary: "Momentum is steady.", market_analysis: "", technical_analysis: "", fundamental_analysis: "", sentiment_analysis: "",
          prediction_analysis: "", risk_analysis: "", decision_explanation: "", bullish_factors: ["Volume is rising"],
          bearish_factors: [], key_risks: ["High volatility expected"], uncertainties: [], data_quality: "", disclaimer: "Not financial advice.",
        },
        decision_snapshot: { decision: "HOLD", status: "ok", risk_level: "MEDIUM", risk_score: 40, confidence: 0.6, decision_score: 0.1, engine_version: "1", generated_at: "2026-10-01T00:00:00Z" },
        data_availability: {}, model: "gemini", model_version: null, prompt_version: "1", source_data_timestamp: "2026-10-01T00:00:00Z",
        generated_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-02T00:00:00Z", is_stale: false, is_outdated: false, cached: true,
        next_regeneration_at: null, disclaimer: "Not financial advice.",
      } as never);
      render(<MemoryRouter><Dashboard /></MemoryRouter>);

      const panel = within(await screen.findByRole("region", { name: "AI Market Insights" }));
      expect(await panel.findByText("Momentum is steady.")).toBeInTheDocument();
      expect(panel.getByRole("heading", { name: "Market Sentiment" })).toBeInTheDocument();
      expect(panel.getByRole("heading", { name: "Key Observations" })).toBeInTheDocument();
      expect(panel.getByText("Volume is rising")).toBeInTheDocument();
      expect(panel.getByRole("heading", { name: "Risk Warnings" })).toBeInTheDocument();
      expect(panel.getByText("High volatility expected")).toBeInTheDocument();
      // The deterministic decision is labelled as the engine's, not the AI's.
      expect(panel.getByRole("heading", { name: "Technical Signals" })).toBeInTheDocument();
      expect(panel.getByText(/decision engine/i)).toBeInTheDocument();
      expect(panel.getByRole("link", { name: /view detailed analysis/i })).toHaveAttribute("href", "/coins/btc-id#coin-ai-analysis");
    });

    it("AI Market Insights says plainly when no explanation is stored, and ends its loading state", async () => {
      mockedMarketApi.fetchMarketCoins.mockResolvedValue(coinsPage([marketCoin(1, { name: "Bitcoin", symbol: "BTC", coin_id: "btc-id" })]));
      const { container } = render(<MemoryRouter><Dashboard /></MemoryRouter>);
      expect(await screen.findByText(/no ai explanation has been generated for bitcoin yet/i)).toBeInTheDocument();
      await waitFor(() => expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBe(0));
    });

    it("AI Market Insights shows an empty message (not a permanent skeleton) when there is no market data", async () => {
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const panel = within(await screen.findByRole("region", { name: "AI Market Insights" }));
      expect(await panel.findByText(/appear once market data is available/i)).toBeInTheDocument();
      expect(panel.getByRole("link", { name: /view detailed analysis/i })).toHaveAttribute("href", "/markets");
    });

    it("Quick Actions link to real destinations; AI Analysis follows the largest coin", async () => {
      mockedMarketApi.fetchMarketCoins.mockResolvedValue(coinsPage([marketCoin(1, { coin_id: "big-id" })]));
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const actions = within(await screen.findByRole("region", { name: "Quick Actions" }));
      expect(actions.getByRole("link", { name: "Explore Markets" })).toHaveAttribute("href", "/markets");
      expect(actions.getByRole("link", { name: "Search Coin" })).toHaveAttribute("href", "/markets"); // signed out: no palette
      expect(actions.getByRole("link", { name: "Watchlist" })).toHaveAttribute("href", "/watchlist");
      expect(actions.getByRole("link", { name: "Portfolio" })).toHaveAttribute("href", "/portfolio");
      expect(actions.getByRole("link", { name: "Alerts" })).toHaveAttribute("href", "/alerts");
      await waitFor(() => expect(actions.getByRole("link", { name: "AI Analysis" })).toHaveAttribute("href", "/coins/big-id#coin-ai-analysis"));
    });

    it("Quick Actions' Search Coin opens the command palette for signed-in users", async () => {
      useAuthStore.setState({ user: USER, isAuthenticated: true, isLoading: false, error: null });
      useUserListsStore.setState({ userId: USER.id, recent: [] });
      const user = userEvent.setup();
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const actions = within(await screen.findByRole("region", { name: "Quick Actions" }));
      await user.click(actions.getByRole("button", { name: "Search Coin" }));
      expect(await screen.findByRole("dialog")).toBeInTheDocument();
    });

    it("Top Movers and Latest News offer View All links to their full pages", async () => {
      render(<MemoryRouter><Dashboard /></MemoryRouter>);
      const movers = within(await screen.findByRole("region", { name: "Top Movers" }));
      expect(movers.getByRole("link", { name: /view all/i })).toHaveAttribute("href", "/markets?tab=gainers");
      await user_clickTab(movers, "Losers");
      expect(movers.getByRole("link", { name: /view all/i })).toHaveAttribute("href", "/markets?tab=losers");
      expect(within(screen.getByRole("region", { name: "Latest News" })).getByRole("link", { name: /view all news/i })).toHaveAttribute("href", "/news");
    });
  });
});

async function user_clickTab(scope: ReturnType<typeof within>, name: string) {
  await userEvent.setup().click(scope.getByRole("tab", { name }));
}
