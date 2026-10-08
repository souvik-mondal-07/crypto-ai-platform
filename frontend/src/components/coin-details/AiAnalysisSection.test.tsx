import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AiAnalysisSection } from "./AiAnalysisSection";
import * as aiApi from "../../services/api/aiAnalysis.api";
import { ApiError } from "../../types/apiError";
import type { AiAnalysisResponse } from "../../types/aiAnalysis";
import { AI_DISCLAIMER_TEXT, buildAiAnalysis, buildAiContent } from "../../test-fixtures/aiAnalysis";

vi.mock("../../services/api/aiAnalysis.api", () => ({ fetchAiAnalysis: vi.fn(), generateAiAnalysis: vi.fn() }));
const mocked = vi.mocked(aiApi);
const COIN = "507f1f77bcf86cd799439011";
const notFound = () => new ApiError("No AI analysis has been generated for this coin yet.", 404, "AI_ANALYSIS_NOT_FOUND");

beforeEach(() => vi.clearAllMocks());

describe("AiAnalysisSection", () => {
  it("shows the AI summary, every explanation section and the factor lists", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    render(<AiAnalysisSection coinId={COIN} />);

    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Analysis" })).toBeInTheDocument();
    expect(screen.getByText("Powered by Gemini 3.1 Flash-Lite")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Market Summary" })).toBeInTheDocument();
    for (const title of [
      "Market Interpretation", "Technical Explanation", "Fundamental Explanation", "Sentiment Explanation",
      "Prediction Explanation", "Risk Explanation", "Decision Explanation",
    ]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
    expect(screen.getByText("Synthetic technical explanation.")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Bullish Factors" })).getByText("Synthetic bullish factor")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Bearish Factors" })).getByText("Synthetic bearish factor")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Key Risks" })).getByText("Synthetic key risk")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Uncertainties" })).getByText("Synthetic uncertainty")).toBeInTheDocument();
    expect(screen.getByText("Synthetic data quality note.")).toBeInTheDocument();
  });

  it("reads the stored analysis without generating one", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);
    expect(mocked.fetchAiAnalysis).toHaveBeenCalledTimes(1);
    expect(mocked.fetchAiAnalysis.mock.calls[0][0]).toBe(COIN);
    expect(mocked.generateAiAnalysis).not.toHaveBeenCalled();
  });

  it("shows the OFFICIAL decision snapshot and the explanation, and says what the AI is explaining", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    render(<AiAnalysisSection coinId={COIN} />);
    const context = await screen.findByTestId("ai-decision-context");
    expect(context).toHaveTextContent("BUY");
    expect(context).toHaveTextContent("Risk Low");
    expect(context).toHaveTextContent("Confidence 78%");
    expect(context).toHaveTextContent("+68");
    expect(screen.getByText(/explanation of why the official decision is buy/i)).toBeInTheDocument();
    expect(screen.getByText(/generated from the platform's market, technical, fundamental, sentiment, prediction, and risk data/i)).toBeInTheDocument();
  });

  it("states honestly when the engine produced no decision", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(
      buildAiAnalysis({ decision_snapshot: { ...buildAiAnalysis().decision_snapshot, decision: null, status: "INSUFFICIENT_DATA", confidence: null, decision_score: null, risk_level: null } }),
    );
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByTestId("ai-decision-context")).toHaveTextContent(/did not produce a BUY \/ HOLD \/ SELL result/i);
  });

  it("always shows the disclaimer, including while loading", async () => {
    let resolve!: (v: AiAnalysisResponse) => void;
    mocked.fetchAiAnalysis.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<AiAnalysisSection coinId={COIN} />);
    expect(screen.getByRole("status", { name: /loading ai analysis/i })).toBeInTheDocument();
    expect(screen.getByText(AI_DISCLAIMER_TEXT)).toBeInTheDocument();
    resolve(buildAiAnalysis());
    await screen.findByText(/synthetic summary/i);
    expect(screen.queryByRole("status", { name: /loading ai analysis/i })).not.toBeInTheDocument();
    expect(screen.getByText(AI_DISCLAIMER_TEXT)).toBeInTheDocument();
  });

  it("generates once when nothing is stored yet, showing a generating state", async () => {
    mocked.fetchAiAnalysis.mockRejectedValue(notFound());
    let resolve!: (v: AiAnalysisResponse) => void;
    mocked.generateAiAnalysis.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<AiAnalysisSection coinId={COIN} />);

    expect(await screen.findByRole("status", { name: /generating ai analysis/i })).toBeInTheDocument();
    resolve(buildAiAnalysis({ cached: false }));
    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(mocked.generateAiAnalysis).toHaveBeenCalledTimes(1);
    expect(mocked.generateAiAnalysis.mock.calls[0][1]).not.toMatchObject({ forceRefresh: true });
  });

  it("asks the backend to refresh an expired analysis while keeping the old text on screen", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis({ is_stale: true }));
    mocked.generateAiAnalysis.mockResolvedValue(buildAiAnalysis({ cached: false, analysis: buildAiContent({ summary: "Fresh synthetic summary." }) }));
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByText("Fresh synthetic summary.")).toBeInTheDocument();
    expect(mocked.generateAiAnalysis).toHaveBeenCalledTimes(1);
  });

  it("keeps the stored explanation and explains why when the background refresh fails", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis({ is_outdated: true }));
    mocked.generateAiAnalysis.mockRejectedValue(new ApiError("x", 503, "AI_UNAVAILABLE"));
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(await screen.findByText(/a new explanation could not be generated: ai analysis is temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/decision has changed since this explanation was written/i)).toBeInTheDocument();
  });

  it("shows which inputs were unavailable instead of hiding the gap", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(
      buildAiAnalysis({ data_availability: { market: { available: true, reason: null }, prediction: { available: false, reason: "Prediction engine unavailable" } } }),
    );
    render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);
    const list = screen.getByRole("list", { name: /inputs that were not available/i });
    expect(within(list).getByText(/prediction engine unavailable/i)).toBeInTheDocument();
    expect(screen.getAllByText(/some input data was unavailable: prediction engine unavailable/i).length).toBe(1);
  });

  it("shows an error with Retry and recovers", async () => {
    mocked.fetchAiAnalysis.mockRejectedValueOnce(new ApiError("boom", 500, "INTERNAL_ERROR"));
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByText(/ai analysis could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /loading ai analysis/i })).not.toBeInTheDocument();

    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
    expect(mocked.fetchAiAnalysis).toHaveBeenCalledTimes(2);
  });

  it("shows 'temporarily unavailable' when Gemini is unavailable, without breaking the section", async () => {
    mocked.fetchAiAnalysis.mockRejectedValue(notFound());
    mocked.generateAiAnalysis.mockRejectedValue(new ApiError("detail", 503, "AI_NOT_CONFIGURED"));
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByText("AI analysis is temporarily unavailable.")).toBeInTheDocument();
    expect(screen.getByText(/risk and decision information on this page is not affected/i)).toBeInTheDocument();
    expect(screen.getByText(AI_DISCLAIMER_TEXT)).toBeInTheDocument();
    expect(screen.queryByText(/detail/)).not.toBeInTheDocument();

    mocked.generateAiAnalysis.mockResolvedValue(buildAiAnalysis());
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/synthetic summary/i)).toBeInTheDocument();
  });

  it("explains insufficient data using the backend's message", async () => {
    mocked.fetchAiAnalysis.mockRejectedValue(notFound());
    mocked.generateAiAnalysis.mockRejectedValue(
      new ApiError("Not enough platform data to explain this coin yet. Unavailable: market, technical.", 422, "AI_INSUFFICIENT_DATA"),
    );
    render(<AiAnalysisSection coinId={COIN} />);
    expect(await screen.findByText("Not enough data for an AI explanation")).toBeInTheDocument();
    expect(screen.getByText(/unavailable: market, technical/i)).toBeInTheDocument();
  });

  it("regenerates on request, keeps the text while generating, and then enforces a cooldown", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);

    mocked.generateAiAnalysis.mockResolvedValue(buildAiAnalysis({ cached: false, analysis: buildAiContent({ summary: "Regenerated synthetic summary." }) }));
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /regenerate analysis/i }));
    expect(await screen.findByText("Regenerated synthetic summary.")).toBeInTheDocument();
    expect(mocked.generateAiAnalysis).toHaveBeenCalledTimes(1);
    expect(mocked.generateAiAnalysis.mock.calls[0][1]).toMatchObject({ forceRefresh: true });

    const button = screen.getByRole("button", { name: /regenerate analysis/i });
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/\(\d+s\)/);
    await user.click(button);
    expect(mocked.generateAiAnalysis).toHaveBeenCalledTimes(1);
  });

  it("disables regenerate while the server says a cooldown applies", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis({ next_regeneration_at: new Date(Date.now() + 45_000).toISOString() }));
    render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);
    expect(screen.getByRole("button", { name: /regenerate analysis/i })).toBeDisabled();
  });

  it("keeps the previous explanation when a regeneration fails", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);

    mocked.generateAiAnalysis.mockRejectedValue(new ApiError("slow down", 429, "AI_RATE_LIMITED"));
    await userEvent.setup().click(screen.getByRole("button", { name: /regenerate analysis/i }));
    expect(await screen.findByText(/a new explanation could not be generated: ai analysis is rate limited/i)).toBeInTheDocument();
    expect(screen.getByText(/synthetic summary/i)).toBeInTheDocument();
  });

  it("does not call the backend again on re-render", async () => {
    mocked.fetchAiAnalysis.mockResolvedValue(buildAiAnalysis());
    const { rerender } = render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);
    rerender(<AiAnalysisSection coinId={COIN} />);
    rerender(<AiAnalysisSection coinId={COIN} />);
    await waitFor(() => expect(mocked.fetchAiAnalysis).toHaveBeenCalledTimes(1));
    expect(mocked.generateAiAnalysis).not.toHaveBeenCalled();
  });

  it("never shows one coin's explanation for another coin", async () => {
    const OTHER = "507f1f77bcf86cd799439022";
    mocked.fetchAiAnalysis.mockResolvedValueOnce(buildAiAnalysis());
    const { rerender } = render(<AiAnalysisSection coinId={COIN} />);
    await screen.findByText(/synthetic summary/i);

    mocked.fetchAiAnalysis.mockReturnValueOnce(new Promise(() => undefined));
    rerender(<AiAnalysisSection coinId={OTHER} />);
    expect(screen.queryByText(/synthetic summary/i)).not.toBeInTheDocument();
    expect(await screen.findByRole("status", { name: /loading ai analysis/i })).toBeInTheDocument();
  });
});
