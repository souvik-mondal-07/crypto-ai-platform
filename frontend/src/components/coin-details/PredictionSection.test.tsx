import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PredictionSection } from "./PredictionSection";
import * as predictionsApi from "../../services/api/predictions.api";
import { ApiError } from "../../types/apiError";
import { buildPrediction, buildPredictionList, buildUnavailable } from "../../test-fixtures/predictions";
import type { PredictionListResponse } from "../../types/predictions";

vi.mock("../../services/api/predictions.api", () => ({ fetchCoinPredictions: vi.fn() }));
const mocked = vi.mocked(predictionsApi);
const COIN = "507f1f77bcf86cd799439011";

beforeEach(() => vi.clearAllMocks());

describe("PredictionSection", () => {
  it("shows direction, return, range, confidence, model, version and generated time", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList());
    render(<PredictionSection coinId={COIN} />);

    expect(await screen.findByText("Model Prediction")).toBeInTheDocument();
    expect(await screen.findByText("Up")).toBeInTheDocument();
    expect(screen.getByText("+2.40%")).toBeInTheDocument();
    expect(screen.getByText("$101.20 – $104.00")).toBeInTheDocument();
    expect(screen.getByText("+1.20% to +4.00%", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("71%")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: /direction confidence/i })).toHaveAttribute("aria-valuenow", "71");
    expect(screen.getByText("XGBoost")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("Generated")).toBeInTheDocument();
    expect(screen.getByText(/1 minute ago|just now|60 seconds ago/i)).toBeInTheDocument();
    expect(screen.getByText(/57\.4%/)).toBeInTheDocument(); // held-out directional accuracy, with its sample size
    expect(screen.getByText(/412 samples/)).toBeInTheDocument();
    expect(mocked.fetchCoinPredictions.mock.calls[0][0]).toBe(COIN);
  });

  it("labels it a model prediction with the disclaimer and never offers a decision or advice", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList());
    const { container } = render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText(/machine-learning estimate based on historical data/i)).toBeInTheDocument();
    expect(screen.getByText(/not a guarantee of future performance/i)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\b(buy|sell|hold)\b/i);
    expect(container.textContent).not.toMatch(/risk score|recommend/i);
  });

  it("shows a skeleton while loading and settles into data (never stuck loading)", async () => {
    let resolve!: (v: PredictionListResponse) => void;
    mocked.fetchCoinPredictions.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<PredictionSection coinId={COIN} />);
    expect(screen.getByRole("status", { name: /loading prediction/i })).toBeInTheDocument();
    resolve(buildPredictionList());
    expect(await screen.findByText("Up")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /loading prediction/i })).not.toBeInTheDocument();
  });

  it("offers only horizons that have a valid prediction and switches between them", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(
      buildPredictionList(
        [
          buildPrediction({ horizon: "4h", predicted_return: -0.0155, direction: "down", predicted_price_range: { lower: 97.5, upper: 99.5 }, predicted_return_range: { lower: -0.025, upper: -0.005 }, confidence: 0.58 }),
          buildPrediction({ horizon: "24h" }),
        ],
        [buildUnavailable("7d", "model_unavailable"), buildUnavailable("30d", "model_unavailable"), buildUnavailable("1h", "model_unavailable")],
      ),
    );
    render(<PredictionSection coinId={COIN} />);
    await screen.findByText("Up");

    const group = screen.getByRole("group", { name: /prediction horizon/i });
    expect(group.querySelectorAll("button")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "7 days" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "24 hours" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.setup().click(screen.getByRole("button", { name: "4 hours" }));
    expect(screen.getByText("Down")).toBeInTheDocument();
    expect(screen.getByText("-1.55%")).toBeInTheDocument();
    expect(screen.getByText("$97.50 – $99.50")).toBeInTheDocument();
    expect(screen.queryByText("Up")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "4 hours" })).toHaveAttribute("aria-pressed", "true");
    expect(mocked.fetchCoinPredictions).toHaveBeenCalledTimes(1); // switching is local, no refetch
  });

  it("defaults to the first available horizon when 24h is not available", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList([buildPrediction({ horizon: "7d" })], [buildUnavailable("24h", "model_unavailable")]));
    render(<PredictionSection coinId={COIN} />);
    await screen.findByText("Up");
    expect(screen.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "true");
  });

  it("states that confidence is unavailable instead of inventing one", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(
      buildPredictionList([buildPrediction({ confidence: null, confidence_status: "unavailable", confidence_note: "Confidence could not be calibrated reliably for this model." })]),
    );
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText(/could not be calibrated reliably/i)).toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  });

  it("shows 'no clear direction' for a flat prediction", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList([buildPrediction({ direction: "flat", predicted_return: 0.0004, confidence: null, confidence_status: "unavailable" })]));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText("No clear direction")).toBeInTheDocument();
  });

  it("explains a missing range rather than drawing one", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList([buildPrediction({ predicted_price_range: null, predicted_return_range: null })]));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText(/predicted range is not available/i)).toBeInTheDocument();
  });

  it("flags an expired prediction", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList([buildPrediction({ is_stale: true })]));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText(/has expired/i)).toBeInTheDocument();
  });

  it("shows 'Prediction unavailable' with a reason when no model exists", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(
      buildPredictionList([], (["1h", "4h", "24h", "7d", "30d"] as const).map((h) => buildUnavailable(h, "model_unavailable"))),
    );
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText("Prediction unavailable")).toBeInTheDocument();
    expect(screen.getByText(/no validated prediction model is available/i)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /prediction horizon/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument(); // no numbers at all
    expect(screen.getByText(/not a guarantee/i)).toBeInTheDocument();
  });

  it("shows 'Insufficient historical data' with the backend's reason", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(
      buildPredictionList([], [buildUnavailable("24h", "insufficient_data", "Only 120 usable candles; at least 400 are required.")]),
    );
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText("Insufficient historical data")).toBeInTheDocument();
    expect(screen.getByText(/only 120 usable candles/i)).toBeInTheDocument();
  });

  it("handles an empty response without crashing", async () => {
    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList([], []));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText("Prediction unavailable")).toBeInTheDocument();
  });

  it("shows an error with Retry, and recovers on retry", async () => {
    mocked.fetchCoinPredictions.mockRejectedValueOnce(new ApiError("boom", 500));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText(/predictions could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /loading prediction/i })).not.toBeInTheDocument();

    mocked.fetchCoinPredictions.mockResolvedValue(buildPredictionList());
    await userEvent.setup().click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText("Up")).toBeInTheDocument();
    await waitFor(() => expect(mocked.fetchCoinPredictions).toHaveBeenCalledTimes(2));
  });

  it("maps a network failure to a clear message", async () => {
    mocked.fetchCoinPredictions.mockRejectedValue(new ApiError("Network Error"));
    render(<PredictionSection coinId={COIN} />);
    expect(await screen.findByText(/unable to reach the server/i)).toBeInTheDocument();
  });
});
