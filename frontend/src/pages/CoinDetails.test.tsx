import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { CoinDetails } from "./CoinDetails";
import { ThemeProvider } from "../context/ThemeContext";
import * as coinsApi from "../services/api/coins.api";
import * as marketApi from "../services/api/market.api";
import * as technicalAnalysisApi from "../services/api/technicalAnalysis.api";
import * as fundamentalsApi from "../services/api/fundamentals.api";
import { ApiError } from "../types/apiError";
import { useUserListsStore } from "../store/userListsStore";
import * as newsApi from "../services/api/news.api";
import * as predictionsApi from "../services/api/predictions.api";
import * as decisionsApi from "../services/api/decisions.api";
import * as aiAnalysisApi from "../services/api/aiAnalysis.api";
import { buildDecision, buildInsufficientDecision } from "../test-fixtures/decisions";
import { buildAiAnalysis } from "../test-fixtures/aiAnalysis";
import type { AiAnalysisResponse } from "../types/aiAnalysis";
import { buildPredictionList } from "../test-fixtures/predictions";
import { buildFundamentals } from "../test-fixtures/fundamentals";
import { buildInsufficientSentiment, buildNewsList } from "../test-fixtures/news";

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
  fetchCoinHistory: vi.fn(),
  fetchMarketOverview: vi.fn(),
  fetchGainers: vi.fn(),
  fetchLosers: vi.fn(),
  fetchGlobalMarket: vi.fn(),
  fetchTrending: vi.fn(),
}));

// Phase 10: technical analysis is loaded independently of the main
// coin/history load state, so it needs its own mock — otherwise every
// test in this file would fire a real (failing) network request.
vi.mock("../services/api/technicalAnalysis.api", () => ({
  fetchTechnicalAnalysis: vi.fn(),
}));

// Phase 11: fundamentals load independently too (own loading/error/empty
// state), so they get their own mock for the same reason.
vi.mock("../services/api/fundamentals.api", () => ({
  fetchFundamentals: vi.fn(),
}));

// Phase 12: news and sentiment load independently too.
vi.mock("../services/api/news.api", () => ({
  fetchNews: vi.fn(),
  fetchNewsSources: vi.fn(),
  fetchCoinSentiment: vi.fn(),
}));

// Phase 13: model predictions load independently too.
vi.mock("../services/api/predictions.api", () => ({ fetchCoinPredictions: vi.fn() }));

// Phase 14: risk & decision loads independently too.
vi.mock("../services/api/decisions.api", () => ({ fetchDecision: vi.fn() }));

// Phase 15: AI analysis loads independently too (read stored -> generate).
vi.mock("../services/api/aiAnalysis.api", () => ({ fetchAiAnalysis: vi.fn(), generateAiAnalysis: vi.fn() }));

// The chart library needs canvas/layout APIs jsdom doesn't provide;
// the chart's own data transformation is covered separately in
// utils/chartUtils.test.ts.
vi.mock("../components/coin-details/CandlestickChart", () => ({
  CandlestickChart: ({ candles }: { candles: unknown[] }) => (
    <div data-testid="candlestick-chart">{candles.length} candles</div>
  ),
}));

const mockedCoinsApi = vi.mocked(coinsApi);
const mockedMarketApi = vi.mocked(marketApi);
const mockedTechnicalAnalysisApi = vi.mocked(technicalAnalysisApi);
const mockedFundamentalsApi = vi.mocked(fundamentalsApi);
const mockedNewsApi = vi.mocked(newsApi);
const mockedPredictionsApi = vi.mocked(predictionsApi);
const mockedDecisionsApi = vi.mocked(decisionsApi);
const mockedAiApi = vi.mocked(aiAnalysisApi);

const COIN_ID = "507f1f77bcf86cd799439011";

const COIN = {
  id: COIN_ID,
  name: "Uniquely Named Coin",
  symbol: "UNC",
  slug: "uniquely-named-coin",
  logo_url: null,
  market_cap_rank: 7,
  is_active: true,
  providers: { coingecko: { id: "uniquely-named-coin", available: true }, binance: null },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MARKET = {
  coin_id: COIN_ID,
  price_usd: 1234.56,
  market_cap_usd: 9_000_000,
  volume_24h_usd: 500_000,
  high_24h_usd: 1300,
  low_24h_usd: 1200,
  percent_change_1h: 0.5,
  percent_change_24h: -2.25,
  percent_change_7d: 3.1,
  percent_change_30d: null,
  percent_change_1y: 120.5,
  price_change_24h_usd: -28.5,
  circulating_supply: 1_000_000,
  total_supply: 2_000_000,
  max_supply: null,
  fully_diluted_valuation_usd: 12_000_000,
  ath_usd: 5000,
  atl_usd: 10,
  ath_change_percentage: -75.3,
  atl_change_percentage: 12234.0,
  ath_date: "2025-11-01T00:00:00Z",
  atl_date: "2020-03-13T00:00:00Z",
  last_updated: "2026-01-01T00:00:00Z",
  data_source: "coingecko",
  is_stale: false,
};

const TECHNICAL_ANALYSIS = {
  coin_id: COIN_ID,
  symbol: "UNC",
  timeframe: "7D",
  calculated_at: "2026-01-01T00:00:00Z",
  candle_count: 60,
  rsi: { period: 14, current: 55.2, zone: "neutral", history: [] },
  macd: {
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
    current: { timestamp: "2026-01-01T00:00:00Z", macd: 1.1, signal: 0.9, histogram: 0.2 },
    crossover: "none",
    history: [],
  },
  moving_averages: { sma: { "20": 100, "50": null, "200": null }, ema: { "20": 101, "50": null } },
  bollinger_bands: { period: 20, num_std_dev: 2.0, upper: 110, middle: 100, lower: 90 },
  atr: { period: 14, current: 3.5, history: [] },
  volume: { current_volume_24h_usd: 500_000, historical_volume: [], average_volume: null, volume_change_percent: null, trend: "unavailable", historical_volume_source: null },
  support_resistance: { support_levels: [90], resistance_levels: [110] },
  trend: { trend: "neutral", signals_considered: 2 },
  data_source: "coingecko",
};

function renderCoinDetails(coinId = COIN_ID) {
  return render(
    <MemoryRouter initialEntries={[`/coins/${coinId}`]}>
      <ThemeProvider>
        <Routes>
          <Route path="/coins/:coinId" element={<CoinDetails />} />
          <Route path="/markets" element={<div>Markets Page</div>} />
        </Routes>
      </ThemeProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedCoinsApi.fetchCoinById.mockResolvedValue(COIN);
  mockedMarketApi.fetchCoinMarketData.mockResolvedValue(MARKET);
  mockedMarketApi.fetchCoinHistory.mockResolvedValue({
    coin_id: COIN_ID,
    timeframe: "7D",
    granularity: "4h",
    candles: [
      { timestamp: "2026-01-01T00:00:00Z", open: 100, high: 110, low: 95, close: 105, volume: null },
    ],
    data_source: "coingecko",
  });
  mockedTechnicalAnalysisApi.fetchTechnicalAnalysis.mockResolvedValue(TECHNICAL_ANALYSIS as never);
  // Default fundamentals fixture is chosen so none of its rendered text
  // duplicates what the Phase 9/10 tests above query for by exact text
  // (rank "#7", price, "1y", "Fully Diluted Valuation", "55.2", ...).
  mockedFundamentalsApi.fetchFundamentals.mockResolvedValue(buildFundamentals());
  mockedNewsApi.fetchNews.mockResolvedValue(buildNewsList([]));
  mockedNewsApi.fetchCoinSentiment.mockResolvedValue(buildInsufficientSentiment());
  // No trained model by default: renders the honest "unavailable" state, with no numbers
  // that could collide with the Phase 9/10 text assertions above.
  mockedPredictionsApi.fetchCoinPredictions.mockResolvedValue(buildPredictionList([], []));
  // Default: not enough data for a decision, so the Phase 14 section renders its honest "no decision"
  // state with no numbers or BUY/HOLD/SELL text that could collide with the earlier text assertions.
  mockedDecisionsApi.fetchDecision.mockResolvedValue(buildInsufficientDecision());
  // Default: the AI explanation is still loading (never resolves), so the section shows only its
  // skeleton — no Retry button, no text and no BUY/HOLD/SELL wording that could collide with the
  // page-wide assertions above. The AI section's own behaviour is tested in the last describe below.
  mockedAiApi.fetchAiAnalysis.mockReturnValue(new Promise<AiAnalysisResponse>(() => undefined));
});

describe("CoinDetails", () => {
  it("extracts the coin ID from the route and requests that exact coin", async () => {
    renderCoinDetails();
    await waitFor(() => expect(mockedCoinsApi.fetchCoinById).toHaveBeenCalledWith(COIN_ID));
  });

  it("renders the real coin name, symbol, rank and price from the backend", async () => {
    renderCoinDetails();
    const heading = await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    expect(heading).toBeInTheDocument();
    expect(screen.getByText("UNC")).toBeInTheDocument();
    // The rank is shown in the page header and again in the "Rank" stat card; assert the header's.
    const header = heading.parentElement;
    expect(header).not.toBeNull();
    expect(within(header as HTMLElement).getByText("#7")).toBeInTheDocument();
    expect(screen.getByText(/1,234\.56/)).toBeInTheDocument();
    // Never a hard-coded well-known coin.
    expect(screen.queryByText("Bitcoin")).not.toBeInTheDocument();
  });

  it("renders the chart once historical data loads", async () => {
    renderCoinDetails();
    expect(await screen.findByTestId("candlestick-chart")).toHaveTextContent("1 candles");
  });

  it("shows a not-found state for a coin the backend doesn't have", async () => {
    mockedCoinsApi.fetchCoinById.mockRejectedValue(new Error("No coin found with id 'x'."));
    renderCoinDetails();
    expect(await screen.findByText(/cryptocurrency not found/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to markets/i })).toBeInTheDocument();
  });

  it("shows a retry-capable error state when the chart request fails", async () => {
    mockedMarketApi.fetchCoinHistory.mockRejectedValue(new Error("boom"));
    renderCoinDetails();
    expect(await screen.findByText(/unable to load historical data/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an empty state when the timeframe has no candles", async () => {
    mockedMarketApi.fetchCoinHistory.mockResolvedValue({
      coin_id: COIN_ID, timeframe: "7D", granularity: "4h", candles: [], data_source: "coingecko",
    });
    renderCoinDetails();
    expect(await screen.findByText(/no historical data available for this timeframe/i)).toBeInTheDocument();
  });

  it("refetches history with the new timeframe without refetching the coin", async () => {
    const user = userEvent.setup();
    renderCoinDetails();

    await screen.findByTestId("candlestick-chart");
    expect(mockedCoinsApi.fetchCoinById).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "30D" }));

    await waitFor(() =>
      expect(mockedMarketApi.fetchCoinHistory).toHaveBeenCalledWith(COIN_ID, "30D", expect.anything())
    );
    // Changing the timeframe must not reload the whole page/coin.
    expect(mockedCoinsApi.fetchCoinById).toHaveBeenCalledTimes(1);
  });

  it("still renders the coin header when market data is unavailable", async () => {
    mockedMarketApi.fetchCoinMarketData.mockRejectedValue(new Error("no market data"));
    renderCoinDetails();
    expect(await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ })).toBeInTheDocument();
    expect(screen.getByText(/no market data has been synchronized/i)).toBeInTheDocument();
  });
});

describe("CoinDetails — Phase 9 additional real-data fields", () => {
  it("shows the absolute 24h USD change alongside the percentage", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    expect(screen.getByText(/-\$28\.50/)).toBeInTheDocument();
  });

  it("shows fully diluted valuation when the backend supplies it", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    expect(screen.getByText("Fully Diluted Valuation")).toBeInTheDocument();
  });

  it("shows the 1y performance figure", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    expect(screen.getByText("1y")).toBeInTheDocument();
    expect(screen.getByText("+120.50%")).toBeInTheDocument();
  });

  it("shows ATH/ATL dates only when the backend provides them", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    // Both dates are supplied in the MARKET fixture.
    expect(screen.getAllByText(/2025|2020/).length).toBeGreaterThan(0);
  });

  it("omits fully diluted valuation gracefully (N/A) when absent, never fabricating a number", async () => {
    mockedMarketApi.fetchCoinMarketData.mockResolvedValue({ ...MARKET, fully_diluted_valuation_usd: null });
    renderCoinDetails();
    await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ });
    // The stat card is present with N/A, not hidden and not a fake value.
    expect(screen.getByText("Fully Diluted Valuation").nextSibling?.textContent).toBe("N/A");
  });
});

describe("CoinDetails — Phase 10 Technical Analysis", () => {
  it("renders RSI/MACD/trend once technical analysis loads", async () => {
    renderCoinDetails();
    expect(await screen.findByText("55.2")).toBeInTheDocument();
    expect(screen.getByText("neutral", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText(/no recent crossover/i)).toBeInTheDocument();
  });

  it("shows an empty/insufficient-data state without a generic error when history is too short", async () => {
    mockedTechnicalAnalysisApi.fetchTechnicalAnalysis.mockRejectedValue(
      new Error("Only 5 candles are available; at least 20 are needed to compute technical analysis.")
    );
    renderCoinDetails();
    expect(
      await screen.findByText(/not enough historical data yet to compute technical analysis/i)
    ).toBeInTheDocument();
  });

  it("shows a retry-capable error state for a genuine failure", async () => {
    mockedTechnicalAnalysisApi.fetchTechnicalAnalysis.mockRejectedValue(new Error("Service unavailable."));
    renderCoinDetails();
    expect(await screen.findByText("Service unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("never renders a BUY/HOLD/SELL decision anywhere in the section", async () => {
    renderCoinDetails();
    await screen.findByText("55.2");
    // The only permitted occurrence is the support/resistance disclaimer ("... not guaranteed to hold"),
    // where "hold" is a verb about price levels, not a decision.
    const decisionWords = screen
      .queryAllByText(/\b(buy|sell|hold)\b/i)
      .filter((element) => !/not guaranteed to hold/i.test(element.textContent ?? ""));
    expect(decisionWords).toEqual([]);
  });

  it("toggling the moving-average overlay checkbox does not refetch the coin or history", async () => {
    const user = userEvent.setup();
    renderCoinDetails();
    await screen.findByText("55.2");

    await user.click(screen.getByRole("checkbox", { name: /show sma 20\/50 on chart/i }));

    expect(mockedCoinsApi.fetchCoinById).toHaveBeenCalledTimes(1);
    expect(mockedMarketApi.fetchCoinHistory).toHaveBeenCalledTimes(1);
  });
});

describe("CoinDetails — Phase 11 Fundamental Analysis", () => {
  const section = () => screen.getByRole("region", { name: /fundamental analysis/i });

  it("renders the Fundamental Analysis section with data once the coin has loaded", async () => {
    renderCoinDetails();
    expect(await screen.findByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
    expect(within(section()).getByText("$1.23B")).toBeInTheDocument();
    expect(within(section()).getByRole("heading", { name: "Fundamental Score" })).toBeInTheDocument();
    expect(mockedFundamentalsApi.fetchFundamentals).toHaveBeenCalledTimes(1);
    expect(mockedFundamentalsApi.fetchFundamentals).toHaveBeenCalledWith(
      COIN_ID,
      expect.objectContaining({ forceRefresh: false })
    );
  });

  it("does not request fundamentals when the coin itself could not be loaded", async () => {
    mockedCoinsApi.fetchCoinById.mockRejectedValue(new Error("No coin found with id 'x'."));
    renderCoinDetails();
    expect(await screen.findByText(/cryptocurrency not found/i)).toBeInTheDocument();
    expect(mockedFundamentalsApi.fetchFundamentals).not.toHaveBeenCalled();
  });

  it("shows its own loading state without blocking the rest of the page", async () => {
    mockedFundamentalsApi.fetchFundamentals.mockReturnValue(new Promise(() => {}));
    renderCoinDetails();
    expect(await screen.findByText("Loading fundamental analysis...")).toBeInTheDocument();
    // Coin details, chart and technical analysis are unaffected.
    expect(await screen.findByText("55.2")).toBeInTheDocument();
    expect(await screen.findByTestId("candlestick-chart")).toBeInTheDocument();
  });

  it("shows a retry-capable error state that does not affect other sections", async () => {
    mockedFundamentalsApi.fetchFundamentals.mockRejectedValue(new Error("Fundamentals service is down."));
    renderCoinDetails();
    expect(await screen.findByText("Fundamentals service is down.")).toBeInTheDocument();
    expect(within(section()).getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(await screen.findByText("55.2")).toBeInTheDocument(); // technical analysis still fine
  });

  it("retries after an error and then shows the data", async () => {
    const user = userEvent.setup();
    mockedFundamentalsApi.fetchFundamentals.mockRejectedValueOnce(new Error("Fundamentals service is down."));
    renderCoinDetails();
    await screen.findByText("Fundamentals service is down.");

    await user.click(within(section()).getByRole("button", { name: /retry/i }));

    expect(await screen.findByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
    expect(mockedFundamentalsApi.fetchFundamentals).toHaveBeenCalledTimes(2);
  });

  it("shows an empty state, not an error, when the coin has no fundamental data", async () => {
    mockedFundamentalsApi.fetchFundamentals.mockRejectedValue(
      new ApiError("No fundamental data is available.", 404, "FUNDAMENTALS_NOT_AVAILABLE")
    );
    renderCoinDetails();
    expect(
      await screen.findByText("Fundamental data is not available for this coin yet.")
    ).toBeInTheDocument();
    expect(within(section()).queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
  });

  it("shows partial data with 'Not available' for the missing parts and the backend's notice", async () => {
    mockedFundamentalsApi.fetchFundamentals.mockResolvedValue(
      buildFundamentals({
        project_info: null,
        ecosystem: null,
        is_partial: true,
        unavailable_sections: ["project_info", "ecosystem"],
        warnings: ["Project information could not be retrieved from the provider right now."],
      })
    );
    renderCoinDetails();
    const projectHeading = await screen.findByRole("heading", { name: "Project Information" });
    expect(within(projectHeading.closest("div")!.parentElement as HTMLElement).getByText("Not available")).toBeInTheDocument();
    expect(screen.getByText(/could not be retrieved from the provider right now/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
  });

  it("asks the backend to force a refresh when Refresh data is clicked", async () => {
    const user = userEvent.setup();
    renderCoinDetails();
    await screen.findByRole("heading", { name: "Market Overview" });

    await user.click(screen.getByRole("button", { name: /refresh data/i }));

    await waitFor(() =>
      expect(mockedFundamentalsApi.fetchFundamentals).toHaveBeenLastCalledWith(
        COIN_ID,
        expect.objectContaining({ forceRefresh: true })
      )
    );
  });

  it("does not refetch fundamentals when the chart timeframe changes", async () => {
    const user = userEvent.setup();
    renderCoinDetails();
    await screen.findByRole("heading", { name: "Market Overview" });

    await user.click(screen.getByRole("button", { name: "30D" }));

    expect(mockedFundamentalsApi.fetchFundamentals).toHaveBeenCalledTimes(1);
  });

  it("never renders a BUY/HOLD/SELL decision within the section", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { name: "Market Overview" });
    const text = section().textContent ?? "";
    expect(text).not.toMatch(/\b(buy|sell|hold)\b/i);
  });
});

describe("CoinDetails — workspace navigation and personal lists", () => {
  beforeEach(() => {
    localStorage.clear();
    useUserListsStore.setState({ userId: "1", watchlist: [], recent: [], compare: [] });
  });

  it("offers in-page navigation only for sections that exist", async () => {
    renderCoinDetails();
    const nav = await screen.findByRole("navigation", { name: /coin sections/i });
    const labels = within(nav).getAllByRole("button").map((button) => button.textContent);
    expect(labels).toEqual(["Overview", "Chart", "Technical", "Fundamental", "Sentiment", "Prediction", "Risk & Decision", "AI Analysis", "News"]);
    expect(within(nav).getByRole("button", { name: "AI Analysis" })).toBeInTheDocument();
  });

  it("stars and unstars the coin", async () => {
    const user = userEvent.setup();
    renderCoinDetails();

    await user.click(await screen.findByRole("button", { name: /add uniquely named coin to watchlist/i }));
    expect(useUserListsStore.getState().watchlist).toEqual([COIN_ID]);

    await user.click(screen.getByRole("button", { name: /remove uniquely named coin from watchlist/i }));
    expect(useUserListsStore.getState().watchlist).toEqual([]);
  });

  it("records the opened coin for Recently Viewed exactly once per visit", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { name: "Market Overview" });
    const recent = useUserListsStore.getState().recent;
    expect(recent).toHaveLength(1);
    expect(recent[0]).toEqual(expect.objectContaining({ coin_id: COIN_ID, name: "Uniquely Named Coin", symbol: "UNC" }));
  });

  it("renders the Model Prediction section and a Prediction nav entry for the route's coin", async () => {
    renderCoinDetails();
    expect(await screen.findByText("Model Prediction")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prediction" })).toBeInTheDocument();
    await waitFor(() => expect(mockedPredictionsApi.fetchCoinPredictions).toHaveBeenCalledTimes(1));
    expect(mockedPredictionsApi.fetchCoinPredictions.mock.calls[0][0]).toBe(COIN_ID);
  });

  it("keeps the rest of the page working when predictions fail", async () => {
    mockedPredictionsApi.fetchCoinPredictions.mockRejectedValue(new ApiError("boom", 500));
    renderCoinDetails();
    expect(await screen.findByText(/predictions could not be loaded/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ })).toBeInTheDocument();
    expect(await screen.findByTestId("candlestick-chart")).toBeInTheDocument();
  });

  it("renders the Risk & Decision section and a nav entry for the route's coin", async () => {
    renderCoinDetails();
    expect(await screen.findByRole("heading", { name: "Risk & Decision" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Risk & Decision" })).toBeInTheDocument();
    await waitFor(() => expect(mockedDecisionsApi.fetchDecision).toHaveBeenCalledTimes(1));
    expect(mockedDecisionsApi.fetchDecision.mock.calls[0][0]).toBe(COIN_ID);
  });

  it("keeps the rest of the page working when the decision request fails", async () => {
    mockedDecisionsApi.fetchDecision.mockRejectedValue(new ApiError("boom", 500));
    renderCoinDetails();
    expect(await screen.findByText(/risk and decision analysis could not be loaded/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: /Uniquely Named Coin/ })).toBeInTheDocument();
    expect(await screen.findByTestId("candlestick-chart")).toBeInTheDocument();
    expect(screen.getByText("Model Prediction")).toBeInTheDocument();
  });

  it("keeps the Model Prediction section free of decisions while Risk & Decision shows one", async () => {
    mockedDecisionsApi.fetchDecision.mockResolvedValue(buildDecision());
    mockedPredictionsApi.fetchCoinPredictions.mockResolvedValue(buildPredictionList());
    renderCoinDetails();
    expect(await screen.findByLabelText("Model-based decision: BUY")).toBeInTheDocument();
    const prediction = (await screen.findByText("Model Prediction")).closest("section") as HTMLElement;
    expect(prediction.textContent).not.toMatch(/\b(buy|sell|hold)\b/i);
  });
});

describe("CoinDetails — AI Analysis (Phase 15)", () => {
  const aiSection = () => screen.getByRole("region", { name: "AI Analysis" });

  it("requests the stored AI analysis once, for the route's internal coin id", async () => {
    renderCoinDetails();
    await screen.findByRole("heading", { name: "Market Overview" });
    await waitFor(() => expect(mockedAiApi.fetchAiAnalysis).toHaveBeenCalledTimes(1));
    expect(mockedAiApi.fetchAiAnalysis.mock.calls[0][0]).toBe(COIN_ID);
    expect(mockedAiApi.generateAiAnalysis).not.toHaveBeenCalled();
  });

  it("renders the AI explanation next to the unchanged Phase 14 decision section", async () => {
    mockedAiApi.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis({ coin_id: COIN_ID }));
    renderCoinDetails();
    expect(await within(await screen.findByRole("region", { name: "AI Analysis" })).findByText(/synthetic summary/i)).toBeInTheDocument();
    // The decision section is still driven only by the Phase 14 API, never by the AI text.
    expect(await screen.findByRole("heading", { name: "Risk & Decision" })).toBeInTheDocument();
    expect(mockedDecisionsApi.fetchDecision).toHaveBeenCalledTimes(1);
  });

  it("generates one when none is stored yet", async () => {
    mockedAiApi.fetchAiAnalysis.mockRejectedValue(new ApiError("none", 404, "AI_ANALYSIS_NOT_FOUND"));
    mockedAiApi.generateAiAnalysis.mockResolvedValue(buildAiAnalysis({ coin_id: COIN_ID, cached: false }));
    renderCoinDetails();
    expect(await within(await screen.findByRole("region", { name: "AI Analysis" })).findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(mockedAiApi.generateAiAnalysis).toHaveBeenCalledTimes(1);
    expect(mockedAiApi.generateAiAnalysis.mock.calls[0][0]).toBe(COIN_ID);
  });

  it("keeps every other section working when the AI service is unavailable", async () => {
    mockedAiApi.fetchAiAnalysis.mockRejectedValue(new ApiError("down", 503, "AI_UNAVAILABLE"));
    renderCoinDetails();
    expect(await within(await screen.findByRole("region", { name: "AI Analysis" })).findByText("AI analysis is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Market Overview" })).toBeInTheDocument();
    expect(await screen.findByTestId("candlestick-chart")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Risk & Decision" })).toBeInTheDocument();
    // Only the AI section offers a retry for this failure.
    expect(within(aiSection()).getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
