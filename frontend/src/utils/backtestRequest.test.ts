import { describe, expect, it } from "vitest";

import { config } from "../test-fixtures/backtesting";
import { buildBacktestRequest } from "./backtestRequest";

const BTC = { id: "a".repeat(24), name: "Bitcoin", symbol: "btc", logo_url: null };
const TODAY = new Date("2026-10-15T12:00:00Z");
const base = {
  coins: [BTC], start: "2026-08-01", end: "2026-09-01", capital: "10000", interval: "1h" as const, sizingMode: "fixed_fraction" as const,
  positionSize: "25", maxAllocationPct: "50", feePct: "0.1", slippagePct: "0.05", closeAtEnd: true,
};
const build = (over: Partial<typeof base> = {}) => buildBacktestRequest({ ...base, ...over }, config(), TODAY);

describe("buildBacktestRequest", () => {
  it("converts percentages to fractions and dates to UTC midnight", () => {
    const result = build();
    expect(result).toEqual({
      request: {
        coin_ids: [BTC.id], start: "2026-08-01T00:00:00.000Z", end: "2026-09-01T00:00:00.000Z", starting_capital: 10000, bar_interval: "1h",
        sizing_mode: "fixed_fraction", position_size: 0.25, max_allocation_pct: 0.5, fee_rate: 0.001, slippage_rate: 0.0005, close_open_positions_at_end: true,
      },
    });
  });

  it("allows explicit zero costs (the caller is warned in the UI)", () => {
    const result = build({ feePct: "0", slippagePct: "0" });
    expect("request" in result && result.request.fee_rate === 0 && result.request.slippage_rate === 0).toBe(true);
  });

  it.each([
    [{ coins: [] }, /at least one coin/i],
    [{ start: "", end: "2026-09-01" }, /valid start and end/i],
    [{ start: "2026-09-02", end: "2026-09-01" }, /before the end/i],
    [{ end: "2026-11-01" }, /future/i],
    [{ start: "2024-01-01", end: "2026-01-01" }, /cannot exceed 365/i],
    [{ start: "2026-01-01", end: "2026-09-01", interval: "1h" as const }, /bars per coin/i],
    [{ capital: "0" }, /capital must be greater than 0/i],
    [{ capital: "abc" }, /capital must be greater than 0/i],
    [{ positionSize: "0" }, /position size must be greater than 0/i],
    [{ positionSize: "150" }, /cannot exceed 100%/i],
    [{ sizingMode: "fixed_amount" as const, positionSize: "20000" }, /cannot exceed the starting capital/i],
    [{ maxAllocationPct: "0" }, /maximum allocation/i],
    [{ maxAllocationPct: "101" }, /maximum allocation/i],
    [{ feePct: "-0.1" }, /fee/i],
    [{ feePct: "10" }, /fee/i],
    [{ slippagePct: "-1" }, /slippage/i],
  ])("rejects invalid input %#", (over, message) => {
    const result = build(over);
    expect("error" in result).toBe(true);
    if ("error" in result) expect(result.error).toMatch(message);
  });

  it("rejects too many coins", () => {
    const many = Array.from({ length: 11 }, (_, i) => ({ ...BTC, id: String(i).padStart(24, "0") }));
    const result = build({ coins: many });
    expect("error" in result && /at most 10/i.test(result.error)).toBe(true);
  });
});
