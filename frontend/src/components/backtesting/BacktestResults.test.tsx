import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { paged, runDetail, trade } from "../../test-fixtures/backtesting";
import type { BacktestRunDetail } from "../../types/backtesting";
import { BacktestResults } from "./BacktestResults";

function setup(detail: BacktestRunDetail | null, over: Partial<Parameters<typeof BacktestResults>[0]> = {}) {
  const handlers = { onRetry: vi.fn(), onTradesPage: vi.fn() };
  render(<BacktestResults detail={detail} loading={false} error={null} trades={null} tradesError={null} {...handlers} {...over} />);
  return handlers;
}

describe("BacktestResults", () => {
  it("shows an empty prompt before any run is selected", () => {
    setup(null);
    expect(screen.getByText(/Run a backtest or choose one/)).toBeInTheDocument();
  });

  it("shows loading and error states", async () => {
    const { rerender } = render(<BacktestResults detail={null} loading error={null} trades={null} tradesError={null} onRetry={vi.fn()} onTradesPage={vi.fn()} />);
    expect(screen.getByText("Loading backtest...")).toBeInTheDocument();
    const onRetry = vi.fn();
    rerender(<BacktestResults detail={null} loading={false} error="This backtest could not be loaded." trades={null} tradesError={null} onRetry={onRetry} onTradesPage={vi.fn()} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it.each([["queued", "Backtest queued..."], ["running", "Backtest running..."]] as const)("shows the %s state without any metrics", (status, text) => {
    setup(runDetail({ status, result_status: null, summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0, finished_at: null }));
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(screen.queryByLabelText("Backtest summary")).not.toBeInTheDocument();
    // the cost assumptions are part of EVERY report, even before it has finished
    expect(screen.getByLabelText("Cost and execution assumptions")).toBeInTheDocument();
  });

  it("shows a failed run with its reason and still shows the assumptions", () => {
    setup(runDetail({ status: "failed", result_status: null, summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0, error: "Market data provider error: unavailable" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Backtest failed: Market data provider error: unavailable");
    expect(screen.getByLabelText("Cost and execution assumptions")).toBeInTheDocument();
  });

  it("explains an insufficient-data run instead of presenting results", () => {
    setup(runDetail({ result_status: "insufficient_data", summary: null, equity_curve: [], benchmark_curve: [], trade_count: 0,
      reason: "No stored Phase 14 decisions exist for the selected coins in this period, so the strategy made no trades." }));
    expect(screen.getByText(/No stored Phase 14 decisions exist/)).toBeInTheDocument();
    expect(screen.queryByText("Total return")).not.toBeInTheDocument();
    expect(screen.queryByTestId("equity-chart")).not.toBeInTheDocument();
  });

  it("shows every headline metric from the API, with N/A for what could not be computed", () => {
    setup(runDetail());
    const summary = within(screen.getByLabelText("Backtest summary"));
    expect(summary.getByText("+12.50%")).toBeInTheDocument();            // total return
    expect(summary.getByText("$10,000.00 → $11,250.00")).toBeInTheDocument();
    expect(summary.getByText("+8.00%")).toBeInTheDocument();             // benchmark
    expect(summary.getByText("-8.00%")).toBeInTheDocument();             // max drawdown, shown as a loss
    expect(summary.getByText("75.0%")).toBeInTheDocument();              // win rate
    expect(summary.getByText("+6.00%")).toBeInTheDocument();             // average win
    expect(summary.getByText("-2.00%")).toBeInTheDocument();             // average loss
    const annualised = summary.getByText("Annualized return").closest("div") as HTMLElement;
    expect(within(annualised).getByText("N/A")).toBeInTheDocument();
    expect(within(annualised).getByText("Needs a period of at least 30 days")).toBeInTheDocument();
    const sharpe = summary.getByText("Sharpe ratio").closest("div") as HTMLElement;
    expect(within(sharpe).getByText("N/A")).toBeInTheDocument();
    expect(within(sharpe).getByText(/Needs at least 30 return observations/)).toBeInTheDocument();
  });

  it("shows the cost breakdown and the assumptions used", () => {
    setup(runDetail());
    const costs = within(screen.getByLabelText("Cost breakdown"));
    expect(costs.getByText("$42.50")).toBeInTheDocument();
    expect(costs.getByText("$21.25")).toBeInTheDocument();
    expect(costs.getByText("$63.75")).toBeInTheDocument();
    const assumptions = within(screen.getByLabelText("Cost and execution assumptions"));
    expect(assumptions.getByText("0.100% per side")).toBeInTheDocument();
    expect(assumptions.getByText("0.050% per fill (adverse)")).toBeInTheDocument();
    expect(assumptions.getByText("25.0% of equity")).toBeInTheDocument();
    expect(assumptions.getByText("50.0%")).toBeInTheDocument();
    expect(assumptions.getByText("Next bar open")).toBeInTheDocument();
    expect(assumptions.getByText("Long only, no leverage")).toBeInTheDocument();
  });

  it("renders the equity curve from the API's points", () => {
    setup(runDetail());
    expect(screen.getByTestId("strategy-line")).toHaveAttribute("data-points", "5");
    expect(screen.getByTestId("benchmark-line")).toHaveAttribute("data-points", "5");
  });

  it("shows warnings, per-coin data and the disclaimer", () => {
    setup(runDetail());
    expect(screen.getByText(/Only 4 closed trade\(s\)/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Data used" })).toHaveTextContent("BTC: 720 bars, 9 stored decisions");
    expect(screen.getByText("Simulated results on historical data.")).toBeInTheDocument();
  });

  it("lists trades from the API and pages through them", async () => {
    const buy = trade();
    const sell = trade({ side: "SELL", price: 120.5, reason: "end_of_backtest", execution_time: "2026-08-20T00:00:00Z" });
    const { onTradesPage } = setup(runDetail({ trade_count: 60 }), { trades: paged([buy, sell], { total: 60, limit: 25 }) });
    const table = within(screen.getByRole("table", { name: "Trade history" }));
    expect(table.getAllByRole("row")).toHaveLength(3);                    // header + 2 trades
    expect(table.getByText("$100.05")).toBeInTheDocument();
    expect(table.getByText("Closed at end of period")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: /next/i }));
    expect(onTradesPage).toHaveBeenCalledWith(2);
  });

  it("shows trade loading and trade errors separately from the summary", () => {
    setup(runDetail(), { trades: null, tradesError: "Trades could not be loaded." });
    expect(screen.getByText("Trades could not be loaded.")).toBeInTheDocument();
    expect(screen.getByTestId("equity-chart")).toBeInTheDocument();
  });

  it("omits the trade section when a run made no trades", () => {
    setup(runDetail({ trade_count: 0 }));
    expect(screen.queryByRole("table", { name: "Trade history" })).not.toBeInTheDocument();
  });
});
