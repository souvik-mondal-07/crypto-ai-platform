import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CoinSentimentSection } from "./CoinSentimentSection";
import * as newsApi from "../../services/api/news.api";
import { ApiError } from "../../types/apiError";
import { buildInsufficientSentiment, buildSentiment } from "../../test-fixtures/news";

vi.mock("../../services/api/news.api", () => ({ fetchNews: vi.fn(), fetchNewsSources: vi.fn(), fetchCoinSentiment: vi.fn() }));
const mocked = vi.mocked(newsApi);
const COIN = "507f1f77bcf86cd799439011";

beforeEach(() => vi.clearAllMocks());

describe("CoinSentimentSection", () => {
  it("shows label, percentages, counts, article count, average score, trend and period", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildSentiment());
    render(<CoinSentimentSection coinId={COIN} />);
    expect(await screen.findByText("Positive 60.0%")).toBeInTheDocument();
    expect(screen.getByText("Neutral 30.0%")).toBeInTheDocument();
    expect(screen.getByText("Negative 10.0%")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument(); // articles analyzed
    expect(screen.getByText("+0.42")).toBeInTheDocument();
    expect(screen.getByText(/more positive than in the previous period/i)).toBeInTheDocument();
    expect(screen.getByText(/analysis period: the last 24 hours/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /sentiment distribution: 60% positive/i })).toBeInTheDocument();
  });

  it("states it is descriptive and never presents a recommendation or prediction", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildSentiment());
    const { container } = render(<CoinSentimentSection coinId={COIN} />);
    expect(await screen.findByText(/not a price prediction/i)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b(buy|sell|hold)\b/i);
  });

  it("switches the analysis period and re-requests from the backend", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildSentiment());
    render(<CoinSentimentSection coinId={COIN} />);
    await screen.findByText("Positive 60.0%");
    expect(mocked.fetchCoinSentiment.mock.calls[0].slice(0, 2)).toEqual([COIN, "24h"]);
    mocked.fetchCoinSentiment.mockResolvedValue(buildSentiment({ timeframe: "7d", total_articles: 40 }));
    await userEvent.setup().click(screen.getByRole("button", { name: "7 days" }));
    expect(await screen.findByText(/analysis period: the last 7 days/i)).toBeInTheDocument();
    expect(mocked.fetchCoinSentiment.mock.calls.at(-1)!.slice(0, 2)).toEqual([COIN, "7d"]);
    expect(await screen.findByText("40")).toBeInTheDocument();
  });

  it("shows an explicit insufficient-data state — no label, no percentages", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildInsufficientSentiment());
    render(<CoinSentimentSection coinId={COIN} />);
    expect(await screen.findByText(/not enough analyzed news to describe sentiment/i)).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText("Overall tone of news")).not.toBeInTheDocument();
  });

  it("explains a partial shortfall and pending articles", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildInsufficientSentiment({ total_articles: 2, pending_article_count: 5 }));
    render(<CoinSentimentSection coinId={COIN} />);
    expect(await screen.findByText(/only 2 analyzed articles .* at least 3 are needed/i)).toBeInTheDocument();
    expect(screen.getByText(/5 related articles are waiting to be analyzed/i)).toBeInTheDocument();
  });

  it("tells the user when the sentiment model is unavailable", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildInsufficientSentiment({ model_status: "unavailable", pending_article_count: 4 }));
    render(<CoinSentimentSection coinId={COIN} />);
    expect(await screen.findByText(/sentiment analysis is currently unavailable/i)).toBeInTheDocument();
  });

  it("loading then error with retry; never stuck loading", async () => {
    mocked.fetchCoinSentiment.mockRejectedValueOnce(new ApiError("x", 503));
    render(<CoinSentimentSection coinId={COIN} />);
    expect(screen.getByText(/loading sentiment/i)).toBeInTheDocument();
    expect(await screen.findByText(/news is temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/loading sentiment/i)).not.toBeInTheDocument();
    mocked.fetchCoinSentiment.mockResolvedValueOnce(buildSentiment());
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText("Positive 60.0%")).toBeInTheDocument();
  });

  it("uses theme-aware classes and non-colour-only indicators", async () => {
    mocked.fetchCoinSentiment.mockResolvedValue(buildSentiment());
    const { container } = render(<CoinSentimentSection coinId={COIN} />);
    await screen.findByText("Positive 60.0%");
    expect(container.innerHTML).toMatch(/dark:bg-slate-900/);
    expect(container.innerHTML).toMatch(/dark:text-emerald-300/);
    expect(screen.getByText("Positive")).toBeInTheDocument(); // text label next to the colour
  });
});
