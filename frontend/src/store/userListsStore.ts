import { create } from "zustand";

import { readJson, userKey, writeJson } from "../utils/userStorage";

/**
 * Client-side, per-user lists: the watchlist, recently viewed coins and the
 * comparison selection.
 *
 * IMPORTANT — what this is and isn't: the backend currently exposes no
 * watchlist or view-history API, so the watchlist and recently-viewed list
 * persist in this browser's localStorage only (namespaced by user id, see
 * utils/userStorage.ts). They do NOT sync across devices, and nothing here
 * pretends otherwise. When a server API lands, replace the read/write calls
 * in `load`/`persist` below — components only talk to this store.
 *
 * The comparison selection is intentionally in-memory only (a working set for
 * the current visit, not saved data).
 */

export const MAX_COMPARE = 5;
export const MAX_RECENT = 10;

export interface RecentCoin {
  coin_id: string;
  name: string;
  symbol: string;
  logo_url: string | null;
  viewed_at: string;
}

interface UserListsState {
  userId: string | null;
  watchlist: string[];
  recent: RecentCoin[];
  compare: string[];

  /** (Re)load persisted lists for a user; call whenever the signed-in user changes. */
  load: (userId: string | null) => void;
  toggleWatchlist: (coinId: string) => void;
  recordView: (coin: Omit<RecentCoin, "viewed_at">) => void;
  clearRecent: () => void;
  toggleCompare: (coinId: string) => boolean;
  removeCompare: (coinId: string) => void;
  clearCompare: () => void;
}

const WATCHLIST = "watchlist";
const RECENT = "recently_viewed";

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isRecentArray(value: unknown): value is RecentCoin[] {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        item && typeof item === "object" && typeof item.coin_id === "string" && typeof item.name === "string"
    )
  );
}

export const useUserListsStore = create<UserListsState>((set, get) => ({
  userId: null,
  watchlist: [],
  recent: [],
  compare: [],

  load: (userId) => {
    if (get().userId === userId && get().userId !== null) return;
    const watchlist = readJson<unknown>(userKey(WATCHLIST, userId), []);
    const recent = readJson<unknown>(userKey(RECENT, userId), []);
    set({
      userId,
      watchlist: isStringArray(watchlist) ? watchlist : [],
      recent: isRecentArray(recent) ? recent.slice(0, MAX_RECENT) : [],
      compare: [],
    });
  },

  toggleWatchlist: (coinId) => {
    const { watchlist, userId } = get();
    const next = watchlist.includes(coinId) ? watchlist.filter((id) => id !== coinId) : [coinId, ...watchlist];
    set({ watchlist: next });
    writeJson(userKey(WATCHLIST, userId), next);
  },

  recordView: (coin) => {
    const { recent, userId } = get();
    const entry: RecentCoin = { ...coin, viewed_at: new Date().toISOString() };
    const next = [entry, ...recent.filter((item) => item.coin_id !== coin.coin_id)].slice(0, MAX_RECENT);
    set({ recent: next });
    writeJson(userKey(RECENT, userId), next);
  },

  clearRecent: () => {
    set({ recent: [] });
    writeJson(userKey(RECENT, get().userId), []);
  },

  toggleCompare: (coinId) => {
    const { compare } = get();
    if (compare.includes(coinId)) {
      set({ compare: compare.filter((id) => id !== coinId) });
      return true;
    }
    if (compare.length >= MAX_COMPARE) return false; // caller shows the limit message
    set({ compare: [...compare, coinId] });
    return true;
  },

  removeCompare: (coinId) => set({ compare: get().compare.filter((id) => id !== coinId) }),
  clearCompare: () => set({ compare: [] }),
}));
