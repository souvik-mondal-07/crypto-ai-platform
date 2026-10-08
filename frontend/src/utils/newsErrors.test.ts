import { describe, expect, it } from "vitest";

import { ApiError } from "../types/apiError";
import { describeNewsError, describeSyncError } from "./newsErrors";

describe("describeNewsError", () => {
  it.each([
    [new ApiError("x", 429), "rate_limited", /rate limited/i],
    [new ApiError("x", 503), "unavailable", /temporarily unavailable/i],
    [new ApiError("x", 500), "server", /could not be loaded/i],
    [new ApiError("Network Error"), "network", /unable to reach/i],
    [new ApiError("timeout of 10000ms exceeded"), "timeout", /too long/i],
  ])("classifies %#", (error, kind, message) => {
    const result = describeNewsError(error);
    expect(result.kind).toBe(kind);
    expect(result.message).toMatch(message);
  });

  it("explains an unknown coin and keeps backend validation messages", () => {
    expect(describeNewsError(new ApiError("No coin", 404, "COIN_NOT_FOUND")).message).toMatch(/not found/i);
    expect(describeNewsError(new ApiError("date_from must not be after date_to.", 400)).message).toBe(
      "date_from must not be after date_to."
    );
  });

  it("never leaks raw errors for non-API failures", () => {
    expect(describeNewsError(undefined).message).toMatch(/could not be loaded/i);
  });
});

describe("describeSyncError", () => {
  it("is silent without an error and plain-language with one", () => {
    expect(describeSyncError(null)).toBeNull();
    expect(describeSyncError("PROVIDER_RATE_LIMITED")).toMatch(/rate-limited/);
    expect(describeSyncError("SOMETHING_NEW")).toMatch(/failed/);
  });
});
