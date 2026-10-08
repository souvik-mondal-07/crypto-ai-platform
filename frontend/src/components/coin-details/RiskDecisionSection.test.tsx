import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RiskDecisionSection } from "./RiskDecisionSection";
import * as decisionsApi from "../../services/api/decisions.api";
import { ApiError } from "../../types/apiError";
import type { DecisionResponse } from "../../types/decisions";
import { buildDecision, buildDecisionWithoutPrediction, buildInsufficientDecision } from "../../test-fixtures/decisions";

vi.mock("../../services/api/decisions.api", () => ({ fetchDecision: vi.fn() }));
const mocked = vi.mocked(decisionsApi);
const COIN = "507f1f77bcf86cd799439011";

beforeEach(() => vi.clearAllMocks());

describe("RiskDecisionSection", () => {
  it("renders the decision, score, confidence, risk score and risk level", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);

    expect(await screen.findByLabelText("Model-based decision: BUY")).toHaveTextContent("BUY");
    expect(screen.getByRole("heading", { name: "Risk & Decision" })).toBeInTheDocument();
    expect(screen.getByText("Model-Based Decision")).toBeInTheDocument();
    expect(screen.getByText("+68")).toBeInTheDocument();
    expect(screen.getByText("78%")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Decision confidence" })).toHaveAttribute("aria-valuenow", "78");
    expect(screen.getByText("34/100")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Risk score" })).toHaveAttribute("aria-valuenow", "34");
    expect(screen.getByText("Low", { selector: "p" })).toBeInTheDocument();
    expect(mocked.fetchDecision.mock.calls[0][0]).toBe(COIN);
  });

  it.each([
    ["BUY", "+68"],
    ["HOLD", "+12"],
    ["SELL", "-54"],
  ] as const)("displays a %s decision clearly", async (decision, score) => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ decision, decision_score: Number(score) }));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByLabelText(`Model-based decision: ${decision}`)).toHaveTextContent(decision);
    expect(screen.getByText(score)).toBeInTheDocument();
  });

  it.each([
    ["VERY_LOW", "Very low"],
    ["MODERATE", "Moderate"],
    ["HIGH", "High"],
    ["VERY_HIGH", "Very high"],
  ] as const)("shows risk level %s as %s", async (level, label) => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ risk_level: level }));
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  });

  it("shows the signal summary from the backend's real signals", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    const rows = screen.getByText("Signal summary").parentElement as HTMLElement;
    expect(within(rows).getByText("Technical").nextSibling).toHaveTextContent("Bullish");
    expect(within(rows).getByText("Fundamental").nextSibling).toHaveTextContent("Strong");
    expect(within(rows).getByText("Sentiment").nextSibling).toHaveTextContent("Positive");
    expect(within(rows).getByText("ML Prediction").nextSibling).toHaveTextContent("Bullish");
    expect(within(rows).getByText("Risk").nextSibling).toHaveTextContent("Low");
  });

  it("lists the positive and risk factors returned by the backend", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    const positive = screen.getByRole("list", { name: "Positive factors" });
    expect(within(positive).getByText("Positive MACD momentum")).toBeInTheDocument();
    expect(within(positive).getByText("Positive recent news sentiment")).toBeInTheDocument();
    const negative = screen.getByRole("list", { name: "Risk factors" });
    expect(within(negative).getByText(/wide bollinger bands/i)).toBeInTheDocument();
  });

  it("says so when there are no factors rather than inventing some", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ positive_factors: [], negative_factors: [] }));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(/no notable positive factors/i)).toBeInTheDocument();
    expect(screen.getByText(/no notable risk factors/i)).toBeInTheDocument();
  });

  it("presents it as model-based decision support with the disclaimer, never a guarantee", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(/generated from available market, technical, fundamental, sentiment, and machine-learning signals/i)).toBeInTheDocument();
    expect(screen.getByText(/not a guarantee of future performance/i)).toBeInTheDocument();
  });

  it("shows a skeleton while loading and settles into data (never stuck loading)", async () => {
    let resolve!: (v: DecisionResponse) => void;
    mocked.fetchDecision.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(screen.getByRole("status", { name: /loading risk and decision/i })).toBeInTheDocument();
    resolve(buildDecision());
    expect(await screen.findByLabelText(/model-based decision/i)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /loading risk and decision/i })).not.toBeInTheDocument();
  });

  it("shows an error with Retry, and recovers on retry", async () => {
    mocked.fetchDecision.mockRejectedValueOnce(new ApiError("boom", 500));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(/risk and decision analysis could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /loading risk and decision/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/model-based decision/i)).not.toBeInTheDocument();

    mocked.fetchDecision.mockResolvedValue(buildDecision());
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByLabelText("Model-based decision: BUY")).toBeInTheDocument();
    await waitFor(() => expect(mocked.fetchDecision).toHaveBeenCalledTimes(2));
  });

  it("maps a network failure to a clear message", async () => {
    mocked.fetchDecision.mockRejectedValue(new ApiError("Network Error"));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(/unable to reach the server/i)).toBeInTheDocument();
  });

  it("explains insufficient data and shows no decision, score or fake confidence", async () => {
    mocked.fetchDecision.mockResolvedValue(buildInsufficientDecision());
    const { container } = render(<RiskDecisionSection coinId={COIN} />);

    expect(await screen.findByText("Insufficient data")).toBeInTheDocument();
    expect(screen.getByText(/only 1 of the 4 analysis modules have usable data/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/model-based decision/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b(buy|sell|hold)\b/i);

    const unused = screen.getByRole("list", { name: /inputs that could not be used/i });
    expect(within(unused).getByText(/fundamental analysis/i)).toBeInTheDocument();
    expect(within(unused).getByText(/too few analysed news articles/i)).toBeInTheDocument();
    expect(within(unused).getByText(/prediction engine is not available/i)).toBeInTheDocument();
    // The disclaimer is still shown.
    expect(screen.getByText(/not a guarantee/i)).toBeInTheDocument();
  });

  it.each([
    ["STALE_DATA", "Data is out of date"],
    ["PREDICTION_UNAVAILABLE", "ML prediction unavailable"],
    ["ANALYSIS_UNAVAILABLE", "Analysis unavailable"],
  ] as const)("shows a clear title for status %s", async (status, title) => {
    mocked.fetchDecision.mockResolvedValue({ ...buildInsufficientDecision("A reason from the backend."), status });
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(screen.getByText("A reason from the backend.")).toBeInTheDocument();
  });

  it("handles an unavailable prediction without breaking the decision", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecisionWithoutPrediction());
    render(<RiskDecisionSection coinId={COIN} />);

    expect(await screen.findByLabelText("Model-based decision: BUY")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("ML prediction unavailable. Decision calculated using the remaining available signals.");
    const rows = screen.getByText("Signal summary").parentElement as HTMLElement;
    expect(within(rows).getByText("ML Prediction").nextSibling).toHaveTextContent("Unavailable");
    expect(screen.getByRole("list", { name: /data notes/i })).toBeInTheDocument();
  });

  it("states that confidence is unavailable instead of inventing one", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ confidence: null, confidence_status: "unavailable" }));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText("Unavailable", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/reliable confidence could not be established/i)).toBeInTheDocument();
    expect(screen.queryByRole("meter", { name: "Decision confidence" })).not.toBeInTheDocument();
  });

  it("shows an unavailable risk score when the backend could not establish one", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ risk_score: null, risk_level: null }));
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    expect(screen.queryByRole("meter", { name: "Risk score" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  });

  it("shows risk-rule overrides that changed the outcome", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({
      decision: "HOLD", base_decision: "BUY", risk_level: "HIGH", risk_score: 66,
      overrides: [{ rule: "risk_buy_gate", description: "Risk is high: a BUY needs a risk-adjusted score of at least +35 (this one is +30.0), so the decision is HOLD." }],
    }));
    render(<RiskDecisionSection coinId={COIN} />);
    const list = await screen.findByRole("list", { name: /risk rules applied/i });
    expect(within(list).getByText(/a buy needs a risk-adjusted score/i)).toBeInTheDocument();
  });

  it("flags an expired decision", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision({ is_stale: true }));
    render(<RiskDecisionSection coinId={COIN} />);
    expect(await screen.findByText(/has expired/i)).toBeInTheDocument();
  });

  it("exposes the calculation (explanation, risk components, versions) on demand", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    expect(screen.getByText("How this was calculated")).toBeInTheDocument();
    expect(screen.getByText(/risk is low \(34\/100\)/i)).toBeInTheDocument();
    expect(screen.getByText(/^volatility$/i)).toBeInTheDocument();
    expect(screen.getByText(/not used/i)).toBeInTheDocument(); // the unavailable prediction component
    expect(screen.getByText(/engine v1\.0/i)).toBeInTheDocument();
  });

  it("recalculates on request without blanking the visible decision", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);

    mocked.fetchDecision.mockResolvedValue(buildDecision({ decision: "SELL", decision_score: -40 }));
    await userEvent.setup().click(screen.getByRole("button", { name: /recalculate risk and decision/i }));
    expect(await screen.findByLabelText("Model-based decision: SELL")).toBeInTheDocument();
    expect(mocked.fetchDecision).toHaveBeenCalledTimes(2);
    expect(mocked.fetchDecision.mock.calls[1][1]).toMatchObject({ forceRefresh: true });
  });

  it("requests the decision once per coin, not on every re-render", async () => {
    mocked.fetchDecision.mockResolvedValue(buildDecision());
    const { rerender } = render(<RiskDecisionSection coinId={COIN} />);
    await screen.findByLabelText(/model-based decision/i);
    rerender(<RiskDecisionSection coinId={COIN} />);
    rerender(<RiskDecisionSection coinId={COIN} />);
    expect(mocked.fetchDecision).toHaveBeenCalledTimes(1);
  });
});
