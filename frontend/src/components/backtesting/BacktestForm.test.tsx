import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { config } from "../../test-fixtures/backtesting";
import { BacktestForm } from "./BacktestForm";

// The real picker searches /coins/search; here a stub that "chooses" Bitcoin keeps the test about the form.
vi.mock("../common/CoinPicker", async () => {
  const { createElement } = await import("react");
  return {
    CoinPicker: ({ onSelect }: { onSelect: (coin: unknown) => void }) =>
      createElement("button", { type: "button", onClick: () => onSelect({ id: "a".repeat(24), name: "Bitcoin", symbol: "btc", logo_url: null }) }, "Pick Bitcoin"),
  };
});

const onSubmit = vi.fn();

function setup(props: { submitting?: boolean; submitError?: string | null } = {}) {
  render(<BacktestForm config={config()} submitting={props.submitting ?? false} submitError={props.submitError ?? null} onSubmit={onSubmit} />);
  return userEvent.setup();
}

beforeEach(() => onSubmit.mockClear());

describe("BacktestForm", () => {
  it("starts from the API's defaults (fees and slippage are not zero)", () => {
    setup();
    expect(screen.getByLabelText("Starting capital (USD)")).toHaveValue(10000);
    expect(screen.getByLabelText("Transaction fee (% per side)")).toHaveValue(0.1);
    expect(screen.getByLabelText("Slippage (% per fill)")).toHaveValue(0.05);
    expect(screen.getByLabelText("Position size (% of equity)")).toHaveValue(25);
    expect(screen.getByLabelText("Max allocation per asset (%)")).toHaveValue(50);
    expect(screen.getByLabelText("Benchmark")).toBeDisabled();
    expect(screen.getByLabelText("Bar interval")).toHaveValue("1h");
  });

  it("requires a coin before submitting", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose at least one coin.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the converted request (percentages -> fractions) and owner is never part of it", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Pick Bitcoin" }));
    expect(screen.getByRole("list", { name: "Selected coins" })).toHaveTextContent("Bitcoin");
    await user.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const request = onSubmit.mock.calls[0][0];
    expect(request).toMatchObject({
      coin_ids: ["a".repeat(24)], starting_capital: 10000, bar_interval: "1h", sizing_mode: "fixed_fraction", position_size: 0.25,
      max_allocation_pct: 0.5, fee_rate: 0.001, slippage_rate: 0.0005, close_open_positions_at_end: true,
    });
    expect(Object.keys(request)).not.toContain("user_id");
  });

  it("validates costs and sizing before calling the API", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Pick Bitcoin" }));
    const fee = screen.getByLabelText("Transaction fee (% per side)");
    await user.clear(fee);
    await user.type(fee, "-1");
    await user.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/fee/i);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("warns, but allows it, when both costs are explicitly zero", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Pick Bitcoin" }));
    for (const label of ["Transaction fee (% per side)", "Slippage (% per fill)"]) {
      const input = screen.getByLabelText(label);
      await user.clear(input);
      await user.type(input, "0");
    }
    expect(screen.getByText(/Fees and slippage are both set to 0%/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run backtest" }));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ fee_rate: 0, slippage_rate: 0 });
  });

  it("switches to a fixed USD amount", async () => {
    const user = setup();
    await user.selectOptions(screen.getByLabelText("Position sizing"), "fixed_amount");
    expect(screen.getByLabelText("Position size (USD)")).toBeInTheDocument();
  });

  it("removes a selected coin", async () => {
    const user = setup();
    await user.click(screen.getByRole("button", { name: "Pick Bitcoin" }));
    await user.click(screen.getByRole("button", { name: "Remove Bitcoin" }));
    expect(screen.queryByRole("list", { name: "Selected coins" })).not.toBeInTheDocument();
  });

  it("disables inputs while submitting and shows the server's error", () => {
    setup({ submitting: true, submitError: "You can have at most 2 backtests running at once." });
    expect(screen.getByRole("button", { name: "Starting backtest..." })).toBeDisabled();
    expect(screen.getByLabelText("Starting capital (USD)")).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("at most 2 backtests");
  });
});
