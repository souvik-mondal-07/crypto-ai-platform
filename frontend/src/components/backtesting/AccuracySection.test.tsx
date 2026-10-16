import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { accuracy, insufficientMetrics, noDataMetrics } from "../../test-fixtures/backtesting";
import type { AccuracyResponse } from "../../types/backtesting";
import { AccuracySection, INSUFFICIENT_MESSAGE } from "./AccuracySection";

const IDLE = { running: false, message: null, error: null };
const FILTERS = { horizon: "", modelVersion: "", coinId: "" };

function setup(props: Partial<Parameters<typeof AccuracySection>[0]> = {}) {
  const handlers = { onFilters: vi.fn(), onRetry: vi.fn(), onRefresh: vi.fn() };
  render(<AccuracySection data={accuracy()} loading={false} error={null} filters={FILTERS} refresh={IDLE} {...handlers} {...props} />);
  return handlers;
}

describe("AccuracySection", () => {
  it("shows the real metrics, sample size and evaluation period", () => {
    setup();
    const summary = within(screen.getByLabelText("Accuracy summary"));
    expect(summary.getByText("62.5%")).toBeInTheDocument();            // directional accuracy
    expect(summary.getByText("0.800 pp")).toBeInTheDocument();         // MAE
    expect(summary.getByText("1.100 pp")).toBeInTheDocument();         // RMSE
    expect(summary.getByText("120")).toBeInTheDocument();              // sample size
    expect(summary.getByText(/Aug 1, 2026 – Sep 1, 2026/)).toBeInTheDocument();
    expect(summary.getByText(/Nominal 80%/)).toBeInTheDocument();
    expect(screen.getByTestId("accuracy-coverage")).toHaveTextContent("150 stored predictions · 125 matured · 120 matched");
    expect(screen.getByText(/duplicate\(s\) ignored/)).toBeInTheDocument();
    expect(screen.getByText(/missing future price 2/)).toBeInTheDocument();
  });

  it("lists breakdowns by horizon, model/version and coin", () => {
    setup();
    expect(screen.getByRole("row", { name: /^24h/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /^7d/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /xgboost v3/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /^BTC/ })).toBeInTheDocument();
  });

  it("shows the honest insufficient-data message and N/A instead of zeros", () => {
    setup({ data: accuracy({ overall: insufficientMetrics() }) });
    expect(screen.getByText(new RegExp(INSUFFICIENT_MESSAGE.replace(".", "\\.")))).toBeInTheDocument();
    const summary = within(screen.getByLabelText("Accuracy summary"));
    expect(summary.getAllByText("N/A").length).toBeGreaterThanOrEqual(5);
    expect(summary.queryByText("0.0%")).not.toBeInTheDocument();
    expect(summary.getByText("5")).toBeInTheDocument();
  });

  it("shows an empty state when nothing has matured", () => {
    setup({ data: accuracy({ overall: noDataMetrics(), by_horizon: [], by_model: [], by_coin: [] }) });
    expect(screen.getByText("No matured predictions have been matched to market outcomes yet.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Accuracy summary")).not.toBeInTheDocument();
  });

  it("renders limitations supplied by the API", () => {
    setup({ data: accuracy({ limitations: ["3 matured prediction(s) have not been matched to market outcomes yet; use 'Update outcomes'."] }) });
    expect(within(screen.getByRole("list", { name: "Limitations" })).getByText(/3 matured prediction/)).toBeInTheDocument();
  });

  it("reports filter changes (horizon, model/version, coin) from API-provided options only", async () => {
    const { onFilters } = setup();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Prediction horizon"), "7d");
    expect(onFilters).toHaveBeenLastCalledWith({ horizon: "7d" });
    await user.selectOptions(screen.getByLabelText("Model and version"), "xgboost|3");
    expect(onFilters).toHaveBeenLastCalledWith({ modelVersion: "xgboost|3" });
    await user.selectOptions(screen.getByLabelText("Coin"), "a".repeat(24));
    expect(onFilters).toHaveBeenLastCalledWith({ coinId: "a".repeat(24) });
    expect(within(screen.getByLabelText("Prediction horizon")).getAllByRole("option").map((o) => o.textContent)).toEqual(["All horizons", "24h", "7d"]);
  });

  it("starts an outcome update and reflects the running state", async () => {
    const { onRefresh } = setup();
    await userEvent.setup().click(screen.getByRole("button", { name: "Update outcomes" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("disables the button and announces progress while updating", () => {
    setup({ refresh: { running: true, message: null, error: null } });
    expect(screen.getByRole("button", { name: "Updating outcomes..." })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/Matching matured predictions/);
  });

  it("shows a refresh failure", () => {
    setup({ refresh: { running: false, message: null, error: "Provider unavailable" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Provider unavailable");
  });

  it("shows loading, then error with Retry", async () => {
    const { onRetry } = setup({ data: null, loading: true });
    expect(screen.getByRole("status", { name: "Loading model accuracy" })).toBeInTheDocument();
    render(<AccuracySection data={null} loading={false} error="Model accuracy could not be loaded." filters={FILTERS} refresh={IDLE} onFilters={vi.fn()} onRetry={onRetry} onRefresh={vi.fn()} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("never fabricates a number when a metric is null inside an ok result", () => {
    const base: AccuracyResponse = accuracy();
    setup({ data: { ...base, overall: { ...base.overall, range_coverage: null, nominal_coverage: null } } });
    const tile = screen.getByText("Range coverage").closest("div") as HTMLElement;
    expect(within(tile).getByText("N/A")).toBeInTheDocument();
  });
});
