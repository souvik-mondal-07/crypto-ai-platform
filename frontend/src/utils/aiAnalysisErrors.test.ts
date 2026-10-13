import { describe, expect, it } from "vitest";

import { ApiError } from "../types/apiError";
import { AI_UNAVAILABLE_MESSAGE, describeAiError, isNoAnalysisYet } from "./aiAnalysisErrors";

describe("describeAiError", () => {
  it.each(["AI_NOT_CONFIGURED", "AI_AUTH_FAILED", "AI_UNAVAILABLE", "AI_INVALID_RESPONSE"])("treats %s as unavailable", (code) => {
    expect(describeAiError(new ApiError("internal detail", 503, code))).toEqual({ kind: "unavailable", message: AI_UNAVAILABLE_MESSAGE });
  });

  it("never passes provider/internal text through for unavailable errors", () => {
    expect(describeAiError(new ApiError("API key sk-123 rejected", 503, "AI_AUTH_FAILED")).message).not.toMatch(/sk-123|key/i);
  });

  it("maps rate limits, cooldown, timeout and insufficient data", () => {
    expect(describeAiError(new ApiError("x", 429, "AI_RATE_LIMITED")).kind).toBe("rate_limited");
    expect(describeAiError(new ApiError("Try again in about 20 seconds.", 429, "AI_ANALYSIS_COOLDOWN"))).toEqual({
      kind: "cooldown",
      message: "Try again in about 20 seconds.",
    });
    expect(describeAiError(new ApiError("x", 504, "AI_TIMEOUT")).kind).toBe("timeout");
    expect(describeAiError(new ApiError("Unavailable: technical.", 422, "AI_INSUFFICIENT_DATA"))).toEqual({
      kind: "insufficient_data",
      message: "Unavailable: technical.",
    });
  });

  it("maps network failures and plain server errors", () => {
    expect(describeAiError(new ApiError("Network Error")).kind).toBe("network");
    expect(describeAiError(new ApiError("timeout of 60000ms exceeded")).kind).toBe("timeout");
    expect(describeAiError(new ApiError("boom", 500, "INTERNAL_ERROR")).kind).toBe("server");
    expect(describeAiError(new ApiError("nf", 404, "COIN_NOT_FOUND")).kind).toBe("not_found");
    expect(describeAiError("weird").kind).toBe("unknown");
  });

  it("recognises 'nothing generated yet' as a non-failure", () => {
    expect(isNoAnalysisYet(new ApiError("none", 404, "AI_ANALYSIS_NOT_FOUND"))).toBe(true);
    expect(isNoAnalysisYet(new ApiError("none", 404, "COIN_NOT_FOUND"))).toBe(false);
    expect(isNoAnalysisYet(new Error("x"))).toBe(false);
  });
});
