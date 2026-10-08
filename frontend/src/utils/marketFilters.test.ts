import { describe, expect, it } from "vitest";

import {
  CAP_PRESETS,
  CHANGE_PRESETS,
  DEFAULT_SELECTION,
  MARKET_TABS,
  VOLUME_PRESETS,
  activeFilterCount,
  isMarketTabKey,
  parseCap,
  selectionToFilters,
} from "./marketFilters";

describe("selectionToFilters", () => {
  it("sends nothing for the default selection", () => {
    expect(selectionToFilters(DEFAULT_SELECTION)).toEqual({});
  });

  it("maps market cap, change, volume and supply presets to exact backend bounds", () => {
    expect(selectionToFilters({ cap: "1b-10b", change: "5to10", volume: "100m-1b", supply: "capped" })).toEqual({
      marketCapMin: 1e9,
      marketCapMax: 1e10,
      changeMin: 5,
      changeMax: 10,
      volumeMin: 1e8,
      volumeMax: 1e9,
      hasMaxSupply: true,
    });
  });

  it("uses open-ended bounds for '>' and '<' presets", () => {
    expect(selectionToFilters({ ...DEFAULT_SELECTION, cap: "gt100b" })).toEqual({ marketCapMin: 1e11 });
    expect(selectionToFilters({ ...DEFAULT_SELECTION, change: "ltN10" })).toEqual({ changeMax: -10 });
    expect(selectionToFilters({ ...DEFAULT_SELECTION, volume: "lt10m" })).toEqual({ volumeMax: 1e7 });
  });

  it("distinguishes 'no reported maximum supply' from 'any'", () => {
    expect(selectionToFilters({ ...DEFAULT_SELECTION, supply: "uncapped" })).toEqual({ hasMaxSupply: false });
  });

  it("never produces an inverted range for any preset", () => {
    for (const preset of [...CAP_PRESETS, ...CHANGE_PRESETS, ...VOLUME_PRESETS]) {
      if (preset.min !== undefined && preset.max !== undefined) {
        expect(preset.min).toBeLessThanOrEqual(preset.max);
      }
    }
  });
});

describe("helpers", () => {
  it("counts only non-default filters", () => {
    expect(activeFilterCount(DEFAULT_SELECTION)).toBe(0);
    expect(activeFilterCount({ ...DEFAULT_SELECTION, cap: "lt1b", supply: "capped" })).toBe(2);
  });

  it("rejects unknown tab / preset values from the URL", () => {
    expect(isMarketTabKey("gainers")).toBe(true);
    expect(isMarketTabKey("hacked")).toBe(false);
    expect(isMarketTabKey(null)).toBe(false);
    expect(parseCap("gt10b")).toBe("gt10b");
    expect(parseCap("nonsense")).toBe("any");
  });

  it("only defines tabs whose sort field the backend supports", () => {
    const supported = ["market_cap", "price", "change_24h", "change_7d", "volume", "fdv", "supply", "volatility"];
    for (const tab of MARKET_TABS) expect(supported).toContain(tab.sortBy);
  });
});
