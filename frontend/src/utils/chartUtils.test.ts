import { describe, expect, it } from "vitest";

import { periodChangePercent, toCandlestickData, toCloseLineData } from "./chartUtils";
import type { HistoricalCandle } from "../types/market";

function candle(timestamp: string, overrides: Partial<HistoricalCandle> = {}): HistoricalCandle {
  return { timestamp, open: 100, high: 110, low: 95, close: 105, volume: null, ...overrides };
}

describe("toCandlestickData", () => {
  it("converts an ISO timestamp to a UTC second-precision time", () => {
    const result = toCandlestickData([candle("2026-01-01T00:00:00Z")]);
    expect(result).toHaveLength(1);
    // 2026-01-01T00:00:00Z in seconds
    expect(result[0].time).toBe(Math.floor(Date.parse("2026-01-01T00:00:00Z") / 1000));
  });

  it("preserves OHLC values exactly", () => {
    const result = toCandlestickData([
      candle("2026-01-01T00:00:00Z", { open: 1.5, high: 2.5, low: 1.0, close: 2.0 }),
    ]);
    expect(result[0]).toMatchObject({ open: 1.5, high: 2.5, low: 1.0, close: 2.0 });
  });

  it("drops candles with an unparseable timestamp rather than emitting NaN time", () => {
    const result = toCandlestickData([candle("not-a-date"), candle("2026-01-01T00:00:00Z")]);
    expect(result).toHaveLength(1);
    expect(Number.isNaN(result[0].time as number)).toBe(false);
  });

  it("drops duplicate timestamps, which the chart library rejects", () => {
    const result = toCandlestickData([
      candle("2026-01-01T00:00:00Z"),
      candle("2026-01-01T00:00:00Z"),
    ]);
    expect(result).toHaveLength(1);
  });

  it("drops out-of-order candles so times stay strictly ascending", () => {
    const result = toCandlestickData([
      candle("2026-01-02T00:00:00Z"),
      candle("2026-01-01T00:00:00Z"),
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].time).toBe(Math.floor(Date.parse("2026-01-02T00:00:00Z") / 1000));
  });

  it("returns an empty array for empty input", () => {
    expect(toCandlestickData([])).toEqual([]);
  });
});


describe("toCloseLineData", () => {
  it("maps real candles to close-price points and drops unparseable timestamps", () => {
    const points = toCloseLineData([
      candle("2026-01-01T00:00:00Z", { close: 101 }),
      candle("not-a-date", { close: 999 }),
      candle("2026-01-02T00:00:00Z", { close: 103 }),
    ]);
    expect(points.map((p) => p.value)).toEqual([101, 103]);
  });

  it("returns an empty series for no candles", () => {
    expect(toCloseLineData([])).toEqual([]);
  });
});

describe("periodChangePercent", () => {
  it("measures first open to last close", () => {
    const change = periodChangePercent([
      candle("2026-01-01T00:00:00Z", { open: 100, close: 102 }),
      candle("2026-01-02T00:00:00Z", { open: 102, close: 110 }),
    ]);
    expect(change).toBeCloseTo(10, 6);
  });

  it("is null (not 0) when there is nothing to measure", () => {
    expect(periodChangePercent([])).toBeNull();
    expect(periodChangePercent([candle("2026-01-01T00:00:00Z", { open: 0, close: 5 })])).toBeNull();
  });
});
