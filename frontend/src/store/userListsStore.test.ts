import { beforeEach, describe, expect, it } from "vitest";

import { MAX_COMPARE, MAX_RECENT, useUserListsStore } from "./userListsStore";

const coin = (n: number) => ({ coin_id: `c${n}`, name: `Coin ${n}`, symbol: `C${n}`, logo_url: null });

beforeEach(() => {
  localStorage.clear();
  useUserListsStore.setState({ userId: null, watchlist: [], recent: [], compare: [] });
});

describe("userListsStore", () => {
  it("toggles the watchlist and persists it per user", () => {
    useUserListsStore.getState().load("user-1");
    useUserListsStore.getState().toggleWatchlist("btc");
    expect(useUserListsStore.getState().watchlist).toEqual(["btc"]);

    // A different account on the same browser does not see it.
    useUserListsStore.getState().load("user-2");
    expect(useUserListsStore.getState().watchlist).toEqual([]);

    // ...and the first account gets it back.
    useUserListsStore.getState().load("user-1");
    expect(useUserListsStore.getState().watchlist).toEqual(["btc"]);

    useUserListsStore.getState().toggleWatchlist("btc");
    expect(useUserListsStore.getState().watchlist).toEqual([]);
  });

  it("records recently viewed coins newest-first without duplicates, capped", () => {
    useUserListsStore.getState().load("u");
    for (let i = 0; i < MAX_RECENT + 3; i += 1) useUserListsStore.getState().recordView(coin(i));
    useUserListsStore.getState().recordView(coin(5));

    const recent = useUserListsStore.getState().recent;
    expect(recent).toHaveLength(MAX_RECENT);
    expect(recent[0].coin_id).toBe("c5");
    expect(recent.filter((item) => item.coin_id === "c5")).toHaveLength(1);
  });

  it("limits the comparison selection and reports when the limit is hit", () => {
    const { toggleCompare } = useUserListsStore.getState();
    for (let i = 0; i < MAX_COMPARE; i += 1) expect(toggleCompare(`c${i}`)).toBe(true);
    expect(useUserListsStore.getState().toggleCompare("extra")).toBe(false);
    expect(useUserListsStore.getState().compare).toHaveLength(MAX_COMPARE);
    // Deselecting is always allowed.
    expect(useUserListsStore.getState().toggleCompare("c0")).toBe(true);
    expect(useUserListsStore.getState().compare).not.toContain("c0");
  });

  it("ignores corrupted saved data instead of crashing", () => {
    localStorage.setItem("crypto_ai_platform:watchlist:u", "{not json");
    localStorage.setItem("crypto_ai_platform:recently_viewed:u", JSON.stringify([{ nope: true }]));
    useUserListsStore.getState().load("u");
    expect(useUserListsStore.getState().watchlist).toEqual([]);
    expect(useUserListsStore.getState().recent).toEqual([]);
  });
});
