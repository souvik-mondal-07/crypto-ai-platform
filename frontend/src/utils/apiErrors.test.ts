import { describe, expect, it } from "vitest";

import { ApiError } from "../types/apiError";
import { classifyError } from "./apiErrors";

describe("classifyError", () => {
  it("separates a network failure (no response) from API errors", () => {
    const result = classifyError(new ApiError("Network Error"));
    expect(result.kind).toBe("network");
    expect(result.message).toMatch(/unable to reach the server/i);
  });

  it("recognises timeouts", () => {
    expect(classifyError(new ApiError("timeout of 10000ms exceeded")).kind).toBe("timeout");
  });

  it("maps 429 to the provider rate-limit message", () => {
    const result = classifyError(new ApiError("anything", 429));
    expect(result.kind).toBe("rate_limited");
    expect(result.message).toBe("Market data provider is temporarily rate limited. Please try again shortly.");
  });

  it("maps 500 to a clean retry message and never leaks server text", () => {
    const result = classifyError(new ApiError("Traceback: File app.py line 1", 500));
    expect(result.kind).toBe("server");
    expect(result.message).toBe("Market data could not be loaded. Please retry.");
  });

  it("treats 503/504 as provider unavailable", () => {
    expect(classifyError(new ApiError("x", 503)).kind).toBe("unavailable");
    expect(classifyError(new ApiError("x", 504)).kind).toBe("unavailable");
  });

  it("keeps the backend's own message for 4xx errors", () => {
    expect(classifyError(new ApiError("Coin not found", 404)).message).toBe("Coin not found");
  });

  it("keeps plain Error messages and falls back for unknown values", () => {
    expect(classifyError(new Error("overview down")).message).toBe("overview down");
    expect(classifyError("weird", "fallback text").message).toBe("fallback text");
  });
});
