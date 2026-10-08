import { describe, expect, it, beforeEach, vi } from "vitest";

import { apiClient } from "./client";
import { setToken, removeToken } from "../../utils/authStorage";
import { ApiError } from "../../types/apiError";

describe("apiClient auth interceptor", () => {
  beforeEach(() => {
    removeToken();
  });

  it("attaches Authorization: Bearer <token> when a token is stored", async () => {
    setToken("my-test-token");

    const config = await apiClient.interceptors.request.handlers?.[0]?.fulfilled?.({
      headers: {},
    } as never);

    expect((config as { headers: Record<string, string> }).headers.Authorization).toBe(
      "Bearer my-test-token"
    );
  });

  it("does not attach an Authorization header when no token is stored", async () => {
    const config = await apiClient.interceptors.request.handlers?.[0]?.fulfilled?.({
      headers: {},
    } as never);

    expect((config as { headers: Record<string, string> }).headers.Authorization).toBeUndefined();
  });
});

describe("apiClient error normalization", () => {
  async function rejectWith(error: unknown) {
    const handler = apiClient.interceptors.response.handlers?.[0]?.rejected;
    return handler?.(error as never);
  }

  it("rejects with an ApiError carrying the backend's message, status and code", async () => {
    const failure = rejectWith({
      config: { url: "/coins/abc/fundamentals" },
      message: "Request failed with status code 404",
      response: {
        status: 404,
        statusText: "Not Found",
        data: { error: { code: "FUNDAMENTALS_NOT_AVAILABLE", message: "No fundamental data is available." } },
      },
    });

    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      message: "No fundamental data is available.",
      status: 404,
      code: "FUNDAMENTALS_NOT_AVAILABLE",
    });
  });

  it("is still a plain Error for callers that only read .message", async () => {
    const failure = rejectWith({ config: { url: "/x" }, message: "Network Error" });
    await expect(failure).rejects.toThrow("Network Error");
    await expect(failure).rejects.toBeInstanceOf(Error);
  });

  it("leaves status and code undefined when there was no HTTP response", async () => {
    const failure = rejectWith({ config: { url: "/x" }, message: "Network Error" });
    await expect(failure).rejects.toMatchObject({ status: undefined, code: undefined });
  });
});
