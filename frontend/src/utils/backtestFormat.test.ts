import { describe, expect, it } from "vitest";

import { NOT_AVAILABLE, formatDay, formatNumber, formatPeriod, formatPoints, fractionToPercent, modelVersionKey, modelVersionLabel, returnClass } from "./backtestFormat";

describe("backtest formatting", () => {
  it("renders null/undefined/NaN as N/A, never as zero", () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(fractionToPercent(value)).toBe(NOT_AVAILABLE);
      expect(formatPoints(value)).toBe(NOT_AVAILABLE);
      expect(formatNumber(value)).toBe(NOT_AVAILABLE);
    }
    expect(fractionToPercent(0)).toBe("0.00%");   // a real measured zero is still shown
  });

  it("converts fractions to percentages with optional sign", () => {
    expect(fractionToPercent(0.125, 1)).toBe("12.5%");
    expect(fractionToPercent(0.125, 2, true)).toBe("+12.50%");
    expect(fractionToPercent(-0.02, 2, true)).toBe("-2.00%");
    expect(formatPoints(0.008)).toBe("0.800 pp");
  });

  it("formats dates in UTC and periods", () => {
    expect(formatDay("2026-08-01T00:00:00Z")).toBe("Aug 1, 2026");
    expect(formatDay("garbage")).toBe(NOT_AVAILABLE);
    expect(formatPeriod("2026-08-01T00:00:00Z", "2026-08-31T00:00:00Z")).toBe("Aug 1, 2026 – Aug 31, 2026");
    expect(formatPeriod(null, "2026-08-31T00:00:00Z")).toBe(NOT_AVAILABLE);
  });

  it("builds stable model/version keys and labels", () => {
    expect(modelVersionKey("xgboost", "3")).toBe("xgboost|3");
    expect(modelVersionKey(null, "3")).toBe("");
    expect(modelVersionLabel("xgboost", "3")).toBe("xgboost v3");
    expect(modelVersionLabel("xgboost", null)).toBe("xgboost");
  });

  it("colours only real gains and losses", () => {
    expect(returnClass(0.1)).toContain("emerald");
    expect(returnClass(-0.1)).toContain("red");
    expect(returnClass(0)).not.toContain("emerald");
    expect(returnClass(null)).not.toContain("red");
  });
});
