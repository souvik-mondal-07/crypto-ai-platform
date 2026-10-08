import { describe, expect, it } from "vitest";

import { ApiError } from "../types/apiError";
import { describeDecisionError } from "./decisionErrors";

describe("describeDecisionError", () => {
  it("classifies failures with user-safe wording", () => {
    expect(describeDecisionError(new ApiError("Network Error")).kind).toBe("network");
    expect(describeDecisionError(new ApiError("timeout of 10000ms exceeded")).kind).toBe("timeout");
    expect(describeDecisionError(new ApiError("x", 429)).kind).toBe("rate_limited");
    expect(describeDecisionError(new ApiError("x", 503)).kind).toBe("unavailable");
    expect(describeDecisionError(new ApiError("x", 500)).message).toMatch(/could not be loaded/i);
    expect(describeDecisionError(new ApiError("x", 404, "COIN_NOT_FOUND")).message).toMatch(/not found/i);
    expect(describeDecisionError("weird").kind).toBe("unknown");
  });
});
