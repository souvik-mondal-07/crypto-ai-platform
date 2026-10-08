import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { CoinNewsSection } from "./CoinNewsSection";
import * as newsApi from "../../services/api/news.api";
import { ApiError } from "../../types/apiError";
import { buildArticle, buildNewsList } from "../../test-fixtures/news";

vi.mock("../../services/api/news.api", () => ({ fetchNews: vi.fn(), fetchNewsSources: vi.fn(), fetchCoinSentiment: vi.fn() }));
const mocked = vi.mocked(newsApi);
const COIN = "507f1f77bcf86cd799439011";

function renderSection() {
  return render(
    <MemoryRouter>
      <CoinNewsSection coinId={COIN} coinName="Examplecoin" />
    </MemoryRouter>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("CoinNewsSection", () => {
  it("asks the backend for this coin's news (coin-scoped, not a text search)", async () => {
    mocked.fetchNews.mockResolvedValue(buildNewsList([buildArticle()]));
    renderSection();
    await screen.findByRole("link", { name: /test headline one/i });
    expect(mocked.fetchNews.mock.calls[0][0]).toMatchObject({ coinId: COIN, limit: 5, page: 1 });
    expect(mocked.fetchNews.mock.calls[0][0]).not.toHaveProperty("search");
  });

  it("shows headline, source, time, sentiment and the original link", async () => {
    mocked.fetchNews.mockResolvedValue(
      buildNewsList([
        buildArticle({
          source_url: "https://publisher.example/orig",
          sentiment: { label: "positive", score: 0.6, confidence: 0.9, probabilities: {}, model: "m", analyzed_at: "2026-10-01T00:00:00Z" },
        }),
      ])
    );
    renderSection();
    expect(await screen.findByRole("link", { name: /test headline one/i })).toHaveAttribute("href", "https://publisher.example/orig");
    expect(screen.getByText("Example Publisher")).toBeInTheDocument();
    expect(screen.getByText("Positive")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /see all examplecoin news/i })).toHaveAttribute("href", `/news?coin=${COIN}`);
  });

  it("loading → empty state naming the coin", async () => {
    mocked.fetchNews.mockResolvedValue(buildNewsList([]));
    renderSection();
    expect(screen.getByText(/loading news/i)).toBeInTheDocument();
    expect(await screen.findByText(/no recent news is associated with examplecoin/i)).toBeInTheDocument();
  });

  it("error state with retry that recovers", async () => {
    mocked.fetchNews.mockRejectedValueOnce(new ApiError("x", 429));
    renderSection();
    expect(await screen.findByText(/rate limited/i)).toBeInTheDocument();
    mocked.fetchNews.mockResolvedValueOnce(buildNewsList([buildArticle({ title: "Back again" })]));
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByRole("link", { name: /back again/i })).toBeInTheDocument();
  });

  it("paginates through the backend", async () => {
    mocked.fetchNews.mockResolvedValue(buildNewsList([buildArticle()], { pages: 2, total: 8, limit: 5 }));
    renderSection();
    await screen.findByText(/page 1 of 2/i);
    mocked.fetchNews.mockResolvedValue(buildNewsList([buildArticle({ title: "Second page" })], { page: 2, pages: 2, total: 8, limit: 5 }));
    await userEvent.setup().click(screen.getByRole("button", { name: /next/i }));
    expect(await screen.findByRole("link", { name: /second page/i })).toBeInTheDocument();
    expect(mocked.fetchNews.mock.calls.at(-1)![0]).toMatchObject({ page: 2 });
  });
});
