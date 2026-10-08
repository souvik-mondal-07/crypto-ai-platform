import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";

import { News } from "./News";
import { ThemeProvider } from "../context/ThemeContext";
import * as coinsApi from "../services/api/coins.api";
import * as newsApi from "../services/api/news.api";
import { ApiError } from "../types/apiError";
import { buildArticle, buildNewsList, buildStatus } from "../test-fixtures/news";

vi.mock("../services/api/news.api", () => ({
  fetchNews: vi.fn(),
  fetchNewsSources: vi.fn(),
  fetchCoinSentiment: vi.fn(),
}));
vi.mock("../services/api/coins.api", () => ({
  fetchCoins: vi.fn(),
  searchCoins: vi.fn(),
  fetchCoinById: vi.fn(),
}));

const mockedNews = vi.mocked(newsApi);
const mockedCoins = vi.mocked(coinsApi);

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderNews(initial = "/news") {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[initial]}>
        <News />
        <LocationProbe />
      </MemoryRouter>
    </ThemeProvider>
  );
}

const lastQuery = () => mockedNews.fetchNews.mock.calls.at(-1)![0]!;

beforeEach(() => {
  vi.clearAllMocks();
  mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle()]));
  mockedNews.fetchNewsSources.mockResolvedValue({ items: ["CoinDesk", "Example Publisher"] });
  mockedCoins.searchCoins.mockResolvedValue({ items: [], query: "", limit: 6, total: 0 } as never);
});

describe("News page — states", () => {
  it("shows a loading state, then the real articles", async () => {
    renderNews();
    expect(screen.getByText(/loading news/i)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /test headline one/i })).toBeInTheDocument();
    expect(screen.queryByText(/loading news/i)).not.toBeInTheDocument();
  });

  it("shows a clear empty state (no fabricated articles) when nothing is stored", async () => {
    mockedNews.fetchNews.mockResolvedValue(buildNewsList([]));
    renderNews();
    expect(await screen.findByText(/no news articles are stored yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("shows a no-match empty state when filters exclude everything, with a way back", async () => {
    mockedNews.fetchNews.mockResolvedValue(buildNewsList([]));
    renderNews("/news?source=CoinDesk");
    expect(await screen.findByText(/no articles match these filters/i)).toBeInTheDocument();
    await userEvent.setup().click(screen.getAllByRole("button", { name: /clear filters/i })[0]);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^$/));
  });

  it("shows a clean error with Retry (never stuck loading), and retry re-requests", async () => {
    mockedNews.fetchNews.mockRejectedValueOnce(new ApiError("boom", 503));
    renderNews();
    expect(await screen.findByText(/news is temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/loading news/i)).not.toBeInTheDocument();
    mockedNews.fetchNews.mockResolvedValueOnce(buildNewsList([buildArticle({ title: "Recovered headline" })]));
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByRole("link", { name: /recovered headline/i })).toBeInTheDocument();
  });

  it("explains provider trouble and unavailable sentiment while still showing stored articles", async () => {
    mockedNews.fetchNews.mockResolvedValue(
      buildNewsList([buildArticle()], {
        status: buildStatus({ last_sync_error_code: "PROVIDER_RATE_LIMITED", sentiment_model_status: "unavailable" }),
      })
    );
    renderNews();
    expect(await screen.findByText(/rate-limited the last refresh/i)).toBeInTheDocument();
    expect(screen.getByText(/sentiment analysis is currently unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /test headline one/i })).toBeInTheDocument();
  });
});

describe("News page — pagination and filters (server-side)", () => {
  it("requests the page from the backend and updates the URL", async () => {
    mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle()], { page: 1, pages: 3, total: 55 }));
    renderNews();
    await screen.findByText(/page 1 of 3/i);
    expect(lastQuery()).toMatchObject({ page: 1, limit: 20 });

    mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle({ title: "Page two item" })], { page: 2, pages: 3, total: 55 }));
    await userEvent.setup().click(screen.getByRole("button", { name: /next/i }));
    expect(await screen.findByRole("link", { name: /page two item/i })).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ page: 2 });
    expect(screen.getByTestId("location")).toHaveTextContent("page=2");
  });

  it("disables Previous on the first page and Next on the last", async () => {
    mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle()], { page: 3, pages: 3, total: 41 }));
    renderNews("/news?page=3");
    await screen.findByText(/page 3 of 3/i);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /previous/i })).toBeEnabled();
  });

  it("sends source and sentiment filters to the backend and resets to page 1", async () => {
    mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle()], { page: 2, pages: 3, total: 55 }));
    renderNews("/news?page=2");
    await screen.findByText(/page 2 of 3/i);
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Source"), "CoinDesk");
    await waitFor(() => expect(lastQuery()).toMatchObject({ source: "CoinDesk", page: 1 }));

    await user.selectOptions(screen.getByLabelText("Sentiment"), "negative");
    await waitFor(() => expect(lastQuery()).toMatchObject({ source: "CoinDesk", sentiment: "negative" }));
    expect(screen.getByTestId("location")).toHaveTextContent("sentiment=negative");
  });

  it("debounces text search into a single backend request", async () => {
    renderNews();
    await screen.findByRole("link", { name: /test headline one/i });
    const callsBefore = mockedNews.fetchNews.mock.calls.length;
    await userEvent.setup().type(screen.getByLabelText("Search headlines"), "etf");
    await waitFor(() => expect(lastQuery()).toMatchObject({ search: "etf" }));
    // 3 keystrokes must not become 3 requests
    expect(mockedNews.fetchNews.mock.calls.length - callsBefore).toBeLessThanOrEqual(2);
  });

  it("sends a date range as UTC bounds", async () => {
    renderNews("/news?from=2026-09-01&to=2026-09-30");
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ dateFrom: "2026-09-01T00:00:00Z", dateTo: "2026-09-30T23:59:59.999Z" })
    );
  });

  it("ignores malformed URL filter values instead of sending them to the API", async () => {
    renderNews("/news?sentiment=bullish&from=nonsense&page=-4");
    await waitFor(() => expect(mockedNews.fetchNews).toHaveBeenCalled());
    const query = lastQuery();
    expect(query.page).toBe(1);
    // Malformed values must not be sent at all (the query omits the keys rather than sending them).
    expect(query.sentiment).toBeUndefined();
    expect(query.dateFrom).toBeUndefined();
  });

  it("filters by coin from the URL and surfaces an invalid coin as a clear error", async () => {
    mockedCoins.fetchCoinById.mockResolvedValue({ name: "Bitcoin", symbol: "BTC" } as never);
    mockedNews.fetchNews.mockRejectedValueOnce(new ApiError("No coin found", 404, "COIN_NOT_FOUND"));
    renderNews("/news?coin=507f1f77bcf86cd799439011");
    expect(await screen.findByText(/cryptocurrency was not found/i)).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ coinId: "507f1f77bcf86cd799439011" });

    mockedNews.fetchNews.mockResolvedValue(buildNewsList([buildArticle()]));
    // Two controls legitimately clear the filter here (the chip's X and the error's button); use the error's.
    await userEvent.setup().click(within(screen.getByRole("alert")).getByRole("button", { name: /clear coin filter/i }));
    expect(await screen.findByRole("link", { name: /test headline one/i })).toBeInTheDocument();
    expect(screen.getByTestId("location")).not.toHaveTextContent("coin=");
  });

  it("still shows the feed if the sources list fails to load", async () => {
    mockedNews.fetchNewsSources.mockRejectedValue(new ApiError("down", 503));
    renderNews();
    expect(await screen.findByRole("link", { name: /test headline one/i })).toBeInTheDocument();
    expect(within(screen.getByLabelText("Source")).getByRole("option", { name: "All sources" })).toBeInTheDocument();
  });
});
