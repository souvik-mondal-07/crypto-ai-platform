import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import { useFundamentals } from "./useFundamentals";
import * as fundamentalsApi from "../services/api/fundamentals.api";
import { ApiError } from "../types/apiError";
import { buildFundamentals } from "../test-fixtures/fundamentals";

vi.mock("../services/api/fundamentals.api", () => ({ fetchFundamentals: vi.fn() }));
const mockedApi = vi.mocked(fundamentalsApi);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useFundamentals", () => {
  it("starts loading, then exposes the data", async () => {
    mockedApi.fetchFundamentals.mockResolvedValue(buildFundamentals());
    const { result } = renderHook(() => useFundamentals("coin-a"));

    expect(result.current.loading).toBe(true);
    expect(result.current.fundamentals).toBeNull();

    await waitFor(() => expect(result.current.fundamentals).not.toBeNull());
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockedApi.fetchFundamentals).toHaveBeenCalledWith("coin-a", expect.objectContaining({ forceRefresh: false }));
  });

  it("does not fetch until a coin id is available", () => {
    renderHook(() => useFundamentals(undefined));
    expect(mockedApi.fetchFundamentals).not.toHaveBeenCalled();
  });

  it("ends in an error state (never an endless loading state) when the request fails", async () => {
    mockedApi.fetchFundamentals.mockRejectedValue(new Error("Provider unavailable."));
    const { result } = renderHook(() => useFundamentals("coin-a"));

    await waitFor(() => expect(result.current.error).toBe("Provider unavailable."));
    expect(result.current.loading).toBe(false);
    expect(result.current.notAvailable).toBe(false);
    expect(result.current.fundamentals).toBeNull();
  });

  it("distinguishes 'no data exists' from a failed request using the backend error code", async () => {
    mockedApi.fetchFundamentals.mockRejectedValue(
      new ApiError("No fundamental data is available.", 404, "FUNDAMENTALS_NOT_AVAILABLE")
    );
    const { result } = renderHook(() => useFundamentals("coin-a"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.notAvailable).toBe(true);
  });

  it("treats other API errors (even 404s) as failures, not as 'no data'", async () => {
    mockedApi.fetchFundamentals.mockRejectedValue(new ApiError("No coin found.", 404, "COIN_NOT_FOUND"));
    const { result } = renderHook(() => useFundamentals("coin-a"));

    await waitFor(() => expect(result.current.error).toBe("No coin found."));
    expect(result.current.notAvailable).toBe(false);
  });

  it("refetch retries after a failure", async () => {
    mockedApi.fetchFundamentals.mockRejectedValueOnce(new Error("boom"));
    mockedApi.fetchFundamentals.mockResolvedValueOnce(buildFundamentals());
    const { result } = renderHook(() => useFundamentals("coin-a"));
    await waitFor(() => expect(result.current.error).toBe("boom"));

    await act(async () => {
      result.current.refetch();
    });

    await waitFor(() => expect(result.current.fundamentals).not.toBeNull());
    expect(result.current.error).toBeNull();
  });

  it("refresh asks the backend to force a provider refresh and keeps data visible meanwhile", async () => {
    mockedApi.fetchFundamentals.mockResolvedValueOnce(buildFundamentals());
    const { result } = renderHook(() => useFundamentals("coin-a"));
    await waitFor(() => expect(result.current.fundamentals).not.toBeNull());

    let release: (v: ReturnType<typeof buildFundamentals>) => void = () => {};
    mockedApi.fetchFundamentals.mockReturnValueOnce(new Promise((resolve) => { release = resolve; }));
    act(() => {
      result.current.refresh();
    });

    await waitFor(() => expect(result.current.refreshing).toBe(true));
    expect(result.current.fundamentals).not.toBeNull(); // not blanked
    expect(result.current.loading).toBe(false);
    expect(mockedApi.fetchFundamentals).toHaveBeenLastCalledWith("coin-a", expect.objectContaining({ forceRefresh: true }));

    await act(async () => {
      release(buildFundamentals({ name: "Refreshed" }));
    });
    await waitFor(() => expect(result.current.refreshing).toBe(false));
    expect(result.current.fundamentals?.name).toBe("Refreshed");
  });

  it("keeps existing data and reports the error when a refresh fails", async () => {
    mockedApi.fetchFundamentals.mockResolvedValueOnce(buildFundamentals());
    const { result } = renderHook(() => useFundamentals("coin-a"));
    await waitFor(() => expect(result.current.fundamentals).not.toBeNull());

    mockedApi.fetchFundamentals.mockRejectedValueOnce(new Error("refresh failed"));
    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(result.current.error).toBe("refresh failed"));
    expect(result.current.fundamentals).not.toBeNull();
  });

  it("never exposes the previous coin's data after the coin changes", async () => {
    mockedApi.fetchFundamentals.mockResolvedValueOnce(buildFundamentals({ name: "Coin A" }));
    const { result, rerender } = renderHook(({ id }) => useFundamentals(id), { initialProps: { id: "coin-a" } });
    await waitFor(() => expect(result.current.fundamentals?.name).toBe("Coin A"));

    mockedApi.fetchFundamentals.mockReturnValueOnce(new Promise(() => {})); // coin B never resolves
    rerender({ id: "coin-b" });

    expect(result.current.fundamentals).toBeNull();
    await waitFor(() => expect(result.current.loading).toBe(true));
  });

  it("ignores a late response for a coin that is no longer displayed", async () => {
    let resolveA: (v: ReturnType<typeof buildFundamentals>) => void = () => {};
    mockedApi.fetchFundamentals.mockReturnValueOnce(new Promise((resolve) => { resolveA = resolve; }));
    const { result, rerender } = renderHook(({ id }) => useFundamentals(id), { initialProps: { id: "coin-a" } });

    mockedApi.fetchFundamentals.mockResolvedValueOnce(buildFundamentals({ name: "Coin B" }));
    rerender({ id: "coin-b" });
    await waitFor(() => expect(result.current.fundamentals?.name).toBe("Coin B"));

    await act(async () => {
      resolveA(buildFundamentals({ name: "Coin A (late)" }));
    });
    expect(result.current.fundamentals?.name).toBe("Coin B");
  });
});
