import { describe, expect, it } from "vitest";

import { ApiError } from "./apiError";

describe("ApiError", () => {
  it("is still an Error with the same message, so existing handlers are unaffected", () => {
    const error = new ApiError("Something failed.", 503, "DATABASE_UNAVAILABLE");
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe("Something failed.");
    expect(error.name).toBe("ApiError");
  });

  it("carries the HTTP status and backend error code", () => {
    const error = new ApiError("x", 404, "FUNDAMENTALS_NOT_AVAILABLE");
    expect(error.status).toBe(404);
    expect(error.code).toBe("FUNDAMENTALS_NOT_AVAILABLE");
  });

  it("allows status and code to be absent (e.g. a network failure)", () => {
    const error = new ApiError("Network down.");
    expect(error.status).toBeUndefined();
    expect(error.code).toBeUndefined();
  });
});
