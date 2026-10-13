import { beforeEach, describe, expect, it, vi } from "vitest";

import { watchlistApi } from "../services/api/watchlist.api";
import { ApiError } from "../types/apiError";
import { useWatchlistStore } from "./watchlistStore";

vi.mock("../services/api/watchlist.api", () => ({
  watchlistApi: { list: vi.fn(), add: vi.fn(), remove: vi.fn(), status: vi.fn() },
}));
const api = vi.mocked(watchlistApi);

const page = (ids: string[]) => ({
  items: ids.map((coin_id) => ({ coin_id })),
  total: ids.length, page: 1, limit: 250, pages: 1,
}) as never;

beforeEach(() => {
  vi.clearAllMocks();
  useWatchlistStore.getState().reset();
});

describe("watchlistStore", () => {
  it("loads the server's ids and reaches a settled state", async () => {
    api.list.mockResolvedValue(page(["a", "b"]));
    await useWatchlistStore.getState().load("u1");
    expect(useWatchlistStore.getState()).toMatchObject({ ids: ["a", "b"], status: "ready", userId: "u1" });
  });

  it("settles into an error (never stuck loading) when the load fails", async () => {
    api.list.mockRejectedValue(new ApiError("boom", 500));
    await useWatchlistStore.getState().load("u1");
    expect(useWatchlistStore.getState().status).toBe("error");
    expect(useWatchlistStore.getState().error).toBeTruthy();
  });

  it("drops the previous user's ids when a different user signs in, and on logout", async () => {
    api.list.mockResolvedValueOnce(page(["a"]));
    await useWatchlistStore.getState().load("u1");
    api.list.mockImplementationOnce(() => new Promise(() => {})); // second user's load still in flight
    void useWatchlistStore.getState().load("u2");
    expect(useWatchlistStore.getState().ids).toEqual([]);
    await useWatchlistStore.getState().load(null);
    expect(useWatchlistStore.getState()).toMatchObject({ userId: null, ids: [], status: "idle" });
  });

  it("adds optimistically and reports success", async () => {
    api.add.mockResolvedValue(undefined);
    await useWatchlistStore.getState().add("a", "Bitcoin");
    expect(useWatchlistStore.getState().ids).toEqual(["a"]);
    expect(useWatchlistStore.getState().notice).toMatchObject({ kind: "success" });
  });

  it("treats 'already exists' as success-with-info and keeps the coin", async () => {
    api.add.mockRejectedValue(new ApiError("dup", 409, "WATCHLIST_ALREADY_EXISTS"));
    await useWatchlistStore.getState().add("a", "Bitcoin");
    expect(useWatchlistStore.getState().ids).toEqual(["a"]);
    expect(useWatchlistStore.getState().notice).toMatchObject({ kind: "info", message: expect.stringMatching(/already/i) });
  });

  it("rolls the add back when the coin is not found", async () => {
    api.add.mockRejectedValue(new ApiError("nope", 404, "COIN_NOT_FOUND"));
    await useWatchlistStore.getState().add("a");
    expect(useWatchlistStore.getState().ids).toEqual([]);
    expect(useWatchlistStore.getState().notice).toMatchObject({ kind: "error", message: expect.stringMatching(/not be found/i) });
  });

  it("rolls the add back on a server failure", async () => {
    api.add.mockRejectedValue(new ApiError("down", 500));
    await useWatchlistStore.getState().add("a");
    expect(useWatchlistStore.getState().ids).toEqual([]);
    expect(useWatchlistStore.getState().notice?.kind).toBe("error");
  });

  it("removes, and restores the coin if the server refuses", async () => {
    useWatchlistStore.setState({ ids: ["a", "b"], status: "ready" });
    api.remove.mockRejectedValueOnce(new ApiError("down", 500));
    await useWatchlistStore.getState().remove("a");
    expect(useWatchlistStore.getState().ids).toContain("a");
    api.remove.mockResolvedValueOnce(undefined);
    await useWatchlistStore.getState().remove("a");
    expect(useWatchlistStore.getState().ids).toEqual(["b"]);
    expect(useWatchlistStore.getState().notice).toMatchObject({ kind: "success" });
  });

  it("ignores a second click while a request for the same coin is in flight", async () => {
    let release: () => void = () => {};
    api.add.mockImplementation(() => new Promise<void>((resolve) => { release = resolve; }));
    const first = useWatchlistStore.getState().add("a");
    await useWatchlistStore.getState().add("a");
    release();
    await first;
    expect(api.add).toHaveBeenCalledTimes(1);
  });

  it("toggle adds then removes", async () => {
    api.add.mockResolvedValue(undefined);
    api.remove.mockResolvedValue(undefined);
    await useWatchlistStore.getState().toggle("a");
    expect(useWatchlistStore.getState().ids).toEqual(["a"]);
    await useWatchlistStore.getState().toggle("a");
    expect(useWatchlistStore.getState().ids).toEqual([]);
  });
});
