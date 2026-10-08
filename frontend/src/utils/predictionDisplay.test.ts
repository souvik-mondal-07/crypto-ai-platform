import { describe, expect, it } from "vitest";

import { buildPredictionList, buildUnavailable } from "../test-fixtures/predictions";
import { ApiError } from "../types/apiError";
import { chooseHorizon, describeUnavailable, markerPosition, modelDisplayName } from "./predictionDisplay";
import { describePredictionError } from "./predictionErrors";

describe("chooseHorizon", () => {
  it("keeps a still-available selection, else 24h, else the first available, else null", () => {
    expect(chooseHorizon("4h", ["4h", "24h"])).toBe("4h");
    expect(chooseHorizon("7d", ["4h", "24h"])).toBe("24h");
    expect(chooseHorizon(null, ["1h", "7d"])).toBe("1h");
    expect(chooseHorizon(null, [])).toBeNull();
  });
});

describe("markerPosition", () => {
  it("places the current price within the displayed span", () => {
    expect(markerPosition(100, 101, 104)).toBe(0);
    expect(markerPosition(102.5, 101, 104)).toBeCloseTo(50);
    expect(markerPosition(110, 101, 104)).toBe(100);
    expect(markerPosition(5, 5, 5)).toBe(50);
  });
});

describe("describeUnavailable", () => {
  it("prefers insufficient data over a missing model", () => {
    const d = describeUnavailable(buildPredictionList([], [buildUnavailable("1h", "model_unavailable"), buildUnavailable("24h", "insufficient_data", "too short")]));
    expect(d).toEqual({ title: "Insufficient historical data", reason: "too short" });
  });
  it("explains a missing model, and an empty response", () => {
    expect(describeUnavailable(buildPredictionList([], [buildUnavailable("1h", "model_unavailable")])).title).toBe("Prediction unavailable");
    expect(describeUnavailable(buildPredictionList([], [])).reason).toMatch(/no prediction could be produced/i);
  });
});

describe("modelDisplayName", () => {
  it("names known models and passes unknown ones through", () => {
    expect(modelDisplayName("lightgbm")).toBe("LightGBM");
    expect(modelDisplayName("ensemble")).toBe("Ensemble");
    expect(modelDisplayName("custom")).toBe("custom");
  });
});

describe("describePredictionError", () => {
  it.each([
    [new ApiError("x", 429), "rate_limited", /rate limited/i],
    [new ApiError("x", 503), "unavailable", /temporarily unavailable/i],
    [new ApiError("x", 503, "PREDICTION_ENGINE_UNAVAILABLE"), "engine_unavailable", /engine is not available/i],
    [new ApiError("x", 500), "server", /could not be loaded/i],
    [new ApiError("Network Error"), "network", /unable to reach/i],
    [new ApiError("timeout of 10000ms exceeded"), "timeout", /too long/i],
    [new ApiError("No coin", 404, "COIN_NOT_FOUND"), "not_found", /not found/i],
    [new ApiError("horizon must be one of", 400, "INVALID_HORIZON"), "invalid", /horizon must be/i],
  ])("classifies %#", (error, kind, message) => {
    const r = describePredictionError(error);
    expect(r.kind).toBe(kind);
    expect(r.message).toMatch(message);
  });
  it("never leaks a raw error object", () => {
    expect(describePredictionError({ weird: true }).message).toMatch(/could not be loaded/i);
  });
});
