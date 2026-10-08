import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchFundamentals } from "./fundamentals.api";
import { apiClient } from "./client";
import { buildFundamentals } from "../../test-fixtures/fundamentals";

vi.mock("./client", () => ({ apiClient: { get: vi.fn() } }));
const mockedGet = vi.mocked(apiClient.get);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("fetchFundamentals", () => {
  it("requests the coin's fundamentals endpoint and returns the body", async () => {
    const body = buildFundamentals();
    mockedGet.mockResolvedValue({ data: body });

    await expect(fetchFundamentals("abc123")).resolves.toEqual(body);
    expect(mockedGet).toHaveBeenCalledWith(
      "/coins/abc123/fundamentals",
      expect.objectContaining({ params: undefined })
    );
  });

  it("sends force_refresh only when requested", async () => {
    mockedGet.mockResolvedValue({ data: buildFundamentals() });
    await fetchFundamentals("abc123", { forceRefresh: true });
    expect(mockedGet).toHaveBeenCalledWith(
      "/coins/abc123/fundamentals",
      expect.objectContaining({ params: { force_refresh: true } })
    );
  });

  it("passes the abort signal through", async () => {
    mockedGet.mockResolvedValue({ data: buildFundamentals() });
    const controller = new AbortController();
    await fetchFundamentals("abc123", { signal: controller.signal });
    expect(mockedGet).toHaveBeenCalledWith(
      "/coins/abc123/fundamentals",
      expect.objectContaining({ signal: controller.signal })
    );
  });

  it("propagates request failures unchanged", async () => {
    mockedGet.mockRejectedValue(new Error("Service unavailable."));
    await expect(fetchFundamentals("abc123")).rejects.toThrow("Service unavailable.");
  });
});
