import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { backtestingApi } from "../services/api/backtesting.api";
import { ApiError } from "../types/apiError";
import {
  accuracy, config, decisionEvaluation, insufficientMetrics, paged, runDetail, runSummary, trade,
} from "../test-fixtures/backtesting";
import { renderAt, signInWithReadyStores } from "../test-fixtures/userFeatures";
import { Backtesting } from "./Backtesting/Backtesting";

vi.mock("../services/api/backtesting.api", () => ({
  backtestingApi: {
    config: vi.fn(), accuracy: vi.fn(), refreshOutcomes: vi.fn(), refreshStatus: vi.fn(), decisions: vi.fn(),
    createRun: vi.fn(), listRuns: vi.fn(), getRun: vi.fn(), runTrades: vi.fn(),
  },
  splitModelVersion: vi.fn(),
}));
vi.mock("../services/api/watchlist.api", () => ({ watchlistApi: { list: vi.fn(), add: vi.fn(), remove: vi.fn(), status: vi.fn() } }));
vi.mock("../services/api/settings.api", () => ({ settingsApi: { get: vi.fn(), update: vi.fn() } }));
// The real picker searches /coins/search; a stub that "chooses" Bitcoin keeps these tests about the page.
vi.mock("../components/common/CoinPicker", async () => {
  const { createElement } = await import("react");
  return {
    CoinPicker: ({ onSelect }: { onSelect: (coin: unknown) => void }) =>
      createElement("button", { type: "button", onClick: () => onSelect({ id: "a".repeat(24), name: "Bitcoin", symbol: "btc", logo_url: null }) }, "Pick Bitcoin"),
  };
});
vi.mock("../services/api/coins.api", () => ({
  fetchCoins: vi.fn(), fetchCoinById: vi.fn(), searchCoins: vi.fn().mockResolvedValue({ items: [], query: "", count: 0 }),
}));

const api = vi.mocked(backtestingApi);
const RUN_ID = "r".repeat(32);

function happyPath() {
  api.config.mockResolvedValue(config());
  api.accuracy.mockResolvedValue(accuracy());
  api.decisions.mockResolvedValue(decisionEvaluation());
  api.listRuns.mockResolvedValue(paged([]) as never);
  api.refreshStatus.mockResolvedValue({ running: false, accepted: false, message: null, last_started_at: null, last_finished_at: null, last_error: null, last_report: null });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  signInWithReadyStores();
  happyPath();
});

const render = () => renderAt(<Backtesting />, "/backtesting");
const accuracySummary = async () => within(await screen.findByLabelText("Accuracy summary"));

describe("Backtesting page", () => {
  it("shows model accuracy, decision evaluation, configuration and results sections from real API data", async () => {
    render();
    expect((await accuracySummary()).getByText("62.5%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Model Accuracy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Decision Evaluation" })).toBeInTheDocument();
    expect(await screen.findByRole("form", { name: "Backtest configuration" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Backtest Results" })).toBeInTheDocument();
    expect(await screen.findByText("You have not run any backtests yet.")).toBeInTheDocument();
    expect(screen.getByText(/No real trades are placed/)).toBeInTheDocument();
  });

  it("shows the honest insufficient-data message when too few predictions have matured", async () => {
    api.accuracy.mockResolvedValue(accuracy({ overall: insufficientMetrics() }));
    render();
    expect(await screen.findByText(/Insufficient historical predictions to calculate reliable accuracy metrics\./)).toBeInTheDocument();
  });

  it("re-queries accuracy with the chosen horizon, model/version and coin filters", async () => {
    render();
    await accuracySummary();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Prediction horizon"), "7d");
    await waitFor(() => expect(api.accuracy).toHaveBeenLastCalledWith(expect.objectContaining({ horizon: "7d" })));
    await user.selectOptions(screen.getByLabelText("Model and version"), "xgboost|3");
    await waitFor(() => expect(api.accuracy).toHaveBeenLastCalledWith(expect.objectContaining({ horizon: "7d", modelVersion: "xgboost|3" })));
    await user.selectOptions(screen.getByLabelText("Coin"), "a".repeat(24));
    await waitFor(() => expect(api.accuracy).toHaveBeenLastCalledWith(expect.objectContaining({ coinId: "a".repeat(24) })));
  });

  it("shows an accuracy error with Retry that reloads", async () => {
    api.accuracy.mockRejectedValueOnce(new ApiError("boom", 500));
    render();
    const alert = await screen.findByText(/could not be loaded/i);
    expect(alert).toBeInTheDocument();
    await userEvent.setup().click(screen.getAllByRole("button", { name: "Retry" })[0]);
    expect((await accuracySummary()).getByText("62.5%")).toBeInTheDocument();
  });

  it("updates outcomes and reloads the metrics", async () => {
    api.refreshOutcomes.mockResolvedValue({ running: false, accepted: false, message: "Outcomes were refreshed moments ago.", last_started_at: null, last_finished_at: null, last_error: null, last_report: null });
    render();
    await accuracySummary();
    await userEvent.setup().click(screen.getByRole("button", { name: "Update outcomes" }));
    expect(await screen.findByText("Outcomes were refreshed moments ago.")).toBeInTheDocument();
    await waitFor(() => expect(api.accuracy.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("re-queries decision evaluation for the chosen horizon", async () => {
    render();
    await screen.findByRole("table", { name: "Decision evaluation" });
    await userEvent.setup().selectOptions(screen.getByLabelText("Decision evaluation horizon"), "7d");
    await waitFor(() => expect(api.decisions).toHaveBeenLastCalledWith("7d"));
  });

  it("shows an error with Retry when the backtest options cannot load", async () => {
    api.config.mockRejectedValueOnce(new ApiError("down", 503));
    render();
    expect(await screen.findByText(/Backtest options could not be loaded|unavailable/i)).toBeInTheDocument();
  });

  it("does not call the API until the configuration is valid", async () => {
    render();
    const form = await screen.findByRole("form", { name: "Backtest configuration" });
    await userEvent.setup().click(within(form).getByRole("button", { name: "Run backtest" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("Choose at least one coin.");
    expect(api.createRun).not.toHaveBeenCalled();
  });

  it("starts a backtest with the explicit configuration, then follows it from running to completed", async () => {
    api.createRun.mockResolvedValue(runSummary({ run_id: RUN_ID, status: "queued", result_status: null, total_return: null, number_of_trades: null }));
    api.getRun
      .mockResolvedValueOnce(runDetail({ run_id: RUN_ID, status: "running", result_status: null, summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0 }))
      .mockResolvedValue(runDetail({ run_id: RUN_ID, trade_count: 0 }));
    render();
    const user = userEvent.setup();
    const form = await screen.findByRole("form", { name: "Backtest configuration" });
    await user.click(within(form).getByRole("button", { name: "Pick Bitcoin" }));
    await user.click(within(form).getByRole("button", { name: "Run backtest" }));
    await waitFor(() => expect(api.createRun).toHaveBeenCalledTimes(1));
    expect(api.createRun.mock.calls[0][0]).toMatchObject({
      coin_ids: ["a".repeat(24)], starting_capital: 10000, fee_rate: 0.001, slippage_rate: 0.0005, sizing_mode: "fixed_fraction", position_size: 0.25,
    });
    expect(Object.keys(api.createRun.mock.calls[0][0])).not.toContain("user_id");
    const results = await screen.findByTestId("backtest-results");
    expect(await within(results).findByText("Backtest running...")).toBeInTheDocument();
    expect(await within(results).findByText("+12.50%", {}, { timeout: 6000 })).toBeInTheDocument();
    expect(within(results).queryByText("Backtest running...")).not.toBeInTheDocument();
  }, 15_000);

  it("shows the server's error when a backtest cannot be started", async () => {
    api.createRun.mockRejectedValue(new ApiError("You can have at most 2 backtests running at once.", 429, "BACKTEST_LIMIT"));
    render();
    const user = userEvent.setup();
    const form = await screen.findByRole("form", { name: "Backtest configuration" });
    await user.click(within(form).getByRole("button", { name: "Pick Bitcoin" }));
    await user.click(within(form).getByRole("button", { name: "Run backtest" }));
    expect(await within(form).findByRole("alert")).toBeInTheDocument();
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it("loads a past run from the list and shows its results, cost breakdown, chart and trades", async () => {
    api.listRuns.mockResolvedValue(paged([runSummary({ run_id: RUN_ID })]) as never);
    api.getRun.mockResolvedValue(runDetail({ run_id: RUN_ID }));
    api.runTrades.mockResolvedValue(paged([trade(), trade({ side: "SELL", price: 120.5, reason: "end_of_backtest" })], { total: 8 }) as never);
    render();
    await userEvent.setup().click(await screen.findByRole("button", { name: /BTC/ }));
    expect(api.getRun).toHaveBeenCalledWith(RUN_ID);
    const results = await screen.findByTestId("backtest-results");
    expect(await within(results).findByText("+12.50%")).toBeInTheDocument();
    expect(within(results).getByLabelText("Cost breakdown")).toHaveTextContent("$63.75");
    expect(within(results).getByTestId("strategy-line")).toHaveAttribute("data-points", "5");
    expect(await within(results).findByRole("table", { name: "Trade history" })).toBeInTheDocument();
    expect(api.runTrades).toHaveBeenCalledWith(RUN_ID, 1, 25);
  });

  it("polls a running backtest until it completes", async () => {
    api.listRuns.mockResolvedValue(paged([runSummary({ run_id: RUN_ID, status: "running", result_status: null, total_return: null })]) as never);
    api.getRun
      .mockResolvedValueOnce(runDetail({ run_id: RUN_ID, status: "running", result_status: null, summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0 }))
      .mockResolvedValue(runDetail({ run_id: RUN_ID, trade_count: 0 }));
    render();
    await userEvent.setup().click(await screen.findByRole("button", { name: /BTC/ }));
    expect(await screen.findByText("Backtest running...")).toBeInTheDocument();
    const results = await screen.findByTestId("backtest-results");
    expect(await within(results).findByText("+12.50%", {}, { timeout: 6000 })).toBeInTheDocument();
    expect(within(results).queryByText("Backtest running...")).not.toBeInTheDocument();
  }, 15_000);

  it("shows a failed run clearly", async () => {
    api.listRuns.mockResolvedValue(paged([runSummary({ run_id: RUN_ID, status: "failed", result_status: null, total_return: null, error: "Market data provider error: down" })]) as never);
    api.getRun.mockResolvedValue(runDetail({ run_id: RUN_ID, status: "failed", result_status: null, summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0, error: "Market data provider error: down" }));
    render();
    await userEvent.setup().click(await screen.findByRole("button", { name: /BTC/ }));
    expect(await screen.findByText(/Backtest failed: Market data provider error: down/)).toBeInTheDocument();
  });

  it("labels a completed run with no usable data as insufficient, not as a result", async () => {
    api.listRuns.mockResolvedValue(paged([runSummary({ run_id: RUN_ID, result_status: "insufficient_data", total_return: null })]) as never);
    api.getRun.mockResolvedValue(runDetail({ run_id: RUN_ID, result_status: "insufficient_data", summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0, reason: "No real historical candles were available for the selected coins and period." }));
    render();
    expect(await screen.findByText("Insufficient data")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /BTC/ }));
    expect(await screen.findByText(/No real historical candles were available/)).toBeInTheDocument();
  });

  it("shows an error when the run list cannot be loaded", async () => {
    api.listRuns.mockRejectedValueOnce(new ApiError("boom", 500));
    render();
    expect(await screen.findByText(/backtest runs could not be loaded|could not be loaded/i)).toBeInTheDocument();
  });
});
