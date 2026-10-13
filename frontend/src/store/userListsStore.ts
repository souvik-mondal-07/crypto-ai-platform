import { create } from "zustand";

import { readJson, userKey, writeJson } from "../utils/userStorage";

/**
 * Client-side, per-user lists: recently viewed coins and the comparison selection.
 *
 * The WATCHLIST used to live here; since Phase 16 it is server-backed (see
 * watchlistStore.ts and /api/v1/watchlist). The recently-viewed list is still
 * device-local: it persists in this browser's localStorage only (namespaced by
 * user id, see utils/userStorage.ts) and does NOT sync across devices.
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
  recent: RecentCoin[];
  compare: string[];

  /** (Re)load persisted lists for a user; call whenever the signed-in user changes. */
  load: (userId: string | null) => void;
  recordView: (coin: Omit<RecentCoin, "viewed_at">) => void;
  clearRecent: () => void;
  toggleCompare: (coinId: string) => boolean;
  removeCompare: (coinId: string) => void;
  clearCompare: () => void;
}

const RECENT = "recently_viewed";

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
  recent: [],
  compare: [],

  load: (userId) => {
    if (get().userId === userId && get().userId !== null) return;
    const recent = readJson<unknown>(userKey(RECENT, userId), []);
    set({
      userId,
      recent: isRecentArray(recent) ? recent.slice(0, MAX_RECENT) : [],
      compare: [],
    });
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
